from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

from database import get_sqlite
from models.diet import DietProfile, DietProfileUpdate, FoodLogCreate, FoodLogEntry

logger = logging.getLogger(__name__)


# ── Diet profile ───────────────────────────────────────────────────────────────

async def get_diet_profile(user_id) -> Optional[DietProfile]:
    db = get_sqlite()
    async with db.execute(
        "SELECT user_id, diet_labels, allergens, price_pref, updated_at FROM diet_profiles WHERE user_id = ?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return DietProfile(
        user_id=row["user_id"],
        diet_labels=json.loads(row["diet_labels"] or "[]"),
        allergens=json.loads(row["allergens"] or "[]"),
        price_pref=row["price_pref"],
        updated_at=row["updated_at"],
    )


async def upsert_diet_profile(user_id, payload: DietProfileUpdate) -> DietProfile:
    db = get_sqlite()
    existing = await get_diet_profile(user_id)
    diet_labels = payload.diet_labels if payload.diet_labels is not None else (existing.diet_labels if existing else [])
    allergens = payload.allergens if payload.allergens is not None else (existing.allergens if existing else [])
    price_pref = payload.price_pref if payload.price_pref is not None else (existing.price_pref if existing else None)

    await db.execute(
        """INSERT INTO diet_profiles (user_id, diet_labels, allergens, price_pref, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET
               diet_labels = excluded.diet_labels,
               allergens   = excluded.allergens,
               price_pref  = excluded.price_pref,
               updated_at  = datetime('now')""",
        (user_id, json.dumps(diet_labels), json.dumps(allergens), price_pref),
    )
    await db.commit()
    return await get_diet_profile(user_id)  # type: ignore[return-value]


# ── Food log ───────────────────────────────────────────────────────────────────

async def add_food_log(user_id, entry: FoodLogCreate) -> FoodLogEntry:
    db = get_sqlite()
    log_date = entry.log_date or date.today()
    async with db.execute(
        """INSERT INTO food_log_entries
               (user_id, food_id, food_name_snapshot, log_date, meal_type,
                amount_g, calories, protein_g, fat_g, carb_g, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            entry.food_id,
            entry.food_name_snapshot,
            str(log_date),
            entry.meal_type,
            entry.amount_g,
            entry.calories,
            entry.protein_g,
            entry.fat_g,
            entry.carb_g,
            entry.notes,
        ),
    ) as cur:
        row_id = cur.lastrowid
    await db.commit()

    async with db.execute("SELECT * FROM food_log_entries WHERE id = ?", (row_id,)) as cur:
        row = await cur.fetchone()
    return _row_to_entry(row)


async def list_food_logs(user_id, log_date: date) -> List[FoodLogEntry]:
    db = get_sqlite()
    async with db.execute(
        "SELECT * FROM food_log_entries WHERE user_id = ? AND log_date = ? ORDER BY created_at",
        (user_id, str(log_date)),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_entry(r) for r in rows]


async def list_food_logs_range(user_id, from_date: date, to_date: date) -> List[FoodLogEntry]:
    db = get_sqlite()
    async with db.execute(
        "SELECT * FROM food_log_entries WHERE user_id = ? AND log_date BETWEEN ? AND ? ORDER BY log_date, created_at",
        (user_id, str(from_date), str(to_date)),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_entry(r) for r in rows]


async def delete_food_log(user_id, entry_id: int) -> bool:
    db = get_sqlite()
    async with db.execute(
        "DELETE FROM food_log_entries WHERE id = ? AND user_id = ?",
        (entry_id, user_id),
    ) as cur:
        deleted = cur.rowcount
    await db.commit()
    return deleted > 0


async def get_daily_totals(user_id, log_date: date) -> Dict[str, float]:
    db = get_sqlite()
    async with db.execute(
        """SELECT
               COALESCE(SUM(calories), 0)  AS calories,
               COALESCE(SUM(protein_g), 0) AS protein_g,
               COALESCE(SUM(fat_g), 0)     AS fat_g,
               COALESCE(SUM(carb_g), 0)    AS carb_g
           FROM food_log_entries WHERE user_id = ? AND log_date = ?""",
        (user_id, str(log_date)),
    ) as cur:
        row = await cur.fetchone()
    return {
        "calories": float(row["calories"]),
        "protein_g": float(row["protein_g"]),
        "fat_g": float(row["fat_g"]),
        "carb_g": float(row["carb_g"]),
    }


# ── Saved restaurants ──────────────────────────────────────────────────────────

async def save_restaurant(user_id, restaurant_id: str) -> None:
    db = get_sqlite()
    await db.execute(
        "INSERT OR IGNORE INTO saved_restaurants (user_id, restaurant_id) VALUES (?, ?)",
        (user_id, restaurant_id),
    )
    await db.commit()


async def unsave_restaurant(user_id, restaurant_id: str) -> None:
    db = get_sqlite()
    await db.execute(
        "DELETE FROM saved_restaurants WHERE user_id = ? AND restaurant_id = ?",
        (user_id, restaurant_id),
    )
    await db.commit()


async def list_saved_restaurants(user_id) -> List[str]:
    db = get_sqlite()
    async with db.execute(
        "SELECT restaurant_id FROM saved_restaurants WHERE user_id = ? ORDER BY saved_at DESC",
        (user_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [r["restaurant_id"] for r in rows]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_entry(row) -> FoodLogEntry:
    return FoodLogEntry(
        id=row["id"],
        user_id=row["user_id"],
        food_name_snapshot=row["food_name_snapshot"],
        log_date=row["log_date"],
        meal_type=row["meal_type"],
        amount_g=row["amount_g"],
        calories=row["calories"],
        protein_g=row["protein_g"],
        fat_g=row["fat_g"],
        carb_g=row["carb_g"],
        notes=row["notes"],
        created_at=row["created_at"],
    )
