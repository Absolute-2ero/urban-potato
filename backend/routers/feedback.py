from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional

from database import get_pg

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    query: str
    restaurant_id: Optional[str] = None
    is_relevant: bool
    comment: Optional[str] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(payload: FeedbackCreate, request: Request) -> dict:
    uid = request.session.get("user_id")  # 允许匿名反馈
    pool = get_pg()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO search_feedbacks (user_id, query, restaurant_id, is_relevant, comment)
            VALUES ($1, $2, $3, $4, $5)
            """,
            uid,
            payload.query,
            payload.restaurant_id,
            payload.is_relevant,
            payload.comment,
        )
    return {"message": "Feedback recorded"}
