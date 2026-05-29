"""
餐厅评价富化脚本 —— 品牌去重 + 双提供商并发

策略
----
1. 按品牌名对未富化餐厅分组（去掉门店后缀，如"(王府井店)"）
2. 连锁品牌（≥2家门店）：只调用一次 LLM，结果写入所有门店
3. 独立餐厅（唯一门店）：单独调用
4. 提供商池：Kimi（月之暗面）+ GLM-4-Flash（智谱），轮流分配
   - 两家各有独立 RPM 配额，相当于双倍吞吐
   - DeepSeek 无内置搜索，不参与此任务

用法
----
    python -m crawler.enrich_reviews                   # 富化全部
    python -m crawler.enrich_reviews --limit 100       # 限制数量
    python -m crawler.enrich_reviews --dry-run         # 只打印，不调用
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import cycle
from typing import Any, Callable, Dict, List, Optional

import httpx
from elasticsearch import AsyncElasticsearch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import cfg

logger = logging.getLogger(__name__)

# ── API Keys ──────────────────────────────────────────────────────────────────
_KIMI_KEY  = os.environ.get("MOONSHOT_API_KEY") or cfg.moonshot_api_key
_GLM_KEY   = os.environ.get("ZHIPU_API_KEY")   or cfg.zhipu_api_key

# ── ES ────────────────────────────────────────────────────────────────────────
_ES_INDEX = cfg.es_index_name
_ES_URL   = cfg.elasticsearch_url

# ── Prompt ────────────────────────────────────────────────────────────────────
_SYSTEM = (
    "你是一个严格基于搜索结果的餐厅信息提取助手。"
    "铁律：只能引用搜索到的真实帖子、评论或菜单页面里明确出现的内容，"
    "不得根据餐厅名称、菜系或常识进行任何推断或补充。"
    "宁可返回 not_found 或留空，也不能编造。"
)

_USER_TMPL = """\
请搜索以下餐厅/品牌的真实网络评价（重点搜小红书、大众点评、微博、知乎），\
仅凭搜索结果填写下方 JSON，不得超出搜索内容范围。

名称：{name}
地址参考：{address}

填写规则：
1. signature_dishes：评论或菜单中明确点名的具体菜品（如"黑松露薯条"），\
   不接受品类词（如"烧鸟""烤串"）；最多 5 道；无具体菜名则填 []
2. positive_ratio：格式 "X/Y"（X=正面评论数，Y=全部评论数含差评）；\
   找不到任何评论填 null
3. pros / cons：搜索结果里高频出现的具体描述，≤10 字/条，最多各 3 条；无则 []
4. source_count：实际找到的独立评论来源数
5. is_chain：true=确认连锁，false=确认非连锁，null=不确定
6. chain_note：若评价是品牌通用而非此门店专属，填"评价来自品牌整体，非本店专属"；否则 null

