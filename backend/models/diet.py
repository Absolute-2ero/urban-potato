from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel

VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}


class DietProfile(BaseModel):
    user_id: int
    diet_labels: List[str] = []
    allergens: List[str] = []
    price_pref: Optional[int] = None
    updated_at: Optional[datetime] = None


class DietProfileUpdate(BaseModel):
    diet_labels: Optional[List[str]] = None
    allergens: Optional[List[str]] = None
    price_pref: Optional[int] = None


class FoodLogCreate(BaseModel):
    food_id: Optional[int] = None
    food_name_snapshot: str
    log_date: Optional[date] = None
    meal_type: str = "lunch"
    amount_g: float = 100.0
    calories: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carb_g: float = 0.0
    notes: Optional[str] = None


class FoodLogEntry(BaseModel):
    id: int
    user_id: int
    food_name_snapshot: str
    log_date: date
    meal_type: str
    amount_g: float
    calories: float
    protein_g: float
    fat_g: float
    carb_g: float
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
