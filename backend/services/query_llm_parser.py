"""
LLM 查询理解：用 Kimi 把自然语言 query 解析为结构化搜索参数。
坐标解析：LLM 提取地名，高德 geocoding API 转换为精确坐标。
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional, Tuple

import httpx

from config import cfg

logger = logging.getLogger(__name__)

_KIMI_KEY = os.environ.get("MOONSHOT_API_KEY") or cfg.moonshot_api_key
_KIMI_URL = "https://api.moonshot.cn/v1/chat/completions"

_GAODE_KEY = cfg.gaode_api_key
_GAODE_GEO_URL   = "https://restapi.amap.com/v3/geocode/geo"
_GAODE_POI_URL   = "https://restapi.amap.com/v3/place/text"

_CITY_CN = {
    "beijing":  "北京",
    "hongkong": "香港",
    "hk":       "香港",
    "hong_kong": "香港",
}

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

请提取以下字段（无法确定的填 null 或 []）。无论用户用何种语言输入，所有字段均用中文输出（diet_labels / allergen_free_required 除外，保持英文）：
- q: 核心搜索词（食物/餐厅名称），去掉位置、距离、价格、饮食偏好等修饰词；若为英文则翻译成中文（"hotpot"→"火锅"，"Japanese food"→"日料"，"restaurant"→"餐厅"）
- location: 用户提到的具体位置名称（地标、街道、商圈、地铁站等，如"北宫门"、"三里屯"、"海淀区"），无则 null
- radius_km: 距离半径（数字）
  * 明确距离："500米"→0.5，"1公里"→1，"2公里"→2
  * 只说"附近"/"周边"/"旁边"→ 5（不强调距离时给宽松范围，结合 sort_mode=distance_first 展示最近的）
  * 没有任何位置/距离含义 → null
- cuisine_types: 菜系列表，统一用中文（"hotpot"→"火锅"，"Japanese"→"日料"，"Korean"→"韩餐"，"Thai"→"泰餐"，"Western"→"西餐"），无则 []
- diet_labels: 饮食标签，只从以下选取：{valid_labels}，无则 []
- allergen_free_required: 需要不含的过敏原，只从以下选取：{valid_allergens}，无则 []
- price_levels: 价格档次（1=经济，2=中档，3=较贵，4=高档），无则 []
- min_rating: 最低评分（4.0/4.5/5.0之一），无则 null
- sort_mode: "distance_first"（强调距离近/附近/周边）/"rating_first"（强调口碑好）/"default"

映射示例：
- "清真" → diet_labels: ["halal"]
- "素食/纯素/vegan" → diet_labels: ["vegetarian"/"vegan"]
- "无麸质/无小麦" → allergen_free_required: ["gluten"]
- "不含海鲜" → allergen_free_required: ["shellfish","fish"]
- "便宜/实惠/经济" → price_levels: [1,2]
- "高档/精致" → price_levels: [3,4]
- "评分高/口碑好" → min_rating: 4.5, sort_mode: "rating_first"
- "附近/周边/旁边" → radius_km: 5, sort_mode: "distance_first"
- "500米内" → radius_km: 0.5, sort_mode: "distance_first"

查询示例：
输入："北宫门附近便宜的清真火锅"
输出：{{"q":"火锅","location":"北宫门","radius_km":5,"cuisine_types":["火锅"],"diet_labels":["halal"],"allergen_free_required":[],"price_levels":[1,2],"min_rating":null,"sort_mode":"distance_first"}}

输入："cheap hotpot near Wudaokou"
输出：{{"q":"火锅","location":"五道口","radius_km":5,"cuisine_types":["火锅"],"diet_labels":[],"allergen_free_required":[],"price_levels":[1,2],"min_rating":null,"sort_mode":"distance_first"}}

输入："vegan Japanese restaurant in Sanlitun within 500m"
输出：{{"q":"日料","location":"三里屯","radius_km":0.5,"cuisine_types":["日料"],"diet_labels":["vegan"],"allergen_free_required":[],"price_levels":[],"min_rating":null,"sort_mode":"distance_first"}}

只返回 JSON，不要 markdown 代码块，不要任何额外文字。
"""


