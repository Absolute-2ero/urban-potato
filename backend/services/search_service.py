from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from database import get_es
from ir.query_parser import QueryParser
from ir.spell_checker import check_query
from ir.synonyms import DietSynonymDict
from models.restaurant import Facets, SearchParams, SearchResponse
from services.ranking_service import RankingService

logger = logging.getLogger(__name__)

_INDEX = "restaurants"

# 模块级单例（由 main.py lifespan 初始化）
_synonyms: Optional[DietSynonymDict] = None
_parser: Optional[QueryParser] = None
_ranker: Optional[RankingService] = None


def init_search_components() -> None:
    global _synonyms, _parser, _ranker
    _synonyms = DietSynonymDict.load()
    _parser = QueryParser(_synonyms)
    _ranker = RankingService()
    logger.info("Search components initialized")


# ── ES 查询构建 ───────────────────────────────────────────────────────────────

def _build_es_query(
    tokens: List[str],
    diet_labels: List[str],
    price_levels: Optional[List[int]],
    geo: Optional[Tuple[float, float]],
    geo_radius_km: float,
    from_: int,
    size: int,
) -> Dict[str, Any]:
    must_clauses: List[Dict] = []
    filter_clauses: List[Dict] = []

    # ── 全文 BM25 ────────────────────────────────────────────────────────────
    # 每个 token（含同义词）独立构成一个 should 子句，最少匹配 1 个即可命中
    if tokens:
        should_clauses = [
            {
                "multi_match": {
                    "query": tok,
                    "fields": ["name^3", "description^2", "cuisine_type", "address"],
                    "type": "best_fields",
                }
            }
            for tok in tokens
        ]
        must_clauses.append(
            {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1,
                }
            }
        )

    # ── 饮食标签过滤 ─────────────────────────────────────────────────────────
    if diet_labels:
        filter_clauses.append({"terms": {"diet_labels": diet_labels}})

    # ── 价格档次过滤 ─────────────────────────────────────────────────────────
    if price_levels:
        filter_clauses.append({"terms": {"price_level": price_levels}})

    # ── 地理位置过滤 ─────────────────────────────────────────────────────────
    if geo:
        lat, lng = geo
        filter_clauses.append(
            {
                "geo_distance": {
                    "distance": f"{geo_radius_km}km",
                    "geo": {"lat": lat, "lon": lng},
                }
            }
        )

    bool_query: Dict[str, Any] = {}
    if must_clauses:
        bool_query["must"] = must_clauses
    else:
        bool_query["must"] = [{"match_all": {}}]
    if filter_clauses:
        bool_query["filter"] = filter_clauses

    # ── Aggregations (Facets) ────────────────────────────────────────────────
    aggs = {
        "diet_labels": {"terms": {"field": "diet_labels", "size": 20}},
        "price_level": {"terms": {"field": "price_level", "size": 5}},
        "cuisine_type": {"terms": {"field": "cuisine_type.keyword", "size": 20}},
    }

    return {
        "from": from_,
        "size": size,
        "query": {"bool": bool_query},
        "aggs": aggs,
        "_source": True,
    }


def _parse_facets(aggs: Dict[str, Any]) -> Facets:
    def _buckets(key: str) -> Dict[str, int]:
        return {
            b["key"]: b["doc_count"]
            for b in aggs.get(key, {}).get("buckets", [])
        }

    return Facets(
        diet_labels=_buckets("diet_labels"),
        price_level={str(k): v for k, v in _buckets("price_level").items()},
        cuisine_type=_buckets("cuisine_type"),
    )


# ── 主搜索入口 ────────────────────────────────────────────────────────────────

