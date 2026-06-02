"""
Quick smoke test for the LLM API connection and llm_labeler.

Usage (from backend/):
    py -3.12 -m crawler.test.test_llm
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


TEST_DISHES = [
    {"name": "Beef Noodle", "description": "Braised beef with noodles", "price": 68},
    {"name": "蛋炒飯", "description": "", "price": 45},
    {"name": "Vegan Salad", "description": "Mixed greens, tofu, sesame dressing", "price": 58},
    {"name": "少油清蒸魚", "description": "Steamed fish with minimal oil, light soy sauce", "price": 120},
    {"name": "無糖豆漿", "description": "Unsweetened soy milk", "price": 18},
    {"name": "不辣牛肉炒飯", "description": "Stir-fried beef rice, non-spicy", "price": 55},
    {"name": "無花生沙律", "description": "Garden salad, peanut-free dressing", "price": 68},
]

NEW_LABELS = {
    "low-fat", "low-sugar", "low-oil", "no-spicy", "peanut-free", "seafood-free"
}


TEST_RESTAURANTS = [
    {"name": "翠華餐廳"},           # Chinese only → needs name_en
    {"name": "Mak's Noodle"},       # English only → needs name_zh
    {"name": "Tim Ho Wan 添好運"},  # Mixed → both should be clean
]


async def main() -> None:
    from config import cfg
    from crawler.hk.llm_labeler import _call_llm, translate_restaurant_name

    print(f"Model  : {cfg.llm_model}")
    print(f"BaseURL: {cfg.llm_base_url}")
    print(f"Key    : {'set' if cfg.llm_api_key else 'NOT SET'}")
    print()

    if not cfg.llm_api_key:
        print("ERROR: LLM_API_KEY not set in .env")
        sys.exit(1)

    # ── Restaurant name translation ───────────────────────────────────────────
    print("── Restaurant name translation ──")
    name_ok = True
    for doc in TEST_RESTAURANTS:
        await translate_restaurant_name(doc)
        en, zh = doc.get("name_en", ""), doc.get("name_zh", "")
        if not en or not zh:
            name_ok = False
        print(f"  {doc['name']}")
        print(f"    name_en: {en}")
        print(f"    name_zh: {zh}")
        print()

    # ── Menu item labeling ────────────────────────────────────────────────────
    print("── Menu item labeling ──")
    results = await _call_llm(TEST_DISHES)

    all_labels_seen: set[str] = set()
    nutrition_ok = True

    for dish, result in zip(TEST_DISHES, results):
        labels = result.get("diet_labels", [])
        all_labels_seen.update(labels)
        if not result.get("calories"):
            nutrition_ok = False
        print(f"  {dish['name']}")
        print(f"    name_en : {result.get('name_en')}")
        print(f"    name_zh : {result.get('name_zh')}")
        print(f"    nutrition: {result.get('calories')} kcal  "
              f"P:{result.get('protein')}g  F:{result.get('fat')}g  C:{result.get('carbs')}g")
        print(f"    labels  : {labels}")
        print(f"    allergens: {result.get('allergens', [])}")
        print()

    new_labels_seen = all_labels_seen & NEW_LABELS
    print("─" * 50)
    print(f"Restaurant name_en + name_zh : {'OK' if name_ok else 'MISSING — check prompt'}")
    print(f"Menu item nutrition          : {'OK' if nutrition_ok else 'MISSING — check prompt'}")
    print(f"Menu item name_zh            : {'OK' if all(r.get('name_zh') for r in results) else 'MISSING — check prompt'}")
    print(f"New labels seen              : {new_labels_seen or 'none'}")


if __name__ == "__main__":
    asyncio.run(main())
