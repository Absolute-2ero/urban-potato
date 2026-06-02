from __future__ import annotations

"""Beijing search strategy — restaurant-level queries with cuisine/allergen filters."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from models.restaurant import Facets, SearchParams, SearchResponse

logger = logging.getLogger(__name__)

_INDEX = "restaurants"


def build_query(
    tokens: List[str],
    diet_labels: List[str],
    cuisine_types: Optional[List[str]],
    allergen_free_required: Optional[List[str]],
    price_levels: Optional[List[int]],
    geo: Optional[Tuple[float, float]],
    geo_radius_km: float,
    from_: int,
    size: int,
    sort_mode: str = "default",
    min_rating: Optional[float] = None,
) -> Dict[str, Any]:
    must_clauses: List[Dict] = []
    filter_clauses: List[Dict] = []

    # Always filter to BJ data
    filter_clauses.append({"term": {"city": "beijing"}})

    # ── Full-text BM25 ───────────────────────────────────────────────────────
    if tokens:
        query_text = " ".join(tokens)
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
        should_clauses += [
            {"match_phrase": {"name":    {"query": query_text, "boost": 10}}},
            {"match_phrase": {"name_en": {"query": query_text, "boost": 8}}},
        ]
        must_clauses.append({"bool": {"should": should_clauses, "minimum_should_match": 1}})

    # ── Diet label filter ────────────────────────────────────────────────────
    if diet_labels:
        filter_clauses.append({"terms": {"diet_labels": diet_labels}})

    # ── Price level filter ───────────────────────────────────────────────────
    if price_levels:
        filter_clauses.append({"terms": {"price_level": price_levels}})

    # ── Cuisine type filter ──────────────────────────────────────────────────
    if cuisine_types:
        filter_clauses.append({
            "bool": {
                "should": [{"match": {"cuisine_type": ct}} for ct in cuisine_types],
                "minimum_should_match": 1,
            }
        })

    # ── Allergen exclusion ───────────────────────────────────────────────────
    if allergen_free_required:
        filter_clauses.append({
            "bool": {"must_not": {"terms": {"allergens": allergen_free_required}}}
        })

    # ── Rating filter ────────────────────────────────────────────────────────
    if min_rating is not None:
        filter_clauses.append({"range": {"rating": {"gte": min_rating}}})

    # ── Geo filter ───────────────────────────────────────────────────────────
    if geo:
        lat, lng = geo
        filter_clauses.append({
            "geo_distance": {
                "distance": f"{geo_radius_km}km",
                "geo": {"lat": lat, "lon": lng},
            }
        })

    bool_query: Dict[str, Any] = {}
    bool_query["must"] = must_clauses if must_clauses else [{"match_all": {}}]
    if filter_clauses:
        bool_query["filter"] = filter_clauses

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


def flatten_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    source = hit.get("_source", {})
    flat = dict(source)
    flat["_score"] = hit.get("_score")
    flat["_final_score"] = hit.get("_final_score", hit.get("_score"))
    flat["_allergen_warning"] = hit.get("_allergen_warning", [])
    flat["matched_dishes"] = []
    return flat
