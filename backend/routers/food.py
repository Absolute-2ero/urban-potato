from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from models.food import FoodConfirmRequest, FoodItem, FoodSearchResult
from services import food_service

router = APIRouter(prefix="/api/food", tags=["food"])


@router.get("/search", response_model=FoodSearchResult)
async def search_food(
    q: str = Query(..., min_length=1, max_length=200, description="食物名称关键词"),
    limit: int = Query(10, ge=1, le=50),
) -> FoodSearchResult:
    return await food_service.search_food(q, limit=limit)


@router.post("/confirm", response_model=FoodItem)
async def confirm_food(payload: FoodConfirmRequest, request: Request) -> FoodItem:
    """
    BR-03: 用户确认 LLM 估算的食物营养数据后写入数据库。
    需要登录（保证责任可溯）。
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    try:
        stored = await food_service.confirm_and_store(payload.item)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return stored


@router.get("/{food_id}", response_model=FoodItem)
async def get_food(food_id: int) -> FoodItem:
    item = await food_service.get_food_by_id(food_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food not found")
    return item
