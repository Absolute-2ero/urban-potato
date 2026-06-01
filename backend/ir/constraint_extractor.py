from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractedConstraints:
    min_calories: Optional[int] = None
    max_calories: Optional[int] = None
    min_protein_g: Optional[float] = None
    max_protein_g: Optional[float] = None
    max_price_rmb: Optional[float] = None
    meal_type: Optional[str] = None
    cleaned_query: str = ""


_CAL_PATTERNS: list[tuple[str, str]] = [
    # "300-400 calories" / "300–500 kcal"  — must come before single-bound patterns
    (r'(\d+)\s*[-–]\s*(\d+)\s*(?:cal(?:ories?)?|kcal)', 'range'),
    # "under/below/< 500 cal"
    (r'(?:under|below|less\s+than|<)\s*(\d+)\s*(?:cal(?:ories?)?|kcal)', 'max'),
    # "above/over/> 300 cal"
    (r'(?:above|over|more\s+than|>)\s*(\d+)\s*(?:cal(?:ories?)?|kcal)', 'min'),
    # Chinese: "500卡以内" / "热量低于600"
    (r'(\d+)\s*(?:卡路里?|千卡)\s*(?:以内|以下|左右)?', 'max'),
    (r'热量(?:低于|不超过|在)\s*(\d+)', 'max'),
]

_PROTEIN_PATTERNS: list[tuple[str, str]] = [
    # "50g+ protein" / "50g protein" / "50gprotein"
    (r'(\d+(?:\.\d+)?)\s*g\+?\s*(?:of\s+)?protein', 'min'),
    # "at least 30g protein"
    (r'(?:at\s+least|min(?:imum)?|[≥]|>=?)\s*(\d+(?:\.\d+)?)\s*g(?:\s+(?:of\s+)?protein)?', 'min'),
    # "30g蛋白质" / "蛋白质30g"
    (r'(\d+(?:\.\d+)?)\s*g\s*蛋白质', 'min'),
    (r'蛋白质\s*(\d+(?:\.\d+)?)\s*g', 'min'),
]

_PRICE_PATTERNS: list[tuple[str, str]] = [
    # "under 30 RMB/yuan/元"
    (r'(?:under|below|less\s+than|<)\s*¥?\s*(\d+(?:\.\d+)?)\s*(?:rmb|yuan|元|块)', 'max'),
    # "不超过30元" / "低于30块"
    (r'(?:不超过|低于)\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb|yuan)', 'max'),
    # "¥30"
    (r'¥\s*(\d+(?:\.\d+)?)', 'max'),
]

_MEAL_KEYWORDS: dict[str, list[str]] = {
    'breakfast': ['breakfast', 'morning meal', 'brunch', '早餐', '早饭', '早点'],
    'lunch':     ['lunch', 'midday meal', 'noon meal', '午餐', '午饭', '中午'],
    'dinner':    ['dinner', 'supper', 'evening meal', '晚餐', '晚饭', '晚上吃'],
    'snack':     ['snack', 'snacks', 'light bite', '零食', '小吃', '点心'],
}


def extract_constraints(query: str) -> ExtractedConstraints:
    """Strip numeric/meal constraints from query text, return cleaned query + constraints."""
    result: dict = {}
    q = query

    # Calorie patterns
    for pattern, kind in _CAL_PATTERNS:
        m = re.search(pattern, q, re.IGNORECASE)
        if m:
            if kind == 'range':
                result.setdefault('min_calories', int(m.group(1)))
                result.setdefault('max_calories', int(m.group(2)))
            elif kind == 'max':
                result.setdefault('max_calories', int(m.group(1)))
            else:
                result.setdefault('min_calories', int(m.group(1)))
            q = re.sub(pattern, ' ', q, flags=re.IGNORECASE)

    # Protein patterns
    for pattern, _ in _PROTEIN_PATTERNS:
        m = re.search(pattern, q, re.IGNORECASE)
        if m:
            result.setdefault('min_protein_g', float(m.group(1)))
            q = re.sub(pattern, ' ', q, flags=re.IGNORECASE)

    # Price patterns
    for pattern, _ in _PRICE_PATTERNS:
        m = re.search(pattern, q, re.IGNORECASE)
        if m:
            result.setdefault('max_price_rmb', float(m.group(1)))
            q = re.sub(pattern, ' ', q, flags=re.IGNORECASE)

    # Meal type (not stripped from query — useful for BM25 too)
    meal_type: Optional[str] = None
    for meal, keywords in _MEAL_KEYWORDS.items():
        if any(kw.lower() in q.lower() for kw in keywords):
            meal_type = meal
            break

    cleaned = re.sub(r'\s{2,}', ' ', q).strip()

    return ExtractedConstraints(
        min_calories=result.get('min_calories'),
        max_calories=result.get('max_calories'),
        min_protein_g=result.get('min_protein_g'),
        max_price_rmb=result.get('max_price_rmb'),
        meal_type=meal_type,
        cleaned_query=cleaned,
    )
