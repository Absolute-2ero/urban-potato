from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from database import get_es
from ir.query_parser import QueryParser
from ir.spell_checker import check_query
from ir.synonyms import DietSynonymDict
from models.restaurant import Facets, SearchParams, SearchResponse
from services.ranking_service import RankingService
from services.search import bj_search, hk_search

logger = logging.getLogger(__name__)

_INDEX = "restaurants"

_synonyms: Optional[DietSynonymDict] = None
_parser: Optional[QueryParser] = None
_ranker: Optional[RankingService] = None


def init_search_components() -> None:
    global _synonyms, _parser, _ranker
    _synonyms = DietSynonymDict.load()
    _parser = QueryParser(_synonyms)
    _ranker = RankingService()
    logger.info("Search components initialized")


def _parse_facets(aggs: Dict[str, Any]) -> Facets:
    def _buckets(key: str) -> Dict[str, int]:
        return {b["key"]: b["doc_count"] for b in aggs.get(key, {}).get("buckets", [])}
    return Facets(
        diet_labels=_buckets("diet_labels"),
        price_level={str(k): v for k, v in _buckets("price_level").items()},
        cuisine_type=_buckets("cuisine_type"),
    )


async def search(
    params: SearchParams,
    user_allergens: Optional[List[str]] = None,
    user_geo: Optional[Tuple[float, float]] = None,
) -> SearchResponse:
    if _parser is None or _ranker is None:
        raise RuntimeError("Search components not initialized")

    user_allergens = user_allergens or []

    # ── 1. Spell correction ──────────────────────────────────────────────────
    spell_suggestion: Optional[str] = None
    query_text = params.q or ""
    if query_text:
        corrected = check_query(query_text)
        if corrected and corrected.lower() != query_text.lower():
            spell_suggestion = corrected

    # ── 2. Query parsing + synonym expansion ────────────────────────────────
    parsed = _parser.parse(query_text, sort_mode=params.sort_mode)
    detected_diet_labels = parsed.detected_diet_labels
    active_diet_labels = list(dict.fromkeys((params.diet_labels or []) + detected_diet_labels))

    # ── 3. Geo ───────────────────────────────────────────────────────────────
    geo: Optional[Tuple[float, float]] = None
    if params.lat is not None and params.lng is not None:
        geo = (params.lat, params.lng)

    # ── 4. Build ES query — city-specific strategy ───────────────────────────
    city = (params.city or "hongkong").lower()

    if city == "beijing":
        search_tokens = parsed.expanded_tokens if hasattr(parsed, "expanded_tokens") else parsed.free_text_tokens
        es_body = bj_search.build_query(
            tokens=search_tokens,
            diet_labels=active_diet_labels,
            cuisine_types=params.cuisine_types or [],
            allergen_free_required=params.allergen_free_required or [],
            price_levels=params.price_levels,
            geo=geo,
            geo_radius_km=params.radius_km or 5.0,
            from_=params.offset,
            size=params.limit,
            sort_mode=params.sort_mode,
            min_rating=params.min_rating,
        )
        flatten_hit = bj_search.flatten_hit
    else:
        # HK (default) — dish-level with nutritional constraints
        search_tokens = parsed.free_text_tokens
        c = getattr(parsed, "extracted_constraints", None)
        min_calories  = params.min_calories  if params.min_calories  is not None else (c.min_calories  if c else None)
        max_calories  = params.max_calories  if params.max_calories  is not None else (c.max_calories  if c else None)
        min_protein_g = params.min_protein_g if params.min_protein_g is not None else (c.min_protein_g if c else None)
        max_price     = params.max_price     if params.max_price     is not None else (c.max_price_rmb if c else None)

        # Landmark geo fallback (HK only)
        if geo is None and getattr(parsed, "landmark_geo", None) is not None:
            geo = parsed.landmark_geo
            logger.debug("Using landmark geo for '%s': %s", parsed.landmark_name, geo)

        es_body = hk_search.build_query(
            tokens=search_tokens,
            diet_labels=active_diet_labels,
            price_levels=params.price_levels,
            geo=geo,
            geo_radius_km=params.radius_km or 5.0,
            from_=params.offset,
            size=params.limit,
            sort_mode=params.sort_mode,
            min_rating=params.min_rating,
            min_price=params.min_price,
            max_price=max_price,
            min_calories=min_calories,
            max_calories=max_calories,
            min_protein_g=min_protein_g,
        )
        flatten_hit = hk_search.flatten_hit

    # ── 5. Execute ES query ───────────────────────────────────────────────────
    es = get_es()
    try:
        resp = await es.search(index=_INDEX, body=es_body)
    except Exception as exc:
        logger.error("ES search error: %s", exc)
        raise

    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]["value"]
    aggs = resp.get("aggregations", {})

    # ── 6. Rerank ─────────────────────────────────────────────────────────────
    reranked = _ranker.rerank(
        hits=hits,
        query_diet_labels=active_diet_labels,
        user_allergens=user_allergens,
        user_geo=user_geo or geo,
        sort_mode=params.sort_mode,
        query_text=query_text,
    )

    # ── 8. Flatten and respond ────────────────────────────────────────────────
    flattened = [flatten_hit(h) for h in reranked]
    facets = _parse_facets(aggs)

    return SearchResponse(
        total=total,
        hits=flattened,
        facets=facets,
        spell_suggestion=spell_suggestion,
        detected_diet_labels=detected_diet_labels,
        detected_cuisine_type=getattr(parsed, "detected_cuisine_type", None),
        landmark_name=getattr(parsed, "landmark_name", None),
        query_tokens=search_tokens,
        sort_mode=params.sort_mode,
        offset=params.offset,
        limit=params.limit,
        crawl_triggered=False,
    )


async def autocomplete(prefix: str, size: int = 8, city: Optional[str] = None) -> List[str]:
    es = get_es()
    filter_clauses: List[Dict] = []
    if city:
        filter_clauses.append({"term": {"city": city.lower()}})
    try:
        body: Dict[str, Any] = {
            "size": size,
            "query": {
                "bool": {
                    "must": {"match_phrase_prefix": {"name": {"query": prefix, "max_expansions": 20}}},
                    **({"filter": filter_clauses} if filter_clauses else {}),
                }
            },
            "_source": ["name"],
        }
        resp = await es.search(index=_INDEX, body=body)
        seen: set = set()
        results: List[str] = []
        for hit in resp["hits"]["hits"]:
            name = hit["_source"].get("name", "")
            if name and name not in seen:
                seen.add(name)
                results.append(name)
        return results
    except Exception as exc:
        logger.warning("Autocomplete error: %s", exc)
        return []
