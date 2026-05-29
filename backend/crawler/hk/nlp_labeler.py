from __future__ import annotations

"""
NLP diet-label inference for Hong Kong restaurants.

Extends the Beijing labeler with English and Cantonese keyword patterns.
Keeps the same label schema and label_restaurant() signature so it can be
swapped in transparently.
"""

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ── Diet label patterns (English + Cantonese + Mandarin) ─────────────────────

_DIET_PATTERNS: List[Tuple[str, str]] = [
    # Vegan
    (r"vegan|plant.based|plant based|pure vegan|全素|純素|纯素|植物性|植物基", "vegan"),
    # Vegetarian
    (r"vegetarian|veggie|素食|素菜|吃素|齋菜|斋菜|佛家|佛教|齋|全齋", "vegetarian"),
    # Halal
    (r"halal|清真|穆斯林|回族|真主|清真認證|清真认证", "halal"),
    # Kosher
    (r"kosher|猶太|犹太", "kosher"),
    # Organic
    (r"organic|有機|有机|绿色食品", "organic"),
    # Gluten-free
    (r"gluten.free|gluten free|無麩質|无麸质|無小麥|无小麦", "gluten-free"),
    # Dairy-free
    (r"dairy.free|dairy free|lactose.free|lactose free|無乳糖|无乳糖|無奶|无奶", "dairy-free"),
    # Keto
    (r"keto|ketogenic|生酮|低碳高脂", "keto"),
    # High-protein
    (r"high.protein|high protein|高蛋白", "high-protein"),
    # Low-carb
    (r"low.carb|low carb|低碳水|低碳", "low-carb"),
    # Low-calorie
    (r"low.cal|low cal|low.calorie|low calorie|低卡|低熱量|低热量|減脂|减脂|控卡", "low-calorie"),
    # Low-sodium
    (r"low.sodium|low sodium|少鹽|少盐|減鹽|减盐|低鈉|低钠", "low-sodium"),
    # Nut-free
    (r"nut.free|nut free|無堅果|无坚果", "nut-free"),
    # Shellfish-free
    (r"shellfish.free|shellfish free|無貝類|无贝类", "shellfish-free"),
    # Soy-free
    (r"soy.free|soy free|無大豆|无大豆", "soy-free"),
    # Light meal (HK specific: 輕食 / 健康餐 / salad bars common in HK)
    (r"light meal|light food|輕食|轻食|健康餐|沙律|salad|健身餐|減肥餐|减肥餐", "light-meal"),
]

# ── Allergen patterns ─────────────────────────────────────────────────────────

_ALLERGEN_PATTERNS: List[Tuple[str, str]] = [
    (r"peanut|花生", "peanut"),
    (r"tree nut|nut|堅果|坚果|核桃|腰果|杏仁|開心果|开心果|榛子|腰果", "tree_nut"),
    (r"dairy|milk|cream|cheese|butter|lactose|牛奶|乳製品|乳制品|忌廉|芝士|cheese|黃油|黄油|鮮奶|鲜奶", "dairy"),
    (r"gluten|wheat|flour|麵包|面包|麩質|麸质|小麥|小麦|麵粉|面粉", "gluten"),
    (r"shellfish|shrimp|crab|lobster|scallop|prawn|蝦|虾|蟹|貝類|贝类|龍蝦|龙虾|扇貝|扇贝", "shellfish"),
    (r"soy|tofu|soya|大豆|豆腐|豆漿|豆浆|黃豆|黄豆", "soy"),
    (r"\begg\b|蛋|蛋黃|蛋黄|蛋白", "egg"),
    (r"sesame|tahini|芝麻|麻醬|麻酱", "sesame"),
    (r"\bfish\b|salmon|tuna|cod|魚|鱼|三文魚|三文鱼|吞拿魚|吞拿鱼|金槍魚|金枪鱼", "fish"),
]

# ── Allergen-free claims ──────────────────────────────────────────────────────

_ALLERGEN_FREE_PATTERNS: List[Tuple[str, str]] = [
    (r"peanut.free|no peanut|無花生|无花生|不含花生", "peanut"),
    (r"gluten.free|wheat.free|無麩質|无麸质|無小麥|无小麦", "gluten"),
    (r"dairy.free|lactose.free|無乳糖|无乳糖|無奶|无奶", "dairy"),
    (r"soy.free|無大豆|无大豆", "soy"),
    (r"nut.free|無堅果|无坚果", "tree_nut"),
    (r"egg.free|無蛋|无蛋", "egg"),
]

# ── Cuisine → diet inference ──────────────────────────────────────────────────

_CUISINE_DIET_MAP: List[Tuple[str, str]] = [
    (r"vegetarian|vegan|素食|素菜|全素|純素|纯素|齋|斋", "vegetarian"),
    (r"halal|清真", "halal"),
    (r"organic|有機|有机", "organic"),
]


def _match(text: str, patterns: List[Tuple[str, str]]) -> List[str]:
    found: List[str] = []
    t = text.lower()
    for pattern, label in patterns:
        if re.search(pattern, t, re.IGNORECASE) and label not in found:
            found.append(label)
    return found


def _build_text(doc: Dict[str, Any]) -> str:
    parts = [
        doc.get("name", ""),
        doc.get("cuisine_type", ""),
        doc.get("district", ""),
        " ".join(doc.get("tags", [])),
    ]
    for item in doc.get("menu_items", []):
        parts.append(item.get("name", ""))
        parts.append(item.get("description", "") or "")
    return " ".join(p for p in parts if p)


def label_restaurant(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Infer diet_labels, allergens, allergen_free for a HK restaurant doc.
    Mutates and returns the doc.
    """
    text = _build_text(doc)
    cuisine_labels = _match(doc.get("cuisine_type", ""), _CUISINE_DIET_MAP)

    diet_labels = list(dict.fromkeys(
        doc.get("diet_labels", [])
        + cuisine_labels
        + _match(text, _DIET_PATTERNS)
    ))
    allergens = list(dict.fromkeys(
        doc.get("allergens", [])
        + _match(text, _ALLERGEN_PATTERNS)
    ))
    allergen_free = list(dict.fromkeys(
        doc.get("allergen_free", [])
        + _match(text, _ALLERGEN_FREE_PATTERNS)
    ))

    allergen_free = [a for a in allergen_free if a not in allergens]

    if "vegan" in diet_labels and "vegetarian" not in diet_labels:
        diet_labels.append("vegetarian")

    doc["diet_labels"]   = diet_labels
    doc["allergens"]     = allergens
    doc["allergen_free"] = allergen_free
    return doc
