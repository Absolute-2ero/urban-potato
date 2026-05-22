from __future__ import annotations

import re
from typing import List, Optional


# 常见饮食词汇拼写词典（用于英文纠错）
_DIET_VOCAB = [
    "vegan", "vegetarian", "halal", "kosher", "organic",
    "gluten", "gluten-free", "dairy", "dairy-free", "lactose",
    "keto", "ketogenic", "protein", "high-protein", "low-carb",
    "calorie", "low-calorie", "sodium", "low-sodium",
    "nut-free", "shellfish", "soy-free",
    "restaurant", "food", "healthy", "diet",
]


def _edit_distance(a: str, b: str) -> int:
    """标准 Levenshtein 编辑距离。"""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[:]
        dp[0] = i
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev[j - 1] + cost)
    return dp[n]


def suggest_correction(token: str, max_dist: int = 2) -> Optional[str]:
    """
    对单个英文 token 给出拼写建议。
    返回编辑距离 ≤ max_dist 的最近词，否则返回 None。
    """
    token = token.lower()
    if token in _DIET_VOCAB:
        return None  # 已正确

    best_word: Optional[str] = None
    best_dist = max_dist + 1
    for word in _DIET_VOCAB:
        d = _edit_distance(token, word)
        if d < best_dist:
            best_dist = d
            best_word = word

    return best_word if best_dist <= max_dist else None


def check_query(query: str) -> Optional[str]:
    """
    检查整个英文查询，返回修正后的查询字符串（仅修正明显拼错的词），或 None。
    """
    tokens = re.split(r"(\s+)", query)
    corrections: List[tuple] = []
    for token in tokens:
        if not token.strip() or not token.isalpha():
            continue
        suggestion = suggest_correction(token)
        if suggestion:
            corrections.append((token, suggestion))

    if not corrections:
        return None

    corrected = query
    for original, fixed in corrections:
        corrected = re.sub(r"\b" + re.escape(original) + r"\b", fixed, corrected, flags=re.IGNORECASE)
    return corrected
