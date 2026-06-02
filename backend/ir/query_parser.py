from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import jieba

from .constraint_extractor import ExtractedConstraints, extract_constraints
from .landmarks import find_landmark
from .synonyms import DietSynonymDict

logger = logging.getLogger(__name__)

_ZH_STOP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stopwords", "zh_stopwords.txt")
_EN_STOP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stopwords", "en_stopwords.txt")
_CUISINE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cuisine_synonyms.json")


def _load_stopwords(path: str) -> Set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.strip().lower() for line in f if line.strip()}


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
    zh_count = sum(1 for c in text if "一" <= c <= "鿿")
    return "zh" if zh_count / max(len(text), 1) > 0.3 else "en"


def _has_cjk(s: str) -> bool:
    return any("一" <= c <= "鿿" for c in s)


def _phrase_in(phrase: str, text: str) -> bool:
    """Word-boundary-aware phrase match. CJK phrases use simple containment."""
    if _has_cjk(phrase):
        return phrase in text
    return bool(re.search(r"\b" + re.escape(phrase) + r"\b", text, re.IGNORECASE))


def _remove_phrase(phrase: str, text: str) -> str:
    if _has_cjk(phrase):
        return text.replace(phrase, " ")
    return re.sub(r"\b" + re.escape(phrase) + r"\b", " ", text, flags=re.IGNORECASE)


@dataclass
class ParsedQuery:
    original: str
    language: str
    tokens: List[str]
    expanded_tokens: List[str]
    detected_diet_labels: List[str]
    free_text_tokens: List[str] = field(default_factory=list)
    spell_corrected: bool = False
    spell_suggestion: Optional[str] = None
    sort_mode: str = "default"
    extracted_constraints: Optional[ExtractedConstraints] = None
    detected_cuisine_type: Optional[str] = None
    landmark_geo: Optional[Tuple[float, float]] = None
    landmark_name: Optional[str] = None


class QueryParser:
    def __init__(self, synonyms: DietSynonymDict) -> None:
        self.synonyms = synonyms

        # Build sorted phrase list from all synonym forms (longest first).
        # _lookup maps every form → (canonical, all_forms).
        self._phrase_synonyms: List[Tuple[str, str]] = []
        for phrase, (canonical, _) in self.synonyms._lookup.items():
            self._phrase_synonyms.append((phrase, canonical))
        self._phrase_synonyms.sort(key=lambda x: len(x[0]), reverse=True)

        # Load cuisine synonyms and build sorted phrase list.
        self._cuisine_synonyms: Dict[str, List[str]] = {}
        if os.path.exists(_CUISINE_PATH):
            with open(_CUISINE_PATH, encoding="utf-8") as f:
                self._cuisine_synonyms = json.load(f)

        self._cuisine_phrases: List[Tuple[str, str]] = []
        for cuisine, phrases in self._cuisine_synonyms.items():
            for phrase in phrases:
                self._cuisine_phrases.append((phrase.lower(), cuisine))
        self._cuisine_phrases.sort(key=lambda x: len(x[0]), reverse=True)

    def parse(self, raw_query: str, sort_mode: str = "default") -> ParsedQuery:
        query = raw_query.strip()

        # ── 1. Numeric constraint extraction ────────────────────────────────
        constraints = extract_constraints(query)
        working = constraints.cleaned_query

        lang = _detect_language(working or query)
        zh_stops, en_stops = _get_stops()

        # ── 2. Phrase-level diet label detection ─────────────────────────────
        # Scan before tokenisation so multi-word/hyphenated synonyms match.
        detected_labels: List[str] = []
        seen_canonical: Set[str] = set()
        for phrase, canonical in self._phrase_synonyms:
            if _phrase_in(phrase, working):
                if canonical not in seen_canonical:
                    detected_labels.append(canonical)
                    seen_canonical.add(canonical)
                working = _remove_phrase(phrase, working)

        # ── 3. Cuisine phrase detection ──────────────────────────────────────
        # Strip the trigger phrase; inject canonical name as a BM25 token so
        # it hits cuisine_type^2 in the multi_match (handles "Asian, Singaporean"
        # etc. via soft scoring rather than a fragile exact-term filter).
        detected_cuisine_type: Optional[str] = None
        cuisine_inject: Optional[str] = None
        for phrase, cuisine in self._cuisine_phrases:
            if _phrase_in(phrase, working):
                detected_cuisine_type = cuisine
                cuisine_inject = cuisine.replace("_", " ")  # "middle_eastern" → "middle eastern"
                working = _remove_phrase(phrase, working)
                break

        # ── 4. Tokenise the remaining free text ──────────────────────────────
        working = re.sub(r"\s{2,}", " ", working).strip()
        if lang == "zh":
            tokens = [
                t for t in jieba.cut_for_search(working)
                if t.strip() and t not in zh_stops
            ]
        else:
            tokens = [
                t.lower()
                for t in re.split(r"[\s\-_,./]+", working)
                if t.strip() and t.lower() not in en_stops
            ]

        # ── 5. Landmark detection ────────────────────────────────────────────
        landmark_geo: Optional[Tuple[float, float]] = None
        landmark_name: Optional[str] = None
        result = find_landmark(tokens)
        if result:
            landmark_name, landmark_geo = result
            landmark_words = set(landmark_name.lower().split())
            tokens = [t for t in tokens if t not in landmark_words]

        # ── 6. Single-token diet matching on remaining tokens ────────────────
        # Catch any diet terms that weren't multi-word (should be rare now).
        free_text: List[str] = []
        for token in tokens:
            match = self.synonyms.match(token)
            if match:
                canonical, _ = match
                if canonical not in seen_canonical:
                    detected_labels.append(canonical)
                    seen_canonical.add(canonical)
            else:
                free_text.append(token)

        # Inject cuisine name as BM25 token (hits cuisine_type^2 in multi_match).
        if cuisine_inject:
            for word in cuisine_inject.split():
                if word not in free_text:
                    free_text.append(word)

        return ParsedQuery(
            original=query,
            language=lang,
            tokens=tokens,
            expanded_tokens=free_text,
            detected_diet_labels=list(dict.fromkeys(detected_labels)),
            free_text_tokens=free_text,
            sort_mode=sort_mode,
            extracted_constraints=constraints,
            detected_cuisine_type=detected_cuisine_type,
            landmark_geo=landmark_geo,
            landmark_name=landmark_name,
        )
