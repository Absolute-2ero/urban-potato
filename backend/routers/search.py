from __future__ import annotations

from typing import List, Optional, Tuple

from fastapi import APIRouter, Query, Request

from models.restaurant import SearchParams, SearchResponse
from services import search_service
from services import diet_service

router = APIRouter(prefix="/api/search", tags=["search"])


async def _get_user_context(request: Request) -> tuple:
    """从 session 获取用户过敏原和位置偏好。"""
    user_allergens: List[str] = []
    uid = request.session.get("user_id")
    if uid:
        profile = await diet_service.get_diet_profile(uid)
        if profile:
            user_allergens = profile.allergens
    return uid, user_allergens


@router.get("", response_model=SearchResponse)
async def search(
    request: Request,
    city: str = Query("hongkong", description="城市 ID: hongkong | beijing"),
    q: Optional[str] = Query(None, max_length=500, description="搜索关键词"),
    diet_labels: Optional[List[str]] = Query(None, description="饮食标签过滤"),
    cuisine_types: Optional[List[str]] = Query(None, description="菜系过滤（北京）"),
    allergen_free_required: Optional[List[str]] = Query(None, description="需排除的过敏原（北京）"),
    price_levels: Optional[List[int]] = Query(None, description="价格档次 1-4"),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(5.0, ge=0.1, le=50.0),
    sort_mode: str = Query("default", description="排序模式"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
) -> SearchResponse:
    params = SearchParams(
        city=city,
        q=q or "",
        diet_labels=diet_labels or [],
        cuisine_types=cuisine_types or [],
        allergen_free_required=allergen_free_required or [],
        price_levels=price_levels or [],
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        sort_mode=sort_mode,
        offset=offset,
        limit=limit,
        min_rating=min_rating,
    )

    _uid, user_allergens = await _get_user_context(request)
    user_geo: Optional[Tuple[float, float]] = (lat, lng) if lat is not None and lng is not None else None

    return await search_service.search(
        params=params,
        user_allergens=user_allergens,
        user_geo=user_geo,
    )


@router.get("/autocomplete")
async def autocomplete(
    prefix: str = Query(..., min_length=1, max_length=100),
    size: int = Query(8, ge=1, le=20),
    city: Optional[str] = Query(None),
) -> List[str]:
    return await search_service.autocomplete(prefix, size=size, city=city)


