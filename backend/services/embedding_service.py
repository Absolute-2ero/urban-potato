"""
Embedding service — ZhipuAI embedding-2 (1024 dims, multilingual).
Used for semantic search (kNN) and personalization (user preference vector).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from config import cfg

logger = logging.getLogger(__name__)

_URL  = "https://open.bigmodel.cn/api/paas/v4/embeddings"
_MODEL = "embedding-2"
_DIMS  = 1024
_BATCH = 20  # ZhipuAI single-call limit

_svc: Optional["EmbeddingService"] = None


def get_embedding_service() -> "EmbeddingService":
    global _svc
    if _svc is None:
        _svc = EmbeddingService()
    return _svc


def restaurant_to_text(doc: Dict[str, Any]) -> str:
    """Serialize a restaurant document into a short text for embedding."""
    parts = []
    if doc.get("name"):
        parts.append(doc["name"])
    if doc.get("cuisine_type"):
        parts.append(doc["cuisine_type"])
    if doc.get("diet_labels"):
        labels = doc["diet_labels"]
        if isinstance(labels, list):
            parts.append(" ".join(labels))
    if doc.get("description"):
        parts.append(str(doc["description"])[:200])
    if doc.get("signature_dishes"):
        sd = doc["signature_dishes"]
        if isinstance(sd, list):
            parts.append(" ".join(str(s) for s in sd[:5]))
        else:
            parts.append(str(sd)[:100])
    if doc.get("tags"):
        t = doc["tags"]
        if isinstance(t, list):
            parts.append(" ".join(str(x) for x in t[:10]))
    return " ".join(parts).strip()


class EmbeddingService:
    def __init__(self) -> None:
        self._key = cfg.zhipu_api_key
        if not self._key:
            logger.warning("ZHIPU_API_KEY not set — semantic search disabled")

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    async def embed(self, text: str, timeout: float = 8.0) -> Optional[List[float]]:
        if not self.enabled or not text.strip():
            return None
        results = await self.embed_batch([text], timeout=timeout)
        return results[0] if results else None

    async def embed_batch(
        self,
        texts: List[str],
        timeout: float = 30.0,
    ) -> List[Optional[List[float]]]:
        if not self.enabled:
            return [None] * len(texts)

        results: List[Optional[List[float]]] = [None] * len(texts)
        for start in range(0, len(texts), _BATCH):
            chunk = texts[start : start + _BATCH]
            try:
                async with httpx.AsyncClient(trust_env=False) as client:
                    resp = await client.post(
                        _URL,
                        headers={"Authorization": f"Bearer {self._key}"},
                        json={"model": _MODEL, "input": chunk},
                        timeout=timeout,
                    )
                    resp.raise_for_status()
                    data = resp.json().get("data", [])
                    for item in data:
                        idx = item["index"]
                        results[start + idx] = item["embedding"]
            except Exception as exc:
                logger.warning("embed_batch chunk %d failed: %s", start, exc)
        return results

    async def embed_restaurant(self, doc: Dict[str, Any]) -> Optional[List[float]]:
        text = restaurant_to_text(doc)
        return await self.embed(text) if text else None

    @staticmethod
    def dims() -> int:
        return _DIMS
