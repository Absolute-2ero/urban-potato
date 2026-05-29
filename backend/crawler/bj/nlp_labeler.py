from __future__ import annotations

"""
NLP 饮食标签推断器（关键词匹配阶段）。

在 Gemini API 分析每道菜之前，先用正则对餐厅整体信息做快速、免费的预标注：
  - 餐厅名称、分类、标签、区域、菜单菜品名称
  - 推断 diet_labels（vegan/vegetarian/halal 等）
  - 推断 allergens（花生/麸质/乳制品等）
  - 推断 allergen_free 声明

结果写回 doc，后续 Gemini 在此基础上补充更细粒度的菜品级标签。
"""

import logging
import re
from typing import Any, Dict, List, Tuple

from ir.synonyms import DietSynonymDict

logger = logging.getLogger(__name__)

_synonyms: DietSynonymDict | None = None


def _get_synonyms() -> DietSynonymDict:
    global _synonyms
    if _synonyms is None:
        _synonyms = DietSynonymDict.load()
    return _synonyms


# ── 饮食标签关键词 ─────────────────────────────────────────────────────────────
_DIET_PATTERNS: List[Tuple[str, str]] = [
    (r"纯素|全素|vegan|植物性|plant.based|植物基",           "vegan"),
    (r"素食|素菜|vegetarian|吃素|斋菜|佛家|佛教",            "vegetarian"),
    (r"清真|halal|穆斯林|回族|真主",                         "halal"),
    (r"犹太|kosher",                                          "kosher"),
    (r"有机|organic|绿色食品",                                "organic"),
    (r"无麸质|gluten.free|无小麦",                            "gluten-free"),
    (r"无乳糖|dairy.free|lactose.free|无奶",                  "dairy-free"),
    (r"生酮|keto|ketogenic|低碳高脂",                         "keto"),
    (r"高蛋白|high.protein",                                  "high-protein"),
    (r"低碳水|低碳|low.carb",                                 "low-carb"),
    (r"低卡|低热量|low.cal|减脂|控卡",                        "low-calorie"),
    (r"低钠|low.sodium|少盐|减盐",                            "low-sodium"),
    (r"无坚果|nut.free",                                      "nut-free"),
    (r"无贝类|shellfish.free",                                "shellfish-free"),
    (r"无大豆|soy.free",                                      "soy-free"),
    (r"轻食|健康餐|沙拉|轻卡|减肥餐|健身餐",                  "light-meal"),
]

# ── 过敏原关键词 ───────────────────────────────────────────────────────────────
_ALLERGEN_PATTERNS: List[Tuple[str, str]] = [
    (r"花生|peanut",                                         "peanut"),
    (r"坚果|核桃|腰果|杏仁|开心果|榛子|nut",                 "tree_nut"),
    (r"牛奶|乳制品|奶酪|芝士|cheese|dairy|milk|lactose|黄油|cream", "dairy"),
    (r"麸质|小麦|面筋|gluten|wheat|面粉",                    "gluten"),
    (r"海鲜|虾|蟹|贝类|shellfish|shrimp|crab|龙虾|扇贝",     "shellfish"),
    (r"大豆|豆腐|豆浆|soy|tofu|黄豆",                        "soy"),
    (r"鸡蛋|蛋液|蛋黄|egg",                                   "egg"),
    (r"芝麻|sesame|麻酱|tahini",                              "sesame"),
    (r"鱼|三文鱼|金枪鱼|鲑鱼|fish|salmon|tuna",              "fish"),
]

# ── 无xx声明 ──────────────────────────────────────────────────────────────────
_ALLERGEN_FREE_PATTERNS: List[Tuple[str, str]] = [
    (r"无花生|不含花生|peanut.free",        "peanut"),
    (r"无麸质|无小麦|gluten.free",           "gluten"),
    (r"无乳糖|无奶|dairy.free|lactose.free", "dairy"),
    (r"无大豆|soy.free",                     "soy"),
    (r"无坚果|nut.free",                     "tree_nut"),
    (r"无鸡蛋|egg.free",                     "egg"),
]

# ── 菜系 → 饮食标签推断 ───────────────────────────────────────────────────────
# 如果 cuisine_type 或 typecode 命中这些，直接加对应标签
_CUISINE_DIET_MAP: List[Tuple[str, str]] = [
    (r"素食|素菜馆|纯素",         "vegetarian"),
    (r"清真",                      "halal"),
    (r"有机",                      "organic"),
]


def _match(text: str, patterns: List[Tuple[str, str]]) -> List[str]:
    found: List[str] = []
    t = text.lower()
    for pattern, label in patterns:
        if re.search(pattern, t, re.IGNORECASE) and label not in found:
            found.append(label)
    return found


def _build_text(doc: Dict[str, Any]) -> str:
    """把餐厅所有文本字段拼成一个大字符串供正则匹配。"""
    parts = [
        doc.get("name", ""),
        doc.get("cuisine_type", ""),
        doc.get("biz_type", ""),
        doc.get("district", ""),
        " ".join(doc.get("tags", [])),
    ]
    # 菜单菜品名
    for item in doc.get("menu_items", []):
        parts.append(item.get("name", ""))
        parts.append(item.get("description", "") or "")
    return " ".join(p for p in parts if p)


def label_restaurant(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    对规范化餐厅文档推断 diet_labels、allergens、allergen_free。
    直接修改传入 dict 并返回。
    """
    text = _build_text(doc)

    # 菜系直接推断（比正文关键词更可靠）
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

    # 一致性：allergen_free 不能与 allergens 重叠
    allergen_free = [a for a in allergen_free if a not in allergens]

    # vegan 隐含 vegetarian
    if "vegan" in diet_labels and "vegetarian" not in diet_labels:
        diet_labels.append("vegetarian")

    doc["diet_labels"]   = diet_labels
    doc["allergens"]     = allergens
    doc["allergen_free"] = allergen_free
    return doc


def label_batch(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [label_restaurant(doc) for doc in docs]
