from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

VALID_DIET_LABELS = {
    "vegan", "vegetarian", "halal", "kosher", "organic",
    "gluten-free", "dairy-free", "nut-free", "shellfish-free", "soy-free",
    "low-carb", "keto", "high-protein", "low-calorie", "low-sodium",
}

VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}


class DietProfile(BaseModel):
    user_id: int
    diet_labels: List[str] = []
    allergens: List[str] = []
    calorie_goal: Optional[int] = None
    protein_goal_g: Optional[float] = None
    fat_goal_g: Optional[float] = None
    carb_goal_g: Optional[float] = None
    price_pref: Optional[int] = None
    cuisine_prefs: List[str] = []
    updated_at: Optional[datetime] = None


class DietProfileUpdate(BaseModel):
    diet_labels: Optional[List[str]] = None
    allergens: Optional[List[str]] = None
    calorie_goal: Optional[int] = None
    protein_goal_g: Optional[float] = None
    fat_goal_g: Optional[float] = None
    carb_goal_g: Optional[float] = None
    price_pref: Optional[int] = None
    cuisine_prefs: Optional[List[str]] = None

    @field_validator("diet_labels")
    @classmethod
    def validate_diet_labels(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        invalid = [l for l in v if l not in VALID_DIET_LABELS]
        if invalid:
            raise ValueError(f"无效的饮食标签: {invalid}，有效值: {sorted(VALID_DIET_LABELS)}")
        return v

    @field_validator("price_pref")
    @classmethod
    def validate_price_pref(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (1, 2, 3, 4):
            raise ValueError("price_pref 必须在 1-4 之间")
        return v


class FoodLogCreate(BaseModel):
    food_id: int
    quantity_g: float
    meal_type: str
    log_date: Optional[date] = None

    @field_validator("quantity_g")
    @classmethod
    def qty_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("分量必须大于 0")
        return v

    @field_validator("meal_type")
    @classmethod
    def meal_type_valid(cls, v: str) -> str:
        if v not in VALID_MEAL_TYPES:
            raise ValueError(f"meal_type 必须是 {VALID_MEAL_TYPES} 之一")
        return v


class FoodLogEntry(BaseModel):
    id: int
    user_id: int
    log_date: date
    meal_type: str
    food_id: int
    food_name: str
    quantity_g: float
    calories_kcal: float
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carb_g: Optional[float] = None
    created_at: Optional[datetime] = None
