from __future__ import annotations

import logging
import os

import aiosqlite

from config import cfg

logger = logging.getLogger(__name__)

_FOOD_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "food_seed.json")


async def init_sqlite_schema(conn: aiosqlite.Connection) -> None:
    """建表 + FTS 索引 + 导入种子数据（幂等，可重复执行）。"""
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS food_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name_zh      TEXT NOT NULL,
            name_en      TEXT,
            name_pinyin  TEXT,
            calories     REAL NOT NULL,
            protein_g    REAL NOT NULL DEFAULT 0,
            fat_g        REAL NOT NULL DEFAULT 0,
            carb_g       REAL NOT NULL DEFAULT 0,
            sodium_mg    REAL,
            fiber_g      REAL,
            diet_labels  TEXT NOT NULL DEFAULT '[]',
            source       TEXT NOT NULL DEFAULT 'static',
            verified     INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS food_fts
        USING fts5(
            name_zh, name_en, name_pinyin,
            content='food_items',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS food_fts_insert
        AFTER INSERT ON food_items BEGIN
            INSERT INTO food_fts(rowid, name_zh, name_en, name_pinyin)
            VALUES (new.id, new.name_zh, new.name_en, new.name_pinyin);
        END;

        CREATE TRIGGER IF NOT EXISTS food_fts_delete
        AFTER DELETE ON food_items BEGIN
            INSERT INTO food_fts(food_fts, rowid, name_zh, name_en, name_pinyin)
            VALUES ('delete', old.id, old.name_zh, old.name_en, old.name_pinyin);
        END;

        CREATE TRIGGER IF NOT EXISTS food_fts_update
        AFTER UPDATE ON food_items BEGIN
            INSERT INTO food_fts(food_fts, rowid, name_zh, name_en, name_pinyin)
            VALUES ('delete', old.id, old.name_zh, old.name_en, old.name_pinyin);
            INSERT INTO food_fts(rowid, name_zh, name_en, name_pinyin)
            VALUES (new.id, new.name_zh, new.name_en, new.name_pinyin);
        END;
    """)
    await conn.commit()

    # 仅在表为空时导入种子数据
    async with conn.execute("SELECT COUNT(*) FROM food_items") as cur:
        row = await cur.fetchone()
        count = row[0]

    if count == 0:
        await _seed_food_items(conn)
        logger.info("Food DB seeded with static items")
    else:
        logger.info("Food DB already has %d items, skip seeding", count)


async def _seed_food_items(conn: aiosqlite.Connection) -> None:
    import json
    seed_path = os.path.normpath(_FOOD_SEED_PATH)
    if not os.path.exists(seed_path):
        logger.warning("food_seed.json not found at %s", seed_path)
        return

    with open(seed_path, encoding="utf-8") as f:
        items = json.load(f)

    await conn.executemany(
        """INSERT OR IGNORE INTO food_items
           (name_zh, name_en, name_pinyin, calories, protein_g, fat_g, carb_g,
            sodium_mg, fiber_g, diet_labels, source, verified)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
        [
            (
                item["name_zh"],
                item.get("name_en"),
                item.get("name_pinyin"),
                item["calories"],
                item.get("protein_g", 0),
                item.get("fat_g", 0),
                item.get("carb_g", 0),
                item.get("sodium_mg"),
                item.get("fiber_g"),
                __import__("json").dumps(item.get("diet_labels", []), ensure_ascii=False),
                "static",
            )
            for item in items
        ],
    )
    await conn.commit()
