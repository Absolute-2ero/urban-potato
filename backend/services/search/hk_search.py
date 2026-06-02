from __future__ import annotations

"""Hong Kong search strategy — dish-level nested queries with nutritional filters."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from models.restaurant import Facets, SearchParams, SearchResponse

logger = logging.getLogger(__name__)

_INDEX = "restaurants"


def build_query(
    tokens: List[str],
    diet_labels: List[str],
    price_levels: Optional[List[int]],
    geo: Optional[Tuple[float, float]],
    geo_radius_km: float,
    from_: int,
    size: int,
    sort_mode: str = "default",
    min_rating: Optional[float] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_calories: Optional[int] = None,
    max_calories: Optional[int] = None,
    min_protein_g: Optional[float] = None,
) -> Dict[str, Any]:
    filter_clauses: List[Dict] = []
    query_text = " ".join(tokens)

    # Always filter to HK data
    filter_clauses.append({"term": {"city": "hongkong"}})

    # ── Nested dish query (text + diet labels) ───────────────────────────────
    nested_dish_conditions: List[Dict] = []
    if query_text:
        nested_dish_conditions.append({
            "bool": {
                "should": [
                    {"match": {"menu_items.name_en": {"query": query_text, "minimum_should_match": "60%"}}},
                    {"match": {"menu_items.name":    {"query": query_text, "minimum_should_match": "60%"}}},
                ],
                "minimum_should_match": 1,
            }
        })
    if diet_labels:
        nested_dish_conditions.append({"terms": {"menu_items.diet_labels": diet_labels}})

    nested_inner_hits: Dict[str, Any] = {
        "size": 20,
        "_source": True,
        "sort": [{"menu_items.price": {"order": "asc", "missing": "_last"}}],
    }

    nested_dish_clause: Optional[Dict] = None
    if nested_dish_conditions:
        nested_dish_clause = {
            "nested": {
                "path": "menu_items",
                "query": (
                    {"bool": {"must": nested_dish_conditions}}
                    if len(nested_dish_conditions) > 1
                    else nested_dish_conditions[0]
                ),
                "inner_hits": nested_inner_hits,
                "score_mode": "max",
            }
        }

    # ── Top-level query ──────────────────────────────────────────────────────
    if query_text:
        restaurant_name_clause: Dict = {
            "bool": {
                "should": [
                    {"multi_match": {
                        "query": query_text,
                        "fields": ["name^6", "name_en^5", "cuisine_type^2", "address"],
                        "type": "best_fields",
                        "minimum_should_match": "60%",
                    }},
                    {"match_phrase": {"name":    {"query": query_text, "boost": 20}}},
                    {"match_phrase": {"name_en": {"query": query_text, "boost": 16}}},
                ]
            }
        }
        should_clauses = [restaurant_name_clause]
        if nested_dish_clause:
            should_clauses.append(nested_dish_clause)
        top_query: Dict = {"bool": {"should": should_clauses, "minimum_should_match": 1}}
    elif nested_dish_clause:
        top_query = nested_dish_clause
    else:
        top_query = {"match_all": {}}

    # ── Filters ──────────────────────────────────────────────────────────────
    if price_levels:
        filter_clauses.append({"terms": {"price_level": price_levels}})
    if geo:
        lat, lng = geo
        filter_clauses.append({
            "geo_distance": {
                "distance": f"{geo_radius_km}km",
                "geo": {"lat": lat, "lon": lng},
            }
        })
    if min_rating is not None:
        filter_clauses.append({"range": {"rating": {"gte": min_rating}}})
    if min_price is not None or max_price is not None:
        price_range: Dict = {}
        if min_price is not None:
            price_range["gte"] = min_price
        if max_price is not None:
            price_range["lte"] = max_price
        filter_clauses.append({
            "nested": {
                "path": "menu_items",
                "query": {"range": {"menu_items.price": price_range}},
            }
        })
    if min_calories is not None or max_calories is not None:
        cal_range: Dict = {}
        if min_calories is not None:
            cal_range["gte"] = min_calories
        if max_calories is not None:
            cal_range["lte"] = max_calories
        filter_clauses.append({
            "nested": {
                "path": "menu_items",
                "query": {"range": {"menu_items.calories": cal_range}},
            }
        })
    if min_protein_g is not None:
        filter_clauses.append({
            "nested": {
                "path": "menu_items",
                "query": {"range": {"menu_items.protein_g": {"gte": min_protein_g}}},
            }
        })

    final_query = (
        {"bool": {"must": top_query, "filter": filter_clauses}}
        if filter_clauses
        else top_query
    )

    # ── Sort ─────────────────────────────────────────────────────────────────
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
        "query": final_query,
        "sort": sort,
        "aggs": aggs,
        "_source": True,
    }


def flatten_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    import re as _re
    src = dict(hit.get("_source", {}))
    for field in ("diet_labels", "allergens", "allergen_free", "images"):
        val = src.get(field)
        if isinstance(val, str):
            src[field] = [v for v in val.split() if v] if val.strip() else []
        elif not isinstance(val, list):
            src[field] = []
    if not isinstance(src.get("menu_items"), list):
        src["menu_items"] = []
    if not src.get("price_level"):
        pr = src.get("price_range", "")
        if pr:
            nums = [int(n) for n in _re.findall(r'\d+', pr)]
            if nums:
                avg = sum(nums) / len(nums)
                src["price_level"] = 1 if avg < 100 else 2 if avg < 200 else 3 if avg < 400 else 4
        if not src.get("price_level"):
            prices = [i["price"] for i in src.get("menu_items", []) if isinstance(i, dict) and i.get("price")]
            if prices:
                avg = sum(prices) / len(prices)
                src["price_level"] = 1 if avg < 50 else 2 if avg < 100 else 3 if avg < 200 else 4
    # Extract matched dishes from inner_hits
    matched_dishes: List[Dict] = []
    inner = hit.get("inner_hits", {})
    if "menu_items" in inner:
        for ih in inner["menu_items"]["hits"]["hits"]:
            dish = dict(ih.get("_source", {}))
            dl = dish.get("diet_labels")
            if isinstance(dl, str):
                dish["diet_labels"] = [v for v in dl.split() if v] if dl.strip() else []
            elif not isinstance(dl, list):
                dish["diet_labels"] = []
            matched_dishes.append(dish)
    src["matched_dishes"] = matched_dishes
    src["_final_score"] = hit.get("_final_score")
    src["_distance_m"] = hit.get("_distance_m")
    src["_allergen_warning"] = hit.get("_allergen_warning") or []
    return src
