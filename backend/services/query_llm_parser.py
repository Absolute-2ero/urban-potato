"""
LLM 查询理解：用 Kimi 把自然语言 query 解析为结构化搜索参数。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx

from config import cfg

logger = logging.getLogger(__name__)

_KIMI_KEY = os.environ.get("MOONSHOT_API_KEY") or cfg.moonshot_api_key
_KIMI_URL = "https://api.moonshot.cn/v1/chat/completions"

_VALID_DIET_LABELS = {
    "vegan", "vegetarian", "halal", "kosher", "organic",
    "gluten-free", "dairy-free", "keto", "high-protein",
    "low-carb", "low-calorie", "low-sodium",
    "nut-free", "shellfish-free", "soy-free",
}
_VALID_ALLERGENS = {
    "peanut", "tree_nut", "dairy", "gluten",
    "shellfish", "soy", "egg", "sesame", "fish",
}

_SYSTEM = "你是餐厅搜索助手，把用户自然语言查询解析为结构化参数，只返回 JSON，不含任何解释。"

_PROMPT = """\
用户查询："{query}"

请提取以下字段（无法确定的填 null 或 []）：
- q: 核心搜索词（食物/餐厅名称），去掉位置、距离、价格、饮食偏好等修饰词
- location: 位置区域名称（如"三里屯"、"海淀区"），无则 null
- radius_km: 距离半径（数字，"500米"→0.5，"1公里"→1，"附近"默认→1），无则 null
- cuisine_types: 菜系列表（中文，如["火锅","日料","川菜"]），无则 []
- diet_labels: 饮食标签，只从以下选取：{valid_labels}，无则 []
- allergen_free_required: 需要不含的过敏原，只从以下选取：{valid_allergens}，无则 []
- price_levels: 价格档次（1=经济<30元，2=中档30-60元，3=较贵60-100元，4=高档>100元），无则 []
- min_rating: 最低评分（4.0/4.5/5.0之一），无则 null
- sort_mode: "distance"（强调距离近）/"rating"（强调口碑好）/"default"

映射示例：
- "清真" → diet_labels: ["halal"]
- "素食/纯素/vegan" → diet_labels: ["vegetarian"/"vegan"]
- "无麸质/无小麦" → allergen_free_required: ["gluten"]
- "不含海鲜" → allergen_free_required: ["shellfish","fish"]
- "便宜/实惠/经济" → price_levels: [1,2]
- "高档/精致" → price_levels: [3,4]
- "评分高/口碑好" → min_rating: 4.5, sort_mode: "rating"
- "离我最近/最近的" → sort_mode: "distance"

查询示例：
输入："三里屯500米内便宜的清真火锅"
输出：{{"q":"火锅","location":"三里屯","radius_km":0.5,"cuisine_types":["火锅"],"diet_labels":["halal"],"allergen_free_required":[],"price_levels":[1,2],"min_rating":null,"sort_mode":"default"}}

只返回 JSON，不要 markdown 代码块，不要任何额外文字。
"""


class ParsedQuery:
    __slots__ = [
        "q", "location", "radius_km", "cuisine_types",
        "diet_labels", "allergen_free_required",
        "price_levels", "min_rating", "sort_mode",
    ]

    def __init__(self, raw: dict, original_query: str = "") -> None:
        self.q: str = str(raw.get("q") or original_query or "").strip()
        self.location: Optional[str] = raw.get("location") or None
        self.radius_km: Optional[float] = _to_float(raw.get("radius_km"))
        self.cuisine_types: list[str] = _clean_list(raw.get("cuisine_types"))
        self.diet_labels: list[str] = [
            d for d in _clean_list(raw.get("diet_labels"))
            if d in _VALID_DIET_LABELS
        ]
        self.allergen_free_required: list[str] = [
            a for a in _clean_list(raw.get("allergen_free_required"))
            if a in _VALID_ALLERGENS
        ]
        self.price_levels: list[int] = [
            int(p) for p in _clean_list(raw.get("price_levels"))
            if str(p).isdigit() and 1 <= int(p) <= 4
        ]
        self.min_rating: Optional[float] = _to_float(raw.get("min_rating"))
        self.sort_mode: str = raw.get("sort_mode") or "default"
        if self.sort_mode not in ("distance", "rating", "default"):
            self.sort_mode = "default"

    def has_extracted_params(self) -> bool:
        return bool(
            self.location or self.radius_km is not None
            or self.cuisine_types or self.diet_labels
            or self.allergen_free_required or self.price_levels
            or self.min_rating is not None
            or self.sort_mode != "default"
        )

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def _clean_list(v) -> list:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x is not None]
    return []


async def parse_query(query: str, timeout: float = 8.0) -> Optional[ParsedQuery]:
    """调用 Kimi 解析自然语言 query，返回结构化参数。失败返回 None。"""
    if not _KIMI_KEY:
        logger.warning("MOONSHOT_API_KEY 未配置，跳过 LLM 解析")
        return None

    prompt = _PROMPT.format(
        query=query,
        valid_labels=", ".join(sorted(_VALID_DIET_LABELS)),
        valid_allergens=", ".join(sorted(_VALID_ALLERGENS)),
    )

    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.post(
                _KIMI_URL,
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 400,
                },
                headers={
                    "Authorization": f"Bearer {_KIMI_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            raw_text = resp.json()["choices"][0]["message"]["content"].strip()

        # 去掉可能的 markdown 代码块
        if raw_text.startswith("```"):
            raw_text = "\n".join(raw_text.split("\n")[1:]).rsplit("```", 1)[0]
        s, e = raw_text.find("{"), raw_text.rfind("}")
        if s == -1:
            logger.warning("LLM 返回非 JSON: %s", raw_text[:120])
            return None

        data = json.loads(raw_text[s : e + 1])
        return ParsedQuery(data, original_query=query)

    except Exception as exc:
        logger.warning("query_llm_parser failed: %s", exc)
        return None
