from __future__ import annotations

import os
from typing import Any, Dict, List

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/cities", tags=["cities"])

_CITIES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "cities.yaml")


def _load_cities() -> List[Dict[str, Any]]:
    try:
        with open(_CITIES_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("cities", [])
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="cities.yaml not found")


@router.get("")
async def list_cities() -> List[Dict[str, Any]]:
    """Return all configured cities with their center coordinates."""
    return _load_cities()
