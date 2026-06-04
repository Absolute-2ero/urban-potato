from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from database import get_es
from ir.query_parser import QueryParser
from ir.spell_checker import check_query
from ir.synonyms import DietSynonymDict
from models.restaurant import Facets, SearchParams, SearchResponse
from services.embedding_service import EmbeddingService, get_embedding_service
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


def _inject_diversity(
    hits: List[Dict[str, Any]],
    user_diet_labels: List[str],
    inject_ratio: float = 0.2,
    concentration_threshold: float = 0.70,
) -> List[Dict[str, Any]]:
    """
    当结果集中某个 diet_label 占比 > threshold 时，
    把最后 inject_ratio 的位置替换为 diet_label 不同的候选，
    让推荐结果更多样。
    """
    if len(hits) < 5:
        return hits

    # 统计前10条里 diet_label 的分布
    window = hits[:10]
    label_counts: Dict[str, int] = {}
    for h in window:
        src = h.get("_source", {})
        for lbl in (src.get("diet_labels") or []):
            label_counts[lbl] = label_counts.get(lbl, 0) + 1

    if not label_counts:
        return hits

    dominant_label, dominant_count = max(label_counts.items(), key=lambda x: x[1])
    if dominant_count / len(window) <= concentration_threshold:
        return hits  # 足够多样，不注入

    # 找出结果里 diet_label 不含 dominant_label 的候选
    diverse = [h for h in hits if dominant_label not in (h.get("_source", {}).get("diet_labels") or [])]
    if not diverse:
        return hits

    n_inject = max(1, int(len(hits) * inject_ratio))
    n_inject = min(n_inject, len(diverse), 3)

    # 把 dominant 结果和 diverse 结果交错插入
    keep = [h for h in hits if dominant_label in (h.get("_source", {}).get("diet_labels") or [])]
    result: List[Dict[str, Any]] = []
    di = 0
    ki = 0
    for i in range(len(hits)):
        # 每隔 ~4 条插一条多样结果
        if di < n_inject and ki > 0 and ki % 4 == 0:
            result.append(diverse[di])
            di += 1
        elif ki < len(keep):
            result.append(keep[ki])
            ki += 1
        elif di < len(diverse):
            result.append(diverse[di])
            di += 1

    return result[:len(hits)]


async def search(
    params: SearchParams,
    user_allergens: Optional[List[str]] = None,
    user_geo: Optional[Tuple[float, float]] = None,
    user_id: Optional[str] = None,
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

    city = (params.city or "hongkong").lower()

    # Landmark geo fallback — applies to all cities
    if geo is None and getattr(parsed, "landmark_geo", None) is not None:
        geo = parsed.landmark_geo
        logger.debug("Using landmark geo for '%s': %s", parsed.landmark_name, geo)

    # ── 4. Embed query + fetch user pref vector (parallel) ──────────────────
    emb_svc = get_embedding_service()
    query_embedding: Optional[List[float]] = None
    user_pref_vector: Optional[List[float]] = None

    semantic_mode = getattr(params, "semantic", False)

    if emb_svc.enabled and query_text:
        embed_text = query_text
        if active_diet_labels:
            embed_text += " " + " ".join(active_diet_labels)

        async def _fetch_query_embedding() -> Optional[List[float]]:
            try:
                return await emb_svc.embed(embed_text, timeout=3.0)
            except Exception as exc:
                logger.debug("Query embedding failed: %s", exc)
                return None

        async def _fetch_user_pref() -> Optional[List[float]]:
            if not user_id:
                return None
            try:
                from services.personalization_service import get_user_preference_vector
                return await get_user_preference_vector(user_id)
            except Exception as exc:
                logger.debug("User pref vector failed: %s", exc)
                return None

        query_embedding, user_pref_vector = await asyncio.gather(
            _fetch_query_embedding(),
            _fetch_user_pref(),
        )

    # ── 5. Build ES query — city-specific strategy ───────────────────────────
    # Semantic mode: skip BM25 text, use kNN only (tokens=[])
    if city == "beijing":
        search_tokens = (
            []
            if semantic_mode
            else (parsed.expanded_tokens if hasattr(parsed, "expanded_tokens") else parsed.free_text_tokens)
        )
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
            query_embedding=query_embedding,
            semantic_only=semantic_mode,
        )
        flatten_hit = bj_search.flatten_hit
    else:
        search_tokens = [] if semantic_mode else parsed.free_text_tokens
        c = getattr(parsed, "extracted_constraints", None)
        min_calories  = params.min_calories  if params.min_calories  is not None else (c.min_calories  if c else None)
        max_calories  = params.max_calories  if params.max_calories  is not None else (c.max_calories  if c else None)
        min_protein_g = params.min_protein_g if params.min_protein_g is not None else (c.min_protein_g if c else None)
        max_price     = params.max_price     if params.max_price     is not None else (c.max_price_rmb if c else None)

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
            query_embedding=query_embedding,
            semantic_only=semantic_mode,
        )
        flatten_hit = hk_search.flatten_hit

    # ── 6. Execute ES query ───────────────────────────────────────────────────
    es = get_es()
    try:
        resp = await es.search(index=_INDEX, body=es_body)
    except Exception as exc:
        logger.error("ES search error: %s", exc)
        raise

    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]["value"]
    aggs = resp.get("aggregations", {})

    # ── 7. Rerank (BM25 + diet + geo + personalization) ──────────────────────
    reranked = _ranker.rerank(
        hits=hits,
        query_diet_labels=active_diet_labels,
        user_allergens=user_allergens,
        user_geo=user_geo or geo,
        sort_mode=params.sort_mode,
        query_text=query_text,
        user_pref_vector=user_pref_vector,
    )

    # ── 8. Diversity injection ────────────────────────────────────────────────
    reranked = _inject_diversity(reranked, active_diet_labels)

    # ── 9. Flatten and respond ────────────────────────────────────────────────
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
