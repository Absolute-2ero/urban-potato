from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.personalization_service import record_interaction

router = APIRouter(prefix="/api/interactions", tags=["interactions"])


class InteractionIn(BaseModel):
    restaurant_id: str
    interaction_type: str = "view"  # view | save | click


@router.post("")
async def log_interaction(body: InteractionIn, request: Request) -> dict:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Login required")
    if body.interaction_type not in ("view", "save", "click"):
        raise HTTPException(status_code=422, detail="Invalid interaction_type")
    await record_interaction(uid, body.restaurant_id, body.interaction_type)
    return {"ok": True}