无结果时返回：{{"status": "not_found"}}
有结果时返回（只输出 JSON，禁止额外文字）：
{{
  "status": "found",
  "signature_dishes": [...],
  "positive_ratio": "X/Y" or null,
  "pros": [...],
  "cons": [...],
  "source_count": N,
  "is_chain": true/false/null,
  "chain_note": "..." or null
}}
"""

# ── 品牌名提取 ─────────────────────────────────────────────────────────────────
# 匹配末尾的门店后缀，如 (王府井店)、（成都太古里店）
_BRANCH_RE = re.compile(r'[\(（][^\)）]{1,30}[店铺馆厅坊居]\s*[\)）]\s*$')

def extract_brand(name: str) -> str:
    return _BRANCH_RE.sub('', name).strip() or name


# ── JSON 提取 ──────────────────────────────────────────────────────────────────
def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1:
        text = text[s: e + 1]
    return json.loads(text)


# ── 提供商定义 ─────────────────────────────────────────────────────────────────
@dataclass
class Provider:
    name: str
    sem: asyncio.Semaphore
    call: Callable  # async (name, address, client) -> dict


# ── Kimi 调用（多轮，内置 $web_search）────────────────────────────────────────
async def _kimi(name: str, address: str, client: httpx.AsyncClient) -> dict:
    headers = {"Authorization": f"Bearer {_KIMI_KEY}", "Content-Type": "application/json"}
    tools   = [{"type": "builtin_function", "function": {"name": "$web_search"}}]
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user",   "content": _USER_TMPL.format(name=name, address=address)},
    ]
    raw = ""
    for attempt in range(4):
        try:
            for _turn in range(10):
                resp = await client.post(
                    "https://api.moonshot.cn/v1/chat/completions",
                    json={"model": "moonshot-v1-8k", "messages": messages,
                          "tools": tools, "temperature": 0.0, "max_tokens": 1024},
                    headers=headers, timeout=60.0,
                )
                if resp.status_code == 429:
                    await asyncio.sleep(5 + 2 ** attempt * 5)
                    continue
                resp.raise_for_status()
                choice = resp.json()["choices"][0]
                msg    = choice["message"]
                finish = choice.get("finish_reason", "")
                if finish == "tool_calls" or msg.get("tool_calls"):
                    messages.append(msg)
                    for tc in msg.get("tool_calls", []):
                        messages.append({"role": "tool", "tool_call_id": tc["id"],
                                         "name": tc["function"]["name"], "content": ""})
                    continue
                raw = (msg.get("content") or "").strip()
                return _parse_json(raw) if raw else {"status": "not_found"}
            return {"status": "error", "detail": "loop_exceeded"}
        except json.JSONDecodeError:
            logger.warning("[kimi] JSON parse failed for %s: %s", name, raw[:120])
            return {"status": "parse_error"}
        except Exception as e:
            if attempt == 3:
                return {"status": "error", "detail": str(e)}
            await asyncio.sleep(2 ** attempt)
    return {"status": "error"}


# ── GLM 调用（单轮，内置 web_search）─────────────────────────────────────────
async def _glm(name: str, address: str, client: httpx.AsyncClient) -> dict:
    headers = {"Authorization": f"Bearer {_GLM_KEY}", "Content-Type": "application/json"}
    raw = ""
    for attempt in range(4):
        try:
            resp = await client.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                json={
                    "model": "glm-4-flash",
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user",   "content": _USER_TMPL.format(name=name, address=address)},
                    ],
                    "tools": [{"type": "web_search",
                               "web_search": {"enable": True, "search_result": True}}],
                    "temperature": 0.01,
                    "max_tokens": 1024,
                },
                headers=headers, timeout=60.0,
            )
            if resp.status_code == 429:
                await asyncio.sleep(5 + 2 ** attempt * 5)
                continue
            resp.raise_for_status()
            raw = (resp.json()["choices"][0]["message"].get("content") or "").strip()
            return _parse_json(raw) if raw else {"status": "not_found"}
        except json.JSONDecodeError:
            logger.warning("[glm] JSON parse failed for %s: %s", name, raw[:120])
            return {"status": "parse_error"}
        except Exception as e:
            if attempt == 3:
                return {"status": "error", "detail": str(e)}
            await asyncio.sleep(2 ** attempt)
    return {"status": "error"}


# ── ES 操作 ────────────────────────────────────────────────────────────────────
async def _fetch_unenriched(es: AsyncElasticsearch, limit: int) -> List[dict]:
    body = {
        "query": {"bool": {"must_not": {"exists": {"field": "review_summary"}}}},
        "_source": ["restaurant_id", "name", "address"],
        "size": min(limit, 10_000),
    }
    resp = await es.search(index=_ES_INDEX, body=body, scroll="10m")
    hits = list(resp["hits"]["hits"])
    sid  = resp.get("_scroll_id")
    while sid and len(hits) < limit:
        page = await es.scroll(scroll_id=sid, scroll="10m")
        if not page["hits"]["hits"]:
            break
        hits.extend(page["hits"]["hits"])
        sid = page.get("_scroll_id")
    return hits[:limit]


async def _write_many(es: AsyncElasticsearch, doc_ids: List[str], result: dict) -> None:
    update = {"review_summary": result}
    if result.get("status") == "found" and result.get("signature_dishes"):
        update["signature_dishes"] = result["signature_dishes"]
    ops = []
    for did in doc_ids:
        ops.append({"update": {"_index": _ES_INDEX, "_id": did, "retry_on_conflict": 3}})
        ops.append({"doc": update})
    if ops:
        await es.bulk(operations=ops, refresh=False)


# ── 主流程 ────────────────────────────────────────────────────────────────────
async def enrich_all(limit: int = 999_999, dry_run: bool = False) -> None:
    missing = [k for k, v in [("Kimi", _KIMI_KEY), ("GLM", _GLM_KEY)] if not v]
    if missing and not dry_run:
        logger.error("缺少 API Key：%s", ", ".join(missing))
        sys.exit(1)

    es = AsyncElasticsearch(_ES_URL, request_timeout=30)
    try:
        logger.info("获取未富化餐厅列表...")
        hits = await _fetch_unenriched(es, limit)
        logger.info("共 %d 家待富化", len(hits))

        # ── 按品牌分组 ─────────────────────────────────────────────────────
        brand_map: Dict[str, List[dict]] = defaultdict(list)
        for h in hits:
            brand_map[extract_brand(h["_source"]["name"])].append(h)

        # 连锁品牌先处理（节省最多 API 调用），再处理独立餐厅
        groups = sorted(brand_map.values(), key=lambda g: -len(g))
        chains   = sum(1 for g in groups if len(g) > 1)
        uniq     = sum(1 for g in groups if len(g) == 1)
        saved    = sum(len(g) - 1 for g in groups if len(g) > 1)
        logger.info("品牌分组：%d 个连锁品牌 / %d 家独立餐厅 / 节省 %d 次 API 调用",
                    chains, uniq, saved)

        # ── 提供商池（轮流分配） ───────────────────────────────────────────
        providers: List[Provider] = []
        if _KIMI_KEY:
            providers.append(Provider("Kimi", asyncio.Semaphore(50), _kimi))
        if _GLM_KEY:
            providers.append(Provider("GLM",  asyncio.Semaphore(3),  _glm))
        if not providers:
            logger.error("没有可用的 API 提供商")
            sys.exit(1)

        provider_cycle = cycle(providers)

        # ── 统计 ──────────────────────────────────────────────────────────
        done = found = not_found = errors = 0
        total = len(groups)
        t0    = time.time()

        async with httpx.AsyncClient(trust_env=False) as http_client:

            async def process_group(group: List[dict], provider: Provider) -> None:
                nonlocal done, found, not_found, errors
                rep  = group[0]["_source"]
                name = extract_brand(rep["name"])  # 用品牌名搜索
                addr = rep.get("address", "")
                ids  = [h["_id"] for h in group]

                async with provider.sem:
                    if dry_run:
                        print(f"\n[{provider.name}] {name}（{len(group)} 家门店）")
                        result: dict = {"status": "dry_run"}
                    else:
                        result = await provider.call(name, addr, http_client)

                # 连锁品牌补充说明
                if len(group) > 1 and result.get("status") == "found":
                    if not result.get("chain_note"):
                        result["chain_note"] = f"评价来自品牌整体，非本店专属（共 {len(group)} 家门店）"
                    result["is_chain"] = True

                if not dry_run:
                    await _write_many(es, ids, result)

                done += 1
                status = result.get("status", "")
                if status == "found":
                    found += 1
                elif status == "not_found":
                    not_found += 1
                else:
                    errors += 1

                if done % 50 == 0 or done == total:
                    elapsed = time.time() - t0
                    rate    = done / elapsed if elapsed else 0
                    eta     = (total - done) / rate if rate else 0
                    logger.info(
                        "[%d/%d] found=%d not_found=%d err=%d  %.1f组/min  ETA %.0f分钟",
                        done, total, found, not_found, errors, rate * 60, eta / 60,
                    )

            # 把所有任务分配给提供商，并发运行
            tasks = [
                process_group(group, next(provider_cycle))
                for group in groups
            ]
            await asyncio.gather(*tasks)

        elapsed = time.time() - t0
        logger.info(
            "富化完成：%d 组（覆盖 %d 家门店），found=%d，not_found=%d，err=%d，耗时 %.1f 分钟",
            total, len(hits), found, not_found, errors, elapsed / 60,
        )
    finally:
        await es.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="LLM 餐厅评价富化（品牌去重 + 双提供商）")
    parser.add_argument("--limit",   type=int, default=999_999, help="最多处理 N 家")
    parser.add_argument("--dry-run", action="store_true",       help="只打印，不调用 API")
    args = parser.parse_args()
    asyncio.run(enrich_all(args.limit, args.dry_run))


if __name__ == "__main__":
    main()
