from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

import jieba

from .synonyms import DietSynonymDict

logger = logging.getLogger(__name__)

_ZH_STOP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stopwords", "zh_stopwords.txt")
_EN_STOP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stopwords", "en_stopwords.txt")


def _load_stopwords(path: str) -> Set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


# 惰性加载（模块级变量）
_zh_stops: Optional[Set[str]] = None
_en_stops: Optional[Set[str]] = None


def _get_stops() -> tuple:
    global _zh_stops, _en_stops
    if _zh_stops is None:
        _zh_stops = _load_stopwords(_ZH_STOP_PATH)
    if _en_stops is None:
        _en_stops = _load_stopwords(_EN_STOP_PATH)
    return _zh_stops, _en_stops


def _detect_language(text: str) -> str:
    """简单语言检测：中文字符占比 > 30% 视为中文，否则英文/混合。"""
    zh_count = sum(1 for c in text if "一" <= c <= "鿿")
    return "zh" if zh_count / max(len(text), 1) > 0.3 else "en"


@dataclass
class ParsedQuery:
    original: str
    language: str
    tokens: List[str]
    expanded_tokens: List[str]         # 含同义词扩展后的词列表
    detected_diet_labels: List[str]    # 从查询中识别出的规范饮食标签
    spell_corrected: bool = False
    spell_suggestion: Optional[str] = None
    sort_mode: str = "default"


class QueryParser:
    def __init__(self, synonyms: DietSynonymDict) -> None:
        self.synonyms = synonyms

    def parse(self, raw_query: str, sort_mode: str = "default") -> ParsedQuery:
        query = raw_query.strip()
        lang = _detect_language(query)
        zh_stops, en_stops = _get_stops()

        # ── 分词 ──────────────────────────────────────────────────────────────
        if lang == "zh":
            tokens = [t for t in jieba.cut_for_search(query)
                      if t.strip() and t not in zh_stops]
        else:
            tokens = [t.lower() for t in re.split(r"[\s\-_,./]+", query)
                      if t.strip() and t.lower() not in en_stops]

        # ── 同义词扩展 + 饮食标签识别 ────────────────────────────────────────
        detected_labels: List[str] = []
        expanded: List[str] = []
        seen_canonical: Set[str] = set()

        for token in tokens:
            match = self.synonyms.match(token)
            if match:
                canonical, all_syns = match
                if canonical not in seen_canonical:
                    detected_labels.append(canonical)
                    seen_canonical.add(canonical)
                    expanded.extend(all_syns)
            else:
                expanded.append(token)

        # 去重保序
        seen: Set[str] = set()
        unique_expanded: List[str] = []
        for t in expanded:
            if t not in seen:
                seen.add(t)
                unique_expanded.append(t)

        return ParsedQuery(
            original=query,
            language=lang,
            tokens=tokens,
            expanded_tokens=unique_expanded,
            detected_diet_labels=list(dict.fromkeys(detected_labels)),
            sort_mode=sort_mode,
        )
