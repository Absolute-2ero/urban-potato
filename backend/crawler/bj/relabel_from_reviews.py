"""
从现有数据推断过敏原/饮食标签（不需要额外搜索）。

输入：ES 中每家餐厅的 name, cuisine_type, tags, description,
      review_summary.signature_dishes, pros, cons
输出：更新 allergens, allergen_free, diet_labels 字段

使用 GLM-4-Flash（纯推理，无网络搜索）。
品牌去重：同品牌只推理一次，结果写入所有门店。
每个标签附带置信度（high/medium/low），供前端展示。

用法：
    python -m crawler.relabel_from_reviews                  # 全量
    python -m crawler.relabel_from_reviews --limit 100      # 测试
    python -m crawler.relabel_from_reviews --overwrite      # 重跑覆盖已有标签
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
from typing import Any, Dict, List, Optional

import httpx
from elasticsearch import AsyncElasticsearch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import cfg

logger = logging.getLogger(__name__)

_KIMI_KEY = os.environ.get("MOONSHOT_API_KEY") or cfg.moonshot_api_key
_KIMI_URL = "https://api.moonshot.cn/v1/chat/completions"
_ES_URL   = cfg.elasticsearch_url
_INDEX    = cfg.es_index_name

_VALID_ALLERGENS = {
    "peanut", "tree_nut", "dairy", "gluten", "shellfish",
    "soy", "egg", "sesame", "fish",
}
_VALID_DIET_LABELS = {
    "vegan", "vegetarian", "halal", "kosher", "organic",
    "gluten-free", "dairy-free", "keto", "high-protein",
    "low-carb", "low-calorie", "low-sodium",
    "nut-free", "shellfish-free", "soy-free",
}

_BRANCH_RE = re.compile(r'[\(（][^\)）]{1,30}[店铺馆厅坊居]\s*[\)）]\s*$')
def extract_brand(name: str) -> str:
    return _BRANCH_RE.sub('', name).strip() or name

_SYSTEM = "你是餐厅食品安全标注助手。只根据所给文字标注，绝不凭通识推断，宁可漏标不可误标。"

_USER_TMPL = """\
餐厅名称：{name}
菜系：{cuisine_type}
标签/描述：{tags}
招牌菜：{dishes}

━━ 步骤1：diet_labels ━━
检查"餐厅名称"是否含以下关键词（仅检查名称，不检查描述）：
· 含"纯素"或"全素"或"vegan" → diet_labels = [vegan(high), vegetarian(high)]
· 含"素食"或"蔬食"或"素菜"或"素斋"或"斋菜"或"佛斋" → diet_labels = [vegetarian(high)]
  ⚠️ "斋"单独出现或作品牌字号（鲁味斋/和庆斋等）→ 不算，diet_labels=[]
· 含"清真" → diet_labels = [halal(high)]
· 以上均无 → diet_labels = []，不得因"有蔬菜菜品"就标vegetarian

━━ 步骤2：allergen_free（仅依据步骤1结果）━━
· diet_labels含vegan → allergen_free = [shellfish(high), fish(high), egg(high), dairy(high)]
· diet_labels含vegetarian（不含vegan）→ allergen_free = [shellfish(high), fish(high)]
· 其他 → allergen_free = []

━━ 步骤3：allergens（只看菜名/描述，找到才填）━━
仅当以下词出现在"标签/描述"或"招牌菜"中才填：
· shellfish：虾/蟹/贝/扇贝/鲍鱼/龙虾/海鲜 → high（"海鲜"出现即可）
· fish：鱼/三文鱼/鳗鱼/生鱼片（"鱼香"不算）→ high
· gluten：面条/拉面/饺子/包子/面包/披萨/馒头 → high
· dairy：奶酪/芝士/黄油/奶油/牛奶 → medium
· egg：鸡蛋/鸭蛋/温泉蛋（菜名中明确出现）→ medium
· soy：豆腐/豆浆/毛豆/纳豆（酱油不算）→ medium
· peanut：花生/花生酱 → medium
· sesame：芝麻/麻酱 → medium
· tree_nut：核桃/腰果/杏仁/松子 → medium
⚠️ 标签/描述和招牌菜均为空或"（无）"时，allergens = []

