from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from database import get_es

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])

_INDEX = "restaurants"


@router.get("/{restaurant_id}")
async def get_restaurant(restaurant_id: str) -> Dict[str, Any]:
    es = get_es()
    try:
        doc = await es.get(index=_INDEX, id=restaurant_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    src = dict(doc["_source"])
    src["restaurant_id"] = doc["_id"]
    for field in ("diet_labels", "allergens", "allergen_free", "images"):
        val = src.get(field)
        if isinstance(val, str):
            src[field] = [v for v in val.split() if v] if val.strip() else []
        elif not isinstance(val, list):
            src[field] = []
    if not isinstance(src.get("menu_items"), list):
        src["menu_items"] = []
    if not src.get("price_level"):
        import re as _re
        pr = src.get("price_range", "")
        if pr:
            nums = [int(n) for n in _re.findall(r'\d+', pr)]
            if nums:
                avg = sum(nums) / len(nums)
                src["price_level"] = 1 if avg < 100 else 2 if avg < 200 else 3 if avg < 400 else 4
        if not src.get("price_level"):
            prices = [i["price"] for i in src["menu_items"] if isinstance(i, dict) and i.get("price")]
            if prices:
                avg = sum(prices) / len(prices)
                src["price_level"] = 1 if avg < 50 else 2 if avg < 100 else 3 if avg < 200 else 4
    return src
