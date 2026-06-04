from __future__ import annotations

"""Beijing search strategy — restaurant-level queries, hybrid BM25 + kNN."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from models.restaurant import Facets, SearchParams, SearchResponse

logger = logging.getLogger(__name__)

_INDEX = "restaurants"


def _bm25_body(
    tokens: List[str],
    diet_labels: List[str],
    cuisine_types: Optional[List[str]],
    allergen_free_required: Optional[List[str]],
    price_levels: Optional[List[int]],
    geo: Optional[Tuple[float, float]],
    geo_radius_km: float,
    from_: int,
    size: int,
    sort_mode: str,
    min_rating: Optional[float],
) -> Dict[str, Any]:
    must_clauses: List[Dict] = []
    filter_clauses: List[Dict] = []

    filter_clauses.append({
        "bool": {
            "should": [
                {"term":  {"city": "beijing"}},
                {"bool": {"must_not": {"exists": {"field": "city"}}}},
            ],
            "minimum_should_match": 1,
        }
    })

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

    if diet_labels:
        filter_clauses.append({"terms": {"diet_labels": diet_labels}})
    if price_levels:
        filter_clauses.append({"terms": {"price_level": price_levels}})
    if cuisine_types:
        filter_clauses.append({
            "bool": {
                "should": [{"match": {"cuisine_type": ct}} for ct in cuisine_types],
                "minimum_should_match": 1,
            }
        })
    if allergen_free_required:
        filter_clauses.append({
            "bool": {"must_not": {"terms": {"allergens": allergen_free_required}}}
        })
    if min_rating is not None:
        filter_clauses.append({"range": {"rating": {"gte": min_rating}}})
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

    if sort_mode == "price_asc":
        sort: List = [{"price_level": {"order": "asc", "missing": "_last"}}, "_score"]
    elif sort_mode == "rating_first":
        sort = [{"rating": {"order": "desc", "missing": "_last"}}, "_score"]
    elif sort_mode == "distance_first" and geo:
        sort = [{"_geo_distance": {"geo": {"lat": geo[0], "lon": geo[1]}, "order": "asc"}}, "_score"]
    else:
        sort = ["_score"]

    aggs = {
        "diet_labels": {"terms": {"field": "diet_labels", "size": 20}},
        "price_level": {"terms": {"field": "price_level", "size": 5}},
        "cuisine_type": {"terms": {"field": "cuisine_type.keyword", "size": 20}},
    }

    return {
        "from": from_,
        "size": size,
        "query": {"bool": bool_query},
        "sort": sort,
        "aggs": aggs,
        "_source": True,
    }


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
    query_embedding: Optional[List[float]] = None,
    semantic_only: bool = False,
) -> Dict[str, Any]:
    body = _bm25_body(
        tokens, diet_labels, cuisine_types, allergen_free_required,
        price_levels, geo, geo_radius_km, from_, size, sort_mode, min_rating,
    )

    if query_embedding:
        knn_filter: List[Dict] = body.get("query", {}).get("bool", {}).get("filter", [])

        if semantic_only:
            # Pure kNN: replace BM25 text query with filter-only match_all
            body["query"] = {"bool": {"filter": knn_filter}} if knn_filter else {"match_all": {}}
            body.pop("sort", None)  # let kNN score drive ordering
            body["knn"] = {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": max(size * 5, 100),
                "num_candidates": max(size * 20, 500),
                **({"filter": knn_filter} if knn_filter else {}),
            }
        elif sort_mode in ("default", ""):
            # Hybrid: kNN + BM25 scores summed, only for default sort
            body["knn"] = {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": max(size * 3, 60),
                "num_candidates": max(size * 10, 200),
                **({"filter": knn_filter} if knn_filter else {}),
            }

    return body


def flatten_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    source = hit.get("_source", {})
    flat = dict(source)
    flat["_score"] = hit.get("_score")
    flat["_final_score"] = hit.get("_final_score", hit.get("_score"))
    flat["_allergen_warning"] = hit.get("_allergen_warning", [])
    flat["matched_dishes"] = []
    return flat
