from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SYNONYM_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "diet_synonyms.json")


class DietSynonymDict:
    """饮食同义词词典：原始词 → (规范标签, [所有同义词含规范标签])"""

    def __init__(self, mapping: Dict[str, List[str]]) -> None:
        # mapping: { canonical_label: [synonym1, synonym2, ...] }
        self._lookup: Dict[str, Tuple[str, List[str]]] = {}
        for canonical, synonyms in mapping.items():
            all_forms = [canonical] + synonyms
            for form in all_forms:
                self._lookup[form.lower()] = (canonical, all_forms)

    def match(self, token: str) -> Optional[Tuple[str, List[str]]]:
        """返回 (canonical_label, [all_synonyms]) 或 None。"""
        return self._lookup.get(token.lower())

    def contains(self, token: str) -> bool:
        return token.lower() in self._lookup

    @classmethod
    def load(cls, path: Optional[str] = None) -> "DietSynonymDict":
        p = os.path.normpath(path or _SYNONYM_PATH)
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Loaded diet synonym dict: %d canonical labels", len(data))
        return cls(data)