只返回 JSON：
{{
  "allergens":     [{{"label":"shellfish","confidence":"high"}}, ...],
  "allergen_free": [{{"label":"fish","confidence":"high"}}, ...],
  "diet_labels":   [{{"label":"vegetarian","confidence":"high"}}, ...]
}}
"""


def _make_prompt(doc: Dict[str, Any]) -> str:
    rs = doc.get("review_summary") or {}
    dishes = ", ".join(rs.get("signature_dishes") or []) or "（无）"
    pros   = ", ".join(rs.get("pros") or []) or "（无）"
    raw_tags = doc.get("tags") or []
    desc     = doc.get("description") or ""
    tags_str = ", ".join(raw_tags[:15]) or desc[:200] or "（无）"
    return _USER_TMPL.format(
        name=doc.get("name", ""),
        cuisine_type=doc.get("cuisine_type", ""),
        tags=tags_str,
        dishes=dishes[:300],
        pros=pros[:150],
    )


_VALID_CONFIDENCES = {"high", "medium", "low"}

def _parse_item(item: Any, valid_labels: set) -> Optional[Dict]:
    """解析 {"label": ..., "confidence": ...} 格式，兼容旧版纯字符串格式。"""
    if isinstance(item, str):
        return {"label": item, "confidence": "medium"} if item in valid_labels else None
    if isinstance(item, dict):
        label = item.get("label", "")
        conf  = item.get("confidence", "medium")
        if label not in valid_labels:
            return None
        if conf not in _VALID_CONFIDENCES:
            conf = "medium"
        return {"label": label, "confidence": conf}
    return None


# 含这些词的餐厅不可能是素食，强制去掉 vegetarian/vegan 标签
_NON_VEGETARIAN_KEYWORDS = {
    "海鲜", "鱼", "虾", "蟹", "贝", "龙虾", "鲍鱼",
    "火锅", "涮肉", "烤肉", "烧烤", "炙烤", "BBQ",
    "牛肉", "羊肉", "猪肉", "鸡肉", "排骨", "烤鸭",
    "肉蟹", "海胆", "刺身", "日料", "寿司", "居酒屋",
    "烧鸟", "串串", "烤串", "卤肉", "卤煮", "炸鸡",
}
# 名字含这些词时优先判为素食（覆盖上面的非素食关键词）
_VEG_OVERRIDE_KEYWORDS = {"素火锅", "素烧烤", "素串串", "素炙烤"}


def _is_non_vegetarian(name: str) -> bool:
    if any(kw in name for kw in _VEG_OVERRIDE_KEYWORDS):
        return False
    return any(kw in name for kw in _NON_VEGETARIAN_KEYWORDS)


def _parse_result(raw: str, restaurant_name: str = "", full_name: str = "") -> Optional[Dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        raw = raw.rsplit("```", 1)[0]
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e == -1:
        return None
    try:
        data = json.loads(raw[s: e + 1])
    except json.JSONDecodeError:
        return None

    allergens   = [r for item in data.get("allergens", [])
                   if (r := _parse_item(item, _VALID_ALLERGENS))]
    diet_labels = [r for item in data.get("diet_labels", [])
                   if (r := _parse_item(item, _VALID_DIET_LABELS))]

    # 名称含非素食关键词时，强制移除 vegetarian/vegan 标签
    if _is_non_vegetarian(restaurant_name):
        diet_labels = [d for d in diet_labels
                       if d["label"] not in ("vegetarian", "vegan")]

    dl_labels       = {d["label"] for d in diet_labels}
    allergen_labels = {a["label"] for a in allergens}

    # vegan + 动物性成分（蛋/奶/海鲜）→ 降级为 vegetarian
    if "vegan" in dl_labels and allergen_labels & {"egg", "dairy", "shellfish", "fish"}:
        diet_labels = [
            {"label": "vegetarian", "confidence": d["confidence"]} if d["label"] == "vegan" else d
            for d in diet_labels
        ]
        dl_labels = {d["label"] for d in diet_labels}

    # 全名含"清真"（含括号后缀）且未标 halal → 补全
    if "清真" in (full_name or restaurant_name) and "halal" not in dl_labels:
        diet_labels.append({"label": "halal", "confidence": "high"})
        dl_labels.add("halal")

    # allergen_free 由 diet_labels 推导，不依赖模型输出
    if "vegan" in dl_labels:
        allergen_free = [
            {"label": l, "confidence": "high"}
            for l in ["shellfish", "fish", "egg", "dairy"]
            if l not in allergen_labels
        ]
    elif "vegetarian" in dl_labels:
        allergen_free = [
            {"label": l, "confidence": "high"}
            for l in ["shellfish", "fish"]
            if l not in allergen_labels
        ]
    else:
        allergen_free = []

    return {
        # 带置信度的完整结构（供前端展示）
        "allergens_detail":     allergens,
        "allergen_free_detail": allergen_free,
        "diet_labels_detail":   diet_labels,
        # 扁平列表保持后端过滤兼容
        "allergens":     [a["label"] for a in allergens],
        "allergen_free": [a["label"] for a in allergen_free],
        "diet_labels":   [a["label"] for a in diet_labels],
    }


async def _call_kimi(prompt: str, client: httpx.AsyncClient, restaurant_name: str = "", full_name: str = "") -> Optional[Dict]:
    raw = ""
    for attempt in range(4):
        try:
            resp = await client.post(
                _KIMI_URL,
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens":  500,
                },
                headers={"Authorization": f"Bearer {_KIMI_KEY}", "Content-Type": "application/json"},
                timeout=30.0,
            )
            if resp.status_code == 429:
                await asyncio.sleep(5 + 2 ** attempt * 5)
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            result = _parse_result(raw, restaurant_name, full_name)
            if result is not None:
                return result
            logger.warning("JSON parse failed: %s", raw[:120])
            return None
        except Exception as exc:
            if attempt == 3:
                logger.warning("Kimi call failed: %s", exc)
                return None
            await asyncio.sleep(2 ** attempt)
    return None


async def _fetch_docs(es: AsyncElasticsearch, limit: int, overwrite: bool) -> List[Dict]:
    query: Dict[str, Any] = {"match_all": {}} if overwrite else {
        "bool": {"must_not": {"exists": {"field": "allergens"}}}
    }
    resp = await es.search(
        index=_INDEX,
        body={
            "query": query,
            "_source": ["name", "cuisine_type", "tags", "description", "review_summary"],
            "size": min(limit, 10_000),
        },
        scroll="10m",
    )
    hits = list(resp["hits"]["hits"])
    sid  = resp.get("_scroll_id")
    while sid and len(hits) < limit:
        page = await es.scroll(scroll_id=sid, scroll="10m")
        if not page["hits"]["hits"]:
            break
        hits.extend(page["hits"]["hits"])
        sid = page.get("_scroll_id")
    return hits[:limit]


async def _write_many(es: AsyncElasticsearch, doc_ids: List[str], result: Dict, is_chain: bool, branch_count: int) -> None:
    chain_update = {"is_chain": True, "chain_branch_count": branch_count} if is_chain else {}
    ops = []
    for did in doc_ids:
        ops.append({"update": {"_index": _INDEX, "_id": did, "retry_on_conflict": 3}})
        ops.append({"doc": {**result, **chain_update}})
    if ops:
        await es.bulk(operations=ops, refresh=False)


async def relabel_all(limit: int = 999_999, overwrite: bool = False, concurrency: int = 20) -> None:
    if not _KIMI_KEY:
        logger.error("MOONSHOT_API_KEY 未设置")
        sys.exit(1)

    es = AsyncElasticsearch(_ES_URL, request_timeout=30)
    try:
        logger.info("获取待处理文档...")
        hits = await _fetch_docs(es, limit, overwrite)
        logger.info("共 %d 家餐厅待重标签", len(hits))

        # 按品牌分组
        brand_map: Dict[str, List[Dict]] = defaultdict(list)
        for h in hits:
            brand = extract_brand(h["_source"]["name"])
            brand_map[brand].append(h)

        groups = sorted(brand_map.values(), key=lambda g: -len(g))
        saved  = sum(len(g) - 1 for g in groups if len(g) > 1)
        logger.info("品牌分组：%d 个品牌，节省 %d 次 API 调用", len(groups), saved)

        sem   = asyncio.Semaphore(concurrency)
        done  = updated = 0
        total = len(groups)
        t0    = time.time()

        async with httpx.AsyncClient(trust_env=False) as http_client:

            async def process_group(group: List[Dict]) -> None:
                nonlocal done, updated
                rep    = group[0]["_source"]
                ids    = [h["_id"] for h in group]
                prompt = _make_prompt(rep)

                async with sem:
                    result = await _call_kimi(prompt, http_client, extract_brand(rep["name"]), rep.get("name", ""))

                if result:
                    await _write_many(es, ids, result, len(group) > 1, len(group))
                    updated += len(ids)

                done += 1
                if done % 100 == 0 or done == total:
                    elapsed = time.time() - t0
                    rate    = done / elapsed if elapsed else 0
                    eta     = (total - done) / rate if rate else 0
                    logger.info(
                        "[%d/%d品牌] 已更新门店=%d  %.0f品牌/min  ETA %.0f分钟",
                        done, total, updated, rate * 60, eta / 60,
                    )

            await asyncio.gather(*(process_group(g) for g in groups))

        logger.info("重标签完成：%d 品牌组 / %d 家门店更新，耗时 %.1f 分钟",
                    total, updated, (time.time() - t0) / 60)
    finally:
        await es.close()


async def fix_logic_errors() -> None:
    """对已标注记录做纯 Python 逻辑修正（不调用 LLM）。"""
    es = AsyncElasticsearch(_ES_URL, request_timeout=30)
    try:
        ops: list = []

        # Fix A: vegan + 动物性 allergens → 降级为 vegetarian
        r = await es.search(index=_INDEX, body={
            "query": {"bool": {
                "must": [{"term": {"diet_labels": "vegan"}}],
                "should": [{"term": {"allergens": a}} for a in ["egg", "dairy", "shellfish", "fish"]],
                "minimum_should_match": 1,
            }},
            "_source": ["name", "diet_labels_detail", "allergens"],
            "size": 1000,
        })
        for h in r["hits"]["hits"]:
            s   = h["_source"]
            did = h["_id"]
            conf = next((d.get("confidence", "high") for d in (s.get("diet_labels_detail") or [])
                         if d.get("label") == "vegan"), "high")
            dl   = [d for d in (s.get("diet_labels_detail") or []) if d.get("label") != "vegan"]
            dl.append({"label": "vegetarian", "confidence": conf})
            dl_set = {d["label"] for d in dl}
            al_set = set(s.get("allergens") or [])
            af = ([{"label": l, "confidence": "high"} for l in ["shellfish", "fish"] if l not in al_set]
                  if "vegetarian" in dl_set else [])
            ops += [
                {"update": {"_index": _INDEX, "_id": did, "retry_on_conflict": 3}},
                {"doc": {"diet_labels": [d["label"] for d in dl], "diet_labels_detail": dl,
                         "allergen_free": [a["label"] for a in af], "allergen_free_detail": af}},
            ]
        logger.info("Fix A (vegan降级vegetarian): %d 条", r["hits"]["total"]["value"])

        # Fix B: 全名含"清真"但无 halal
        r2 = await es.search(index=_INDEX, body={
            "query": {"bool": {
                "must": [
                    {"exists": {"field": "allergens"}},
                    {"wildcard": {"name": "*清真*"}},
                ],
                "must_not": [{"term": {"diet_labels": "halal"}}],
            }},
            "_source": ["name", "diet_labels", "diet_labels_detail"],
            "size": 1000,
        })
        for h in r2["hits"]["hits"]:
            s   = h["_source"]
            did = h["_id"]
            dl  = list(s.get("diet_labels_detail") or [])
            dl.append({"label": "halal", "confidence": "high"})
            ops += [
                {"update": {"_index": _INDEX, "_id": did, "retry_on_conflict": 3}},
                {"doc": {"diet_labels": [d["label"] for d in dl], "diet_labels_detail": dl}},
            ]
        logger.info("Fix B (清真补全): %d 条", r2["hits"]["total"]["value"])

        # Fix C: 误标 vegetarian（名含非素食词，经新规则判断仍为非素食）
        r3 = await es.search(index=_INDEX, body={
            "query": {"bool": {
                "must": [{"term": {"diet_labels": "vegetarian"}}],
                "should": [{"wildcard": {"name": f"*{kw}*"}} for kw in _NON_VEGETARIAN_KEYWORDS],
                "minimum_should_match": 1,
            }},
            "_source": ["name", "diet_labels_detail"],
            "size": 1000,
        })
        fixed_c = 0
        for h in r3["hits"]["hits"]:
            s    = h["_source"]
            did  = h["_id"]
            name = s.get("name", "")
            if _is_non_vegetarian(name):  # 含素火锅豁免
                dl = [d for d in (s.get("diet_labels_detail") or [])
                      if d.get("label") not in ("vegetarian", "vegan")]
                ops += [
                    {"update": {"_index": _INDEX, "_id": did, "retry_on_conflict": 3}},
                    {"doc": {"diet_labels": [d["label"] for d in dl], "diet_labels_detail": dl,
                             "allergen_free": [], "allergen_free_detail": []}},
                ]
                fixed_c += 1
        logger.info("Fix C (误标vegetarian清除): %d 条", fixed_c)

        if ops:
            resp = await es.bulk(operations=ops, refresh=True)
            errs = [i for i in resp["items"] if i.get("update", {}).get("error")]
            logger.info("批量更新完成：%d 条，%d 错误", len(ops) // 2, len(errs))
        else:
            logger.info("无需修正")
    finally:
        await es.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="LLM 重标签（Kimi，品牌去重）")
    parser.add_argument("--limit",       type=int, default=999_999)
    parser.add_argument("--overwrite",   action="store_true", help="覆盖已有标签")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--fix-logic",   action="store_true", help="修正已标注记录的逻辑错误（无 LLM 调用）")
    args = parser.parse_args()
    if args.fix_logic:
        asyncio.run(fix_logic_errors())
    else:
        asyncio.run(relabel_all(args.limit, args.overwrite, args.concurrency))


if __name__ == "__main__":
    main()
