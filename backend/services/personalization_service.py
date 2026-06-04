"""
Personalization service.

- record_interaction(): 记录用户与餐厅的交互（view / save / click）
- get_user_preference_vector(): 基于近期交互历史，构建用户偏好向量
  算法：取最近 N 条交互餐厅的 embedding，做指数加权平均（越近权重越高）
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional

from database import get_es, get_sqlite

logger = logging.getLogger(__name__)

_INDEX = "restaurants"
_MAX_HISTORY = 50  # 用于构建偏好向量的最大历史条数
_DECAY = 0.92       # 每条旧记录的衰减系数（最近一条权重=1, 次新=0.92, …）


async def record_interaction(
    user_id: int,
    restaurant_id: str,
    interaction_type: str = "view",
) -> None:
    """记录一条用户-餐厅交互。interaction_type: 'view' | 'save' | 'click'"""
    db = get_sqlite()
    await db.execute(
        """INSERT INTO user_interactions (user_id, restaurant_id, interaction_type)
           VALUES (?, ?, ?)""",
        (user_id, restaurant_id, interaction_type),
    )
    await db.commit()


async def get_recent_interactions(
    user_id: int,
    limit: int = _MAX_HISTORY,
) -> List[str]:
    """返回用户最近交互的 restaurant_id 列表（最新在前）。"""
    db = get_sqlite()
    async with db.execute(
        """SELECT DISTINCT restaurant_id FROM user_interactions
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (user_id, limit),
    ) as cur:
        rows = await cur.fetchall()
    return [r["restaurant_id"] for r in rows]


async def get_user_preference_vector(
    user_id: int,
) -> Optional[List[float]]:
    """
    构建用户偏好向量：
    1. 取最近 N 条唯一餐厅
    2. 从 ES 批量拉取它们的 embedding
    3. 指数加权平均（越近权重越高）
    """
    restaurant_ids = await get_recent_interactions(user_id)
    if not restaurant_ids:
        return None

    es = get_es()
    try:
        resp = await es.mget(
            index=_INDEX,
            body={"ids": restaurant_ids},
            source_includes=["embedding"],
        )
    except Exception as exc:
        logger.warning("mget for user pref failed: %s", exc)
        return None

    dims: Optional[int] = None
    weighted_sum: Optional[List[float]] = None
    total_weight = 0.0

    for rank, doc in enumerate(resp["docs"]):
        if not doc.get("found"):
            continue
        vec = doc.get("_source", {}).get("embedding")
        if not vec or not isinstance(vec, list):
            continue

        w = _DECAY ** rank  # 越早的记录权重越低
        if weighted_sum is None:
            dims = len(vec)
            weighted_sum = [0.0] * dims
        for i, v in enumerate(vec):
            weighted_sum[i] += v * w
        total_weight += w

    if weighted_sum is None or total_weight == 0:
        return None

    # L2 normalize
    raw = [x / total_weight for x in weighted_sum]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """两个已归一化向量的余弦相似度（点积）。"""
    if len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
