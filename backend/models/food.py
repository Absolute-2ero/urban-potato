from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class FoodItem(BaseModel):
    food_id: Optional[int] = None
    name_zh: str
    name_en: Optional[str] = None
    name_pinyin: Optional[str] = None
    calories: float          # per 100g
    protein_g: float = 0.0
    fat_g: float = 0.0
    carb_g: float = 0.0
    sodium_mg: Optional[float] = None
    fiber_g: Optional[float] = None
    diet_labels: List[str] = []
    source: str = "static"   # static | llm_inferred | user_added
    verified: bool = True


class FoodSearchResult(BaseModel):
    source: str              # "database" | "llm_estimated" | "not_found"
    requires_confirm: bool
    items: List[FoodItem]


class FoodConfirmRequest(BaseModel):
    name_zh: str
    name_en: Optional[str] = None
    calories: float
    protein_g: float = 0.0
    fat_g: float = 0.0
    carb_g: float = 0.0
    diet_labels: List[str] = []
