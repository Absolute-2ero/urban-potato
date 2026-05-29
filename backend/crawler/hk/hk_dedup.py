from __future__ import annotations

"""
Deduplication and merge pass for Hong Kong restaurant data.

After both OpenRice and Foodpanda crawls complete, this module:
1. Loads all restaurants from SQLite.
2. Pairs up records from both sources that refer to the same real restaurant
   (matched by name similarity AND district/geo proximity).
3. Merges the pair: keeps the richer source as primary, fills gaps from the other.
4. Writes merged docs back to SQLite and flags duplicates.

Usage (via hk_pipeline.py):
    py -3.12 -m crawler.hk.hk_pipeline --dedup
"""

import json
import logging
import re
import unicodedata
from math import asin, cos, radians, sin, sqrt
from typing import Any

logger = logging.getLogger(__name__)

_SIM_THRESHOLD = 0.40   # Jaccard character-set similarity threshold


# ── Text normalisation ─────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    # Drop common noise tokens
    for noise in ("restaurant", "cafe", "hk", "hong kong", "limited", "ltd", "company"):
        text = re.sub(rf"\b{noise}\b", "", text)
    return text.strip()


def _char_set(text: str) -> set[str]:
    """Return the set of non-space characters after normalisation."""
    return set(_normalize(text).replace(" ", ""))


def _name_similarity(a: str, b: str) -> float:
    """Jaccard similarity of character sets."""
    sa, sb = _char_set(a), _char_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ── Geo distance ───────────────────────────────────────────────────────────────

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in metres between two WGS-84 points."""
    R = 6_371_000
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _geo_close(doc_a: dict, doc_b: dict, threshold_m: float = 300.0) -> bool:
    """True if both docs have valid GPS and are within threshold_m of each other."""
    ga, gb = doc_a.get("geo") or {}, doc_b.get("geo") or {}
    la, loa = ga.get("lat"), ga.get("lng")
    lb, lob = gb.get("lat"), gb.get("lng")
    if any(x is None for x in (la, loa, lb, lob)):
        return False
    return _haversine_m(la, loa, lb, lob) <= threshold_m


def _district_match(doc_a: dict, doc_b: dict) -> bool:
    """True if both have the same non-empty district string."""
    da = (doc_a.get("district") or "").strip().lower()
    db = (doc_b.get("district") or "").strip().lower()
    return bool(da) and da == db


def _is_same_restaurant(doc_a: dict, doc_b: dict) -> bool:
    """Decide if two docs refer to the same restaurant."""
    sim = _name_similarity(doc_a.get("name", ""), doc_b.get("name", ""))
    if sim < _SIM_THRESHOLD:
        return False
    # Need at least one proximity signal
    return _district_match(doc_a, doc_b) or _geo_close(doc_a, doc_b)


# ── Merge logic ────────────────────────────────────────────────────────────────

def _merge(primary: dict, secondary: dict) -> dict:
    """
    Return a merged copy of primary, filling gaps from secondary.
    primary is usually the record with more review/detail data.
    """
    merged = dict(primary)

    # Prefer Foodpanda menu_items if it has significantly more
    primary_menu = primary.get("menu_items") or []
    secondary_menu = secondary.get("menu_items") or []
    if len(secondary_menu) > len(primary_menu) * 1.2 + 2:
        merged["menu_items"] = secondary_menu

    # Fill images from secondary if primary has none
    if not merged.get("images") and secondary.get("images"):
        merged["images"] = secondary["images"]

    # Fill geo if primary is missing
    p_geo = primary.get("geo") or {}
    if p_geo.get("lat") is None:
        s_geo = secondary.get("geo") or {}
        if s_geo.get("lat") is not None:
            merged["geo"] = s_geo

    # Copy source-specific IDs from secondary for traceability
    for key in ("foodpanda_id", "foodpanda_url", "openrice_id", "openrice_url"):
        if key not in merged and key in secondary:
            merged[key] = secondary[key]

    # Merge tags (deduplicated)
    all_tags = list(dict.fromkeys((merged.get("tags") or []) + (secondary.get("tags") or [])))
    if all_tags:
        merged["tags"] = all_tags

    return merged


# ── Main dedup pass ────────────────────────────────────────────────────────────

async def run_dedup() -> tuple[int, int]:
    """
    Load all HK restaurants from SQLite, find duplicates, merge them.
    Returns (pairs_merged, total_remaining).
    """
    from database import get_sqlite
    db = get_sqlite()

    async with db.execute(
        "SELECT restaurant_id, doc_json FROM pipeline_progress WHERE restaurant_id LIKE 'openrice_%' OR restaurant_id LIKE 'foodpanda_%'"
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        logger.info("Dedup: no HK restaurants in pipeline_progress")
        return 0, 0

    docs: list[dict] = [json.loads(row["doc_json"]) for row in rows]
    openrice = [d for d in docs if d.get("source") == "openrice"]
    foodpanda = [d for d in docs if d.get("source") == "foodpanda"]

    logger.info("Dedup: %d OpenRice + %d Foodpanda = %d total", len(openrice), len(foodpanda), len(docs))

    merged_count = 0
    removed_ids: set[str] = set()

    for fp_doc in foodpanda:
        if fp_doc["restaurant_id"] in removed_ids:
            continue
        best_or: dict | None = None
        best_sim = 0.0
        for or_doc in openrice:
            if or_doc["restaurant_id"] in removed_ids:
                continue
            if _is_same_restaurant(fp_doc, or_doc):
                sim = _name_similarity(fp_doc.get("name", ""), or_doc.get("name", ""))
                if sim > best_sim:
                    best_sim = sim
                    best_or = or_doc

        if best_or is None:
            continue

        # OpenRice is primary (richer review data); Foodpanda fills gaps
        merged = _merge(best_or, fp_doc)
        merged_count += 1

        # Update primary (OpenRice) doc in SQLite
        await db.execute(
            "UPDATE pipeline_progress SET doc_json=?, name=?, updated_at=datetime('now') WHERE restaurant_id=?",
            (json.dumps(merged, ensure_ascii=False, default=str), merged.get("name", ""), merged["restaurant_id"]),
        )
        # Delete the secondary (Foodpanda) doc
        await db.execute(
            "DELETE FROM pipeline_progress WHERE restaurant_id=?",
            (fp_doc["restaurant_id"],),
        )
        removed_ids.add(fp_doc["restaurant_id"])
        logger.debug(
            "Dedup: merged Foodpanda %r → OpenRice %r (sim=%.2f)",
            fp_doc.get("name"), best_or.get("name"), best_sim,
        )

    await db.commit()

    remaining = len(docs) - len(removed_ids)
    logger.info("Dedup: merged %d pairs, %d restaurants remaining", merged_count, remaining)
    return merged_count, remaining
