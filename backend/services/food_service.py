from __future__ import annotations

import json
import logging
from typing import List, Optional

import httpx

from config import cfg
from database import get_redis, get_sqlite
from models.food import FoodItem, FoodSearchResult

logger = logging.getLogger(__name__)

_LLM_CACHE_TTL = 7 * 24 * 3600  # 7 天
_LLM_CACHE_PREFIX = "llm:food:"


# ── SQLite FTS 搜索 ──────────────────────────────────────────────────────────

def _contains_chinese(s: str) -> bool:
    return any('一' <= c <= '鿿' for c in s)


async def search_food_db(query: str, limit: int = 10) -> List[FoodItem]:
    """
    用 FTS5 + LIKE 在本地食物数据库中搜索。
    中文查询用逐字 AND（FTS5 unicode61 按字符切词）；英文用前缀搜索。
    如果 FTS 无结果则退而用 LIKE 模糊匹配。
    """
    conn = get_sqlite()
    q = query.strip()

    if _contains_chinese(q):
        # 中文：每个字符独立作为一个 AND 条件，提高精度
        chars = [c for c in q if not c.isspace()]
        fts_query = " AND ".join(chars) if chars else q
    else:
        # 英文：按空格分词，前缀搜索
        tokens = q.split()
        fts_query = " OR ".join(f"{t}*" for t in tokens) if tokens else q

    try:
        rows = await conn.execute_fetchall(
            """
            SELECT fi.id, fi.name_zh, fi.name_en, fi.name_pinyin,
                   fi.calories, fi.protein_g, fi.fat_g, fi.carb_g,
                   fi.sodium_mg, fi.fiber_g, fi.diet_labels
            FROM food_fts
            JOIN food_items fi ON fi.id = food_fts.rowid
            WHERE food_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        )
    except Exception:
        rows = []

    # Fallback: LIKE 模糊匹配（捕获 FTS 未能命中的情况）
    if not rows:
        like_q = f"%{q}%"
        rows = await conn.execute_fetchall(
            """
            SELECT id, name_zh, name_en, name_pinyin,
                   calories, protein_g, fat_g, carb_g,
                   sodium_mg, fiber_g, diet_labels
            FROM food_items
            WHERE name_zh LIKE ? OR name_en LIKE ? OR name_pinyin LIKE ?
            LIMIT ?
            """,
            (like_q, like_q, like_q, limit),
        )
    results: List[FoodItem] = []
    for r in rows:
        try:
            diet_labels = json.loads(r[10]) if r[10] else []
        except Exception:
            diet_labels = []
        results.append(
            FoodItem(
                food_id=r[0],
                name_zh=r[1],
                name_en=r[2],
                name_pinyin=r[3],
                calories=float(r[4] or 0),
                protein_g=float(r[5] or 0),
                fat_g=float(r[6] or 0),
                carb_g=float(r[7] or 0),
                sodium_mg=float(r[8]) if r[8] is not None else None,
                fiber_g=float(r[9]) if r[9] is not None else None,
                diet_labels=diet_labels,
            )
        )
    return results


# ── LLM fallback ─────────────────────────────────────────────────────────────

async def _query_llm(food_name: str) -> Optional[FoodItem]:
    """调用 DeepSeek API 估算食物营养信息。返回未持久化的 FoodItem（food_id=None）。"""
    cache_key = _LLM_CACHE_PREFIX + food_name.lower().strip()
    redis = get_redis()

    # 检查 Redis 缓存
    cached = await redis.get(cache_key)
    if cached:
        try:
            data = json.loads(cached)
            return FoodItem(**data)
        except Exception:
            pass

    if not cfg.deepseek_api_key:
        logger.warning("DEEPSEEK_API_KEY not configured, skipping LLM fallback")
        return None

    prompt = f"""请给出食物「{food_name}」每100g的营养信息，以JSON格式输出，字段如下：
{{
  "name_zh": "中文名",
  "name_en": "英文名（若无则同中文）",
  "name_pinyin": "拼音（若无则留空）",
  "calories_per_100g": 数字,
  "protein_g": 数字,
  "fat_g": 数字,
  "carb_g": 数字,
  "sodium_mg": 数字,
  "fiber_g": 数字,
  "diet_labels": ["vegan"|"vegetarian"|"halal"|"kosher"|"gluten-free"|"dairy-free"|"keto"|"high-protein"|"low-carb"|"low-calorie"|"low-sodium"|"nut-free"|"shellfish-free"|"soy-free"|"organic" 等，只填适用的]
}}
只输出JSON，不要解释。"""

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # 去掉可能的 markdown fence
            content = content.strip().strip("```json").strip("```").strip()
            data = json.loads(content)
    except Exception as exc:
        logger.error("LLM query failed for '%s': %s", food_name, exc)
        return None

    item = FoodItem(
        food_id=None,
        name_zh=data.get("name_zh", food_name),
        name_en=data.get("name_en"),
        name_pinyin=data.get("name_pinyin"),
        calories=float(data.get("calories_per_100g") or data.get("calories") or 0),
        protein_g=float(data.get("protein_g", 0)),
        fat_g=float(data.get("fat_g", 0)),
        carb_g=float(data.get("carb_g", 0)),
        sodium_mg=float(data.get("sodium_mg", 0)),
        fiber_g=float(data.get("fiber_g", 0)),
        diet_labels=data.get("diet_labels", []),
        source="llm_inferred",
        verified=False,
    )

    # 写入 Redis 缓存（7天），key 存的是 dict（food_id 为 None）
    await redis.set(cache_key, item.model_dump_json(), ex=_LLM_CACHE_TTL)
    logger.info("LLM estimated nutrition for '%s', cached.", food_name)
    return item


# ── 主入口：搜索食物 ──────────────────────────────────────────────────────────

async def search_food(query: str, limit: int = 10) -> FoodSearchResult:
    """
    1. 先查 SQLite FTS；
    2. 没找到则调 LLM（需要用户确认才存库）；
    3. LLM 也失败则返回 not_found。
    """
    db_hits = await search_food_db(query, limit)
    if db_hits:
        return FoodSearchResult(
            items=db_hits,
            source="database",
            requires_confirm=False,
        )

    llm_item = await _query_llm(query)
    if llm_item:
        return FoodSearchResult(
            items=[llm_item],
            source="llm_estimated",
            requires_confirm=True,
        )

    return FoodSearchResult(items=[], source="not_found", requires_confirm=False)


# ── 用户确认后写入 SQLite ─────────────────────────────────────────────────────

async def confirm_and_store(item: FoodItem) -> FoodItem:
    """
    将 LLM 估算结果以 verified=1 写入 SQLite food_items 表，返回含 food_id 的 FoodItem。
    (BR-03: 先确认再入库)
    """
    conn = get_sqlite()
    labels_json = json.dumps(item.diet_labels, ensure_ascii=False)
    cursor = await conn.execute(
        """
        INSERT INTO food_items
            (name_zh, name_en, name_pinyin, calories,
             protein_g, fat_g, carb_g, sodium_mg, fiber_g, diet_labels, verified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            item.name_zh,
            item.name_en,
            item.name_pinyin,
            item.calories,
            item.protein_g,
            item.fat_g,
            item.carb_g,
            item.sodium_mg,
            item.fiber_g,
            labels_json,
        ),
    )
    await conn.commit()
    new_id = cursor.lastrowid
    logger.info("Stored LLM food item '%s' as id=%d", item.name_zh, new_id)
    return item.model_copy(update={"food_id": new_id})


async def get_food_by_id(food_id: int) -> Optional[FoodItem]:
    conn = get_sqlite()
    rows = await conn.execute_fetchall(
        "SELECT id, name_zh, name_en, name_pinyin, calories, "
        "protein_g, fat_g, carb_g, sodium_mg, fiber_g, diet_labels "
        "FROM food_items WHERE id = ?",
        (food_id,),
    )
    if not rows:
        return None
    r = rows[0]
    try:
        diet_labels = json.loads(r[10]) if r[10] else []
    except Exception:
        diet_labels = []
    return FoodItem(
        food_id=r[0], name_zh=r[1], name_en=r[2], name_pinyin=r[3],
        calories=float(r[4] or 0), protein_g=float(r[5] or 0),
        fat_g=float(r[6] or 0), carb_g=float(r[7] or 0),
        sodium_mg=float(r[8]) if r[8] is not None else None,
        fiber_g=float(r[9]) if r[9] is not None else None,
        diet_labels=diet_labels,
    )