async def search(
    params: SearchParams,
    user_allergens: Optional[List[str]] = None,
    user_geo: Optional[Tuple[float, float]] = None,
) -> SearchResponse:
    if _parser is None or _ranker is None:
        raise RuntimeError("Search components not initialized")

    user_allergens = user_allergens or []

    # ── 1. 拼写纠错 ───────────────────────────────────────────────────────────
    spell_suggestion: Optional[str] = None
    query_text = params.q or ""
    if query_text:
        corrected = check_query(query_text)
        if corrected and corrected.lower() != query_text.lower():
            spell_suggestion = corrected

    # ── 2. 查询解析 + 同义词扩展 ──────────────────────────────────────────────
    parsed = _parser.parse(query_text, sort_mode=params.sort_mode)
    search_tokens = parsed.expanded_tokens
    detected_diet_labels = parsed.detected_diet_labels

    # 用户显式指定的 diet_labels 优先，再补充从查询检测到的
    active_diet_labels = list(
        dict.fromkeys((params.diet_labels or []) + detected_diet_labels)
    )

    # ── 3. 地理位置 ───────────────────────────────────────────────────────────
    geo: Optional[Tuple[float, float]] = None
    if params.lat is not None and params.lng is not None:
        geo = (params.lat, params.lng)

    # ── 4. 构建并执行 ES 查询 ─────────────────────────────────────────────────
    es_body = _build_es_query(
        tokens=search_tokens,
        diet_labels=active_diet_labels,
        price_levels=params.price_levels,
        geo=geo,
        geo_radius_km=params.radius_km or 5.0,
        from_=params.offset,
        size=params.limit,
    )

    es = get_es()
    try:
        resp = await es.search(index=_INDEX, body=es_body)
    except Exception as exc:
        logger.error("ES search error: %s", exc)
        raise

    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]["value"]
    aggs = resp.get("aggregations", {})

    # ── 5. 实时爬虫触发（ES 命中不足时后台补充）──────────────────────────────
    # 仅在第一页且有搜索词时触发
    if params.offset == 0 and query_text:
        try:
            from crawler.realtime_crawler import maybe_trigger
            lat = params.lat
            lng = params.lng
            await maybe_trigger(
                query=query_text,
                es_hit_count=total,
                lat=lat,
                lng=lng,
            )
        except Exception as exc:
            logger.warning("Realtime crawl trigger failed (non-fatal): %s", exc)

    # ── 6. 重排序 ─────────────────────────────────────────────────────────────
    reranked = _ranker.rerank(
        hits=hits,
        query_diet_labels=active_diet_labels,
        user_allergens=user_allergens,
        user_geo=user_geo or geo,
        sort_mode=params.sort_mode,
    )

    # ── 7. 展平 _source 字段 ────────────────────────────────────────────────────
    flat_hits: List[Dict[str, Any]] = []
    for hit in reranked:
        source = hit.get("_source", {})
        flat = dict(source)
        flat["_score"] = hit.get("_score")
        flat["_final_score"] = hit.get("_final_score", hit.get("_score"))
        flat["_allergen_warning"] = hit.get("_allergen_warning", [])
        flat_hits.append(flat)

    # ── 8. 组装响应 ───────────────────────────────────────────────────────────
    facets = _parse_facets(aggs)

    return SearchResponse(
        total=total,
        hits=flat_hits,
        facets=facets,
        spell_suggestion=spell_suggestion,
        detected_diet_labels=detected_diet_labels,
        query_tokens=search_tokens,
        sort_mode=params.sort_mode,
        offset=params.offset,
        limit=params.limit,
        crawl_triggered=(total < 5 and params.offset == 0 and bool(query_text)),
    )


# ── 自动补全 ──────────────────────────────────────────────────────────────────

async def autocomplete(prefix: str, size: int = 8) -> List[str]:
    """基于 ES completion suggester 返回餐厅名称候选。"""
    es = get_es()
    try:
        resp = await es.search(
            index=_INDEX,
            body={
                "suggest": {
                    "name_suggest": {
                        "prefix": prefix,
                        "completion": {
                            "field": "name_suggest",
                            "size": size,
                            "skip_duplicates": True,
                        },
                    }
                },
                "_source": False,
            },
        )
        options = resp.get("suggest", {}).get("name_suggest", [{}])[0].get("options", [])
        return [o["text"] for o in options]
    except Exception as exc:
        logger.warning("Autocomplete error: %s", exc)
        return []
