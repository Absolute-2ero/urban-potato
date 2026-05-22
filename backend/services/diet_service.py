from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Optional

from database import get_pg
from models.diet import DietProfile, DietProfileUpdate, FoodLogCreate, FoodLogEntry

logger = logging.getLogger(__name__)


# ── 饮食档案 ──────────────────────────────────────────────────────────────────

async def get_diet_profile(user_id: str) -> Optional[DietProfile]:
    pool = get_pg()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id, diet_labels, allergens, price_pref, updated_at "
            "FROM diet_profiles WHERE user_id = $1",
            user_id,
        )
    if row is None:
        return None
    return DietProfile(
        user_id=row["user_id"],
        diet_labels=list(row["diet_labels"] or []),
        allergens=list(row["allergens"] or []),
        price_pref=row["price_pref"],
        updated_at=row["updated_at"],
    )


async def upsert_diet_profile(user_id: str, payload: DietProfileUpdate) -> DietProfile:
    pool = get_pg()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO diet_profiles (user_id, diet_labels, allergens, price_pref)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
                SET diet_labels = EXCLUDED.diet_labels,
                    allergens   = EXCLUDED.allergens,
                    price_pref  = EXCLUDED.price_pref,
                    updated_at  = now()
            RETURNING user_id, diet_labels, allergens, price_pref, updated_at
            """,
            user_id,
            payload.diet_labels,
            payload.allergens,
            payload.price_pref,
        )
    logger.info("Upserted diet profile for user %s", user_id)
    return DietProfile(
        user_id=row["user_id"],
        diet_labels=list(row["diet_labels"] or []),
        allergens=list(row["allergens"] or []),
        price_pref=row["price_pref"],
        updated_at=row["updated_at"],
    )


# ── 饮食日志 ──────────────────────────────────────────────────────────────────

async def add_food_log(user_id: str, entry: FoodLogCreate) -> FoodLogEntry:
    pool = get_pg()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO food_log_entries
                (user_id, food_id, food_name_snapshot, log_date, meal_type,
                 amount_g, calories, protein_g, fat_g, carb_g)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            user_id,
            entry.food_id,
            entry.food_name_snapshot,
            entry.log_date,
            entry.meal_type,
            entry.amount_g,
            entry.calories,
            entry.protein_g,
            entry.fat_g,
            entry.carb_g,
        )
    return FoodLogEntry(**dict(row))


async def list_food_logs(user_id: str, log_date: date) -> List[FoodLogEntry]:
    pool = get_pg()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM food_log_entries WHERE user_id = $1 AND log_date = $2 ORDER BY created_at",
            user_id,
            log_date,
        )
    return [FoodLogEntry(**dict(r)) for r in rows]


async def delete_food_log(user_id: str, entry_id: int) -> bool:
    pool = get_pg()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM food_log_entries WHERE id = $1 AND user_id = $2",
            entry_id,
            user_id,
        )
    # asyncpg returns "DELETE N"
    return result.endswith("1")


async def get_daily_totals(user_id: str, log_date: date) -> Dict[str, float]:
    """返回当日各营养素合计。"""
    pool = get_pg()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COALESCE(SUM(calories), 0)  AS calories,
                COALESCE(SUM(protein_g), 0) AS protein_g,
                COALESCE(SUM(fat_g), 0)     AS fat_g,
                COALESCE(SUM(carb_g), 0)    AS carb_g
            FROM food_log_entries
            WHERE user_id = $1 AND log_date = $2
            """,
            user_id,
            log_date,
        )
    return {
        "calories": float(row["calories"]),
        "protein_g": float(row["protein_g"]),
        "fat_g": float(row["fat_g"]),
        "carb_g": float(row["carb_g"]),
    }


# ── 收藏餐厅 ──────────────────────────────────────────────────────────────────

async def save_restaurant(user_id: str, restaurant_id: str) -> None:
    pool = get_pg()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO saved_restaurants (user_id, restaurant_id)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            user_id,
            restaurant_id,
        )


async def unsave_restaurant(user_id: str, restaurant_id: str) -> None:
    pool = get_pg()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM saved_restaurants WHERE user_id = $1 AND restaurant_id = $2",
            user_id,
            restaurant_id,
        )


async def list_saved_restaurants(user_id: str) -> List[str]:
    pool = get_pg()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT restaurant_id FROM saved_restaurants WHERE user_id = $1 ORDER BY saved_at DESC",
            user_id,
        )
    return [r["restaurant_id"] for r in rows]
