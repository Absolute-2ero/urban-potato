from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, status

from models.diet import DietProfile, DietProfileUpdate, FoodLogCreate, FoodLogEntry
from services import diet_service

router = APIRouter(prefix="/api/diet", tags=["diet"])


def _require_login(request: Request) -> str:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return uid


# ── 饮食档案 ──────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=DietProfile)
async def get_profile(request: Request) -> DietProfile:
    uid = _require_login(request)
    profile = await diet_service.get_diet_profile(uid)
    if profile is None:
        # 返回空档案，不报错
        return DietProfile(user_id=uid, diet_labels=[], allergens=[], price_pref=None)
    return profile


@router.put("/profile", response_model=DietProfile)
async def update_profile(payload: DietProfileUpdate, request: Request) -> DietProfile:
    uid = _require_login(request)
    return await diet_service.upsert_diet_profile(uid, payload)


# ── 饮食日志 ──────────────────────────────────────────────────────────────────

@router.get("/log", response_model=list)
async def list_logs(
    request: Request,
    log_date: date = Query(default_factory=date.today),
) -> list:
    uid = _require_login(request)
    entries = await diet_service.list_food_logs(uid, log_date)
    totals = await diet_service.get_daily_totals(uid, log_date)
    return [{"entries": [e.model_dump() for e in entries], "totals": totals}]


@router.post("/log", response_model=FoodLogEntry, status_code=status.HTTP_201_CREATED)
async def add_log(payload: FoodLogCreate, request: Request) -> FoodLogEntry:
    uid = _require_login(request)
    return await diet_service.add_food_log(uid, payload)


@router.delete("/log/{entry_id}")
async def delete_log(entry_id: int, request: Request) -> dict:
    uid = _require_login(request)
    deleted = await diet_service.delete_food_log(uid, entry_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return {}


# ── 每日汇总 ──────────────────────────────────────────────────────────────────

@router.get("/totals")
async def daily_totals(
    request: Request,
    log_date: date = Query(default_factory=date.today),
) -> dict:
    uid = _require_login(request)
    return await diet_service.get_daily_totals(uid, log_date)


# ── 收藏餐厅 ──────────────────────────────────────────────────────────────────

@router.get("/saved-restaurants", response_model=list)
async def list_saved(request: Request) -> list:
    uid = _require_login(request)
    return await diet_service.list_saved_restaurants(uid)


@router.post("/saved-restaurants/{restaurant_id}")
async def save_restaurant(restaurant_id: str, request: Request) -> dict:
    uid = _require_login(request)
    await diet_service.save_restaurant(uid, restaurant_id)
    return {}


@router.delete("/saved-restaurants/{restaurant_id}")
async def unsave_restaurant(restaurant_id: str, request: Request) -> dict:
    uid = _require_login(request)
    await diet_service.unsave_restaurant(uid, restaurant_id)
    return {}