class ParsedQuery:
    __slots__ = [
        "q", "location", "location_lat", "location_lng", "radius_km",
        "cuisine_types", "diet_labels", "allergen_free_required",
        "price_levels", "min_rating", "sort_mode",
    ]

    def __init__(self, raw: dict, original_query: str = "") -> None:
        self.q: str = str(raw.get("q") or original_query or "").strip()
        self.location: Optional[str] = raw.get("location") or None
        self.location_lat: Optional[float] = None
        self.location_lng: Optional[float] = None
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
        raw_sort = raw.get("sort_mode") or "default"
        _sort_map = {"distance": "distance_first", "rating": "rating_first"}
        self.sort_mode: str = _sort_map.get(raw_sort, raw_sort)
        if self.sort_mode not in ("distance_first", "rating_first", "price_asc", "default"):
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


async def _geocode_location(
    location: str,
    city_cn: str,
    client: httpx.AsyncClient,
    timeout: float = 4.0,
) -> Optional[Tuple[float, float]]:
    """高德 geocoding：地名 → (lat, lng) GCJ-02 坐标，失败返回 None。
    先试结构化地址接口，再试 POI 关键词搜索。
    """
    if not _GAODE_KEY:
        return None

    # 1. 结构化地址 geocoding
    try:
        r = await client.get(
            _GAODE_GEO_URL,
            params={"address": location, "city": city_cn, "key": _GAODE_KEY},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") == "1" and data.get("geocodes"):
            loc_str = data["geocodes"][0].get("location", "")
            if loc_str and "," in loc_str:
                lng_s, lat_s = loc_str.split(",", 1)
                return float(lat_s), float(lng_s)
    except Exception as exc:
        logger.debug("Gaode geocode failed for '%s': %s", location, exc)

    # 2. POI 关键词搜索 fallback
    try:
        r = await client.get(
            _GAODE_POI_URL,
            params={
                "keywords": location,
                "city": city_cn,
                "citylimit": "true",
                "offset": 1,
                "key": _GAODE_KEY,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        pois = data.get("pois") or []
        if pois:
            loc_str = pois[0].get("location", "")
            if loc_str and "," in loc_str:
                lng_s, lat_s = loc_str.split(",", 1)
                return float(lat_s), float(lng_s)
    except Exception as exc:
        logger.debug("Gaode POI search failed for '%s': %s", location, exc)

    return None


async def parse_query(query: str, city: str = "beijing", timeout: float = 8.0) -> Optional[ParsedQuery]:
    """调用 Kimi 解析自然语言 query，并用高德 geocoding 把地名转为坐标。失败返回 None。"""
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
                    "max_tokens": 300,
                },
                headers={
                    "Authorization": f"Bearer {_KIMI_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            raw_text = resp.json()["choices"][0]["message"]["content"].strip()

        if raw_text.startswith("```"):
            raw_text = "\n".join(raw_text.split("\n")[1:]).rsplit("```", 1)[0]
        s, e = raw_text.find("{"), raw_text.rfind("}")
        if s == -1:
            logger.warning("LLM 返回非 JSON: %s", raw_text[:120])
            return None

        data = json.loads(raw_text[s : e + 1])
        parsed = ParsedQuery(data, original_query=query)

        # 高德 geocoding：把 LLM 提取的地名转换为精确坐标
        if parsed.location:
            city_cn = _CITY_CN.get(city.lower(), "北京")
            async with httpx.AsyncClient(trust_env=False) as client:
                coords = await _geocode_location(parsed.location, city_cn, client)
            if coords:
                parsed.location_lat, parsed.location_lng = coords
                logger.debug(
                    "Geocoded '%s' → lat=%.4f lng=%.4f",
                    parsed.location, parsed.location_lat, parsed.location_lng,
                )
            else:
                logger.info("Gaode geocoding 未找到 '%s'，坐标留空", parsed.location)

        return parsed

    except Exception as exc:
        logger.warning("query_llm_parser failed: %s", exc)
        return None
