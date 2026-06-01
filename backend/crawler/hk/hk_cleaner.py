from __future__ import annotations

"""
Data cleaning pass for HK restaurant records in SQLite.

Fixes menu item names and removes within-restaurant duplicates.
No LLM or network calls — pure string normalisation.

Run before dedup:
    py -3.12 -m crawler.hk.hk_pipeline --clean
"""

import json
import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

# ── Name-level noise patterns ─────────────────────────────────────────────────

# Parenthetical delivery/takeaway qualifiers that add no info
_STRIP_PARENS = re.compile(
    r"\s*[\(\（]"
    r"(?:takeout|take[\s\-]?away|take[\s\-]?out|外賣|外卖|外送|delivery|"
    r"pickup|pick[\s\-]?up|自取|to[\s\-]?go)"
    r"[^\)\）]*[\)\）]",
    re.IGNORECASE,
)

# Leading product / SKU codes: "PFL00104. ", "PFC05052. ", "ABC-1234 "
_SKU_PREFIX = re.compile(r"^[A-Z]{2,6}[\-]?\d{3,8}\.?\s+", re.IGNORECASE)

# Leading/trailing slashes, pipes, bullets, hyphens (e.g. "/ A4 (Set)/")
_EDGE_NOISE = re.compile(r"^[\s/|·•\-]+|[\s/|·•\-]+$")

# Non-food utility items to drop entirely (exact match after cleaning)
_UTILITY_RE = re.compile(
    r"^(?:disposable\s+(?:spoon|fork|chopstick|straw|cup|bowl|bag|cutlery|utensil)|"
    r"plastic\s+(?:bag|wrap)|carrier\s+bag|cutlery\s+set|paper\s+bag|"
    r"napkin|sauce\s+packet|wet\s+wipe|wooden\s+(?:spoon|fork))s?$",
    re.IGNORECASE,
)


# ── Per-item helpers ──────────────────────────────────────────────────────────

def _clean_name(name: str) -> str:
    name = _STRIP_PARENS.sub("", name)
    name = _SKU_PREFIX.sub("", name)
    name = _EDGE_NOISE.sub("", name)
    name = re.sub(r"\s{2,}", " ", name)
    return name.strip()


def _normalize_key(name: str) -> str:
    """Collapse to bare characters for dedup comparison only."""
    name = unicodedata.normalize("NFKD", name.lower())
    # Keep ASCII word chars and CJK characters; drop everything else
    name = re.sub(r"[^\w一-鿿]", "", name, flags=re.UNICODE)
    return name


def _item_richness(item: dict) -> int:
    """Score an item by how much data it has — used to pick the best duplicate."""
    return (
        bool(item.get("description"))
        + bool(item.get("price"))
        + bool(item.get("category"))
    )


# ── Per-restaurant cleaning ───────────────────────────────────────────────────

def _clean_menu_items(items: list[dict]) -> tuple[list[dict], int, int]:
    """
    Clean and deduplicate menu items for one restaurant.
    Returns (cleaned_items, n_removed, n_renamed).
    """
    seen: dict[str, int] = {}   # key → index in `out`
    out: list[dict] = []
    removed = renamed = 0

    for item in items:
        raw = item.get("name", "")
        cleaned = _clean_name(raw)

        if not cleaned:
            removed += 1
            continue

        # Drop pure utility items (cutlery, bags, etc.)
        if _UTILITY_RE.match(cleaned):
            removed += 1
            continue

        key = _normalize_key(cleaned)

        if key in seen:
            # Keep whichever version has more data
            idx = seen[key]
            if _item_richness(item) > _item_richness(out[idx]):
                out[idx] = {**item, "name": cleaned}
            removed += 1
        else:
            seen[key] = len(out)
            if cleaned != raw:
                renamed += 1
            out.append({**item, "name": cleaned})

    return out, removed, renamed


def clean_restaurant(doc: dict) -> tuple[dict, int, int]:
    """
    Clean menu items in a restaurant doc (mutates in place).
    Returns (doc, items_removed, items_renamed).
    """
    original = doc.get("menu_items") or []
    cleaned, removed, renamed = _clean_menu_items(original)
    doc["menu_items"] = cleaned
    return doc, removed, renamed


# ── Drop-empty pass ──────────────────────────────────────────────────────────

# ── Main pass ─────────────────────────────────────────────────────────────────

async def run_clean() -> tuple[int, int, int, int]:
    """
    Clean all HK restaurant docs in SQLite:
      1. Delete restaurants with 0 menu items (failed CAPTCHA etc.) so they
         get re-crawled on the next --resume run.
      2. Fix menu item names and remove within-restaurant duplicates.

    Returns (dropped, restaurants_updated, total_items_removed, total_items_renamed).
    """
    from database import get_sqlite
    db = get_sqlite()

    async with db.execute(
        "SELECT restaurant_id, name, doc_json FROM pipeline_progress "
        "WHERE restaurant_id LIKE 'openrice_%' OR restaurant_id LIKE 'foodpanda_%'"
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        logger.info("Clean: no HK restaurants found")
        return 0, 0, 0, 0

    # Pass 1 — drop restaurants with no menu items
    dropped = 0
    keep_rows = []
    for row in rows:
        doc = json.loads(row["doc_json"])
        if not doc.get("menu_items"):
            await db.execute(
                "DELETE FROM pipeline_progress WHERE restaurant_id=?",
                (row["restaurant_id"],),
            )
            dropped += 1
            logger.info("Clean: dropped empty-menu %r (%s)", row["name"], row["restaurant_id"])
        else:
            keep_rows.append((row["restaurant_id"], doc))

    logger.info("Clean: dropped %d restaurants with 0 menu items", dropped)

    # Pass 2 — clean names and deduplicate items in remaining restaurants
    updated = total_removed = total_renamed = 0
    for rid, doc in keep_rows:
        doc, removed, renamed = clean_restaurant(doc)
        if removed > 0 or renamed > 0:
            await db.execute(
                "UPDATE pipeline_progress SET doc_json=?, updated_at=datetime('now') "
                "WHERE restaurant_id=?",
                (json.dumps(doc, ensure_ascii=False, default=str), rid),
            )
            updated += 1
            total_removed += removed
            total_renamed += renamed
            logger.debug("Clean %r: %d removed, %d renamed", doc.get("name"), removed, renamed)

    await db.commit()
    logger.info(
        "Clean complete: %d dropped, %d updated — %d items removed, %d names fixed",
        dropped, updated, total_removed, total_renamed,
    )
    return dropped, updated, total_removed, total_renamed
