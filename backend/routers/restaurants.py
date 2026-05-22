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
    src = doc["_source"]
    src["restaurant_id"] = doc["_id"]
    return src
