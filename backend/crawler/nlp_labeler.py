from __future__ import annotations

"""
NLP 饮食标签推断器：
  - 基于名称、描述、标签字段的关键词匹配
  - 使用 diet_synonyms.json 做规范化
  - 推断过敏原
"""

import logging
import re
from typing import Any, Dict, List, Tuple

from ir.synonyms import DietSynonymDict

logger = logging.getLogger(__name__)

# 懒加载
_synonyms: DietSynonymDict | None = None


def _get_synonyms() -> DietSynonymDict:
    global _synonyms
    if _synonyms is None:
        _synonyms = DietSynonymDict.load()
    return _synonyms


# ── 过敏原关键词映射 ──────────────────────────────────────────────────────────
_ALLERGEN_PATTERNS: List[Tuple[str, str]] = [
    (r"花生|peanut", "peanut"),
    (r"坚果|核桃|腰果|杏仁|nut", "tree_nut"),
    (r"牛奶|乳制品|奶酪|cheese|dairy|milk|lactose", "dairy"),
    (r"麸质|小麦|面筋|gluten|wheat", "gluten"),
    (r"海鲜|虾|蟹|贝类|shellfish|shrimp|crab", "shellfish"),
    (r"大豆|豆腐|soy|tofu", "soy"),
    (r"鸡蛋|egg", "egg"),
    (r"芝麻|sesame", "sesame"),
]

# ── 无xx声明模式 ──────────────────────────────────────────────────────────────
_ALLERGEN_FREE_PATTERNS: List[Tuple[str, str]] = [
    (r"无花生|不含花生|peanut.free", "peanut"),
    (r"无麸质|无小麦|gluten.free", "gluten"),
    (r"无乳糖|无奶|dairy.free|lactose.free", "dairy"),
    (r"无大豆|soy.free", "soy"),
    (r"无坚果|nut.free", "tree_nut"),
]

# ── 饮食标签关键词（补充同义词词典之外的规则）────────────────────────────────
_DIET_LABEL_PATTERNS: List[Tuple[str, str]] = [
    (r"纯素|全素|vegan|植物性|plant.based", "vegan"),
    (r"素食|vegetarian|素", "vegetarian"),
    (r"清真|halal|穆斯林", "halal"),
    (r"犹太|kosher", "kosher"),
    (r"有机|organic", "organic"),
    (r"无麸质|gluten.free", "gluten-free"),
    (r"无乳|dairy.free|lactose.free", "dairy-free"),
    (r"生酮|keto|ketogenic", "keto"),
    (r"高蛋白|high.protein", "high-protein"),
    (r"低碳|low.carb", "low-carb"),
    (r"低卡|低热量|low.cal", "low-calorie"),
    (r"低钠|low.sodium", "low-sodium"),
    (r"无坚果|nut.free", "nut-free"),
    (r"无贝类|shellfish.free", "shellfish-free"),
    (r"无大豆|soy.free", "soy-free"),
]


def _extract_from_text(text: str, patterns: List[Tuple[str, str]]) -> List[str]:
    found: List[str] = []
    text_lower = text.lower()
    for pattern, label in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            if label not in found:
                found.append(label)
    return found


def label_restaurant(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    对规范化后的餐厅文档推断 diet_labels、allergens、allergen_free。
    直接修改传入 dict 并返回。
    """
    combined_text = " ".join(
        filter(
            None,
            [
                doc.get("name", ""),
                doc.get("description", ""),
                doc.get("cuisine_type", ""),
                " ".join(doc.get("tags", [])),
            ],
        )
    )

    # 从菜品信息追加文本
    for item in doc.get("menu_items", []):
        combined_text += " " + item.get("name", "")

    diet_labels = list(set(
        doc.get("diet_labels", [])
        + _extract_from_text(combined_text, _DIET_LABEL_PATTERNS)
    ))
    allergens = list(set(
        doc.get("allergens", [])
        + _extract_from_text(combined_text, _ALLERGEN_PATTERNS)
    ))
    allergen_free = list(set(
        doc.get("allergen_free", [])
        + _extract_from_text(combined_text, _ALLERGEN_FREE_PATTERNS)
    ))

    # 从 allergen_free 中移除实际存在于 allergens 的（数据一致性）
    allergen_free = [af for af in allergen_free if af not in allergens]

    doc["diet_labels"] = diet_labels
    doc["allergens"] = allergens
    doc["allergen_free"] = allergen_free
    return doc


def label_batch(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [label_restaurant(doc) for doc in docs]
