from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from elasticsearch import AsyncElasticsearch

from database import get_es

logger = logging.getLogger(__name__)

_INDEX = "restaurants"
_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "es_mapping.json")


# ── ES 索引映射 ───────────────────────────────────────────────────────────────

_DEFAULT_MAPPING: Dict[str, Any] = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "ik_smart_analyzer": {
                    "type": "custom",
                    "tokenizer": "ik_smart",
                    "filter": ["lowercase"],
                },
                "ik_max_analyzer": {
                    "type": "custom",
                    "tokenizer": "ik_max_word",
                    "filter": ["lowercase"],
                },
            }
        },
    },
    "mappings": {
        "properties": {
            "restaurant_id":  {"type": "keyword"},
            "name":           {"type": "text", "analyzer": "ik_max_analyzer",
                               "search_analyzer": "ik_smart_analyzer",
                               "copy_to": "name_suggest"},
            "name_suggest":   {"type": "completion"},
            "description":    {"type": "text", "analyzer": "ik_smart_analyzer"},
            "cuisine_type":   {"type": "text", "analyzer": "ik_smart_analyzer",
                               "fields": {"keyword": {"type": "keyword"}}},
            "address":        {"type": "text", "analyzer": "ik_smart_analyzer"},
            "phone":          {"type": "keyword"},
            "price_level":    {"type": "integer"},
            "rating":         {"type": "float"},
            "rating_count":   {"type": "integer"},
            "geo": {
                "type": "geo_point",
                "properties": {
                    "lat": {"type": "double"},
                    "lng": {"type": "double"},
                },
            },
            "diet_labels":    {"type": "keyword"},
            "allergens":      {"type": "keyword"},
            "allergen_free":  {"type": "keyword"},
            "business_hours": {"type": "keyword"},
            "images":         {"type": "keyword", "index": False},
            "source":         {"type": "keyword"},
            "menu_items": {
                "type": "nested",
                "properties": {
                    "item_id":    {"type": "keyword"},
                    "name":       {"type": "text", "analyzer": "ik_max_analyzer"},
                    "price":      {"type": "float"},
                    "diet_labels":{"type": "keyword"},
                    "allergens":  {"type": "keyword"},
                    "calories":   {"type": "float"},
                },
            },
        }
    },
}


async def ensure_index() -> None:
    """确保 ES 索引存在（不存在则创建，存在则跳过）。"""
    es = get_es()

    # 尝试从文件读取自定义 mapping
    mapping = _DEFAULT_MAPPING
    if os.path.exists(_MAPPING_PATH):
        try:
            with open(_MAPPING_PATH, encoding="utf-8") as f:
                mapping = json.load(f)
            logger.info("Loaded ES mapping from %s", _MAPPING_PATH)
        except Exception as exc:
            logger.warning("Failed to load es_mapping.json, using default: %s", exc)

    exists = await es.indices.exists(index=_INDEX)
    if exists:
        logger.info("ES index '%s' already exists, skipping creation", _INDEX)
        return

    await es.indices.create(index=_INDEX, body=mapping)
    logger.info("Created ES index '%s'", _INDEX)


async def delete_index() -> None:
    es = get_es()
    exists = await es.indices.exists(index=_INDEX)
    if exists:
        await es.indices.delete(index=_INDEX)
        logger.info("Deleted ES index '%s'", _INDEX)


async def rebuild_index() -> None:
    """删除并重建索引（用于开发/测试）。"""
    await delete_index()
    await ensure_index()
    logger.info("ES index '%s' rebuilt", _INDEX)


async def bulk_index(documents: List[Dict[str, Any]]) -> int:
    """
    批量写入餐厅文档。
    documents: List of restaurant dicts with 'restaurant_id' field.
    返回成功索引的文档数。
    """
    if not documents:
        return 0

    es = get_es()
    actions: List[Dict] = []
    for doc in documents:
        rid = doc.get("restaurant_id") or doc.get("_id")
        if not rid:
            continue
        actions.append({"index": {"_index": _INDEX, "_id": rid}})
        # geo 字段: ES geo_point 用 lat/lon，但我们存的是 {lat, lng}
        # 转换 lng → lon
        if "geo" in doc and isinstance(doc["geo"], dict):
            g = doc["geo"]
            doc = dict(doc)
            doc["geo"] = {"lat": g.get("lat", 0), "lon": g.get("lng", 0)}
        actions.append(doc)

    resp = await es.bulk(operations=actions, refresh="wait_for")
    errors = [item for item in resp["items"] if "error" in item.get("index", {})]
    if errors:
        logger.warning("Bulk index had %d errors: %s", len(errors), errors[:3])

    success = len(documents) - len(errors)
    logger.info("Bulk indexed %d/%d documents into '%s'", success, len(documents), _INDEX)
    return success


async def index_restaurant(doc: Dict[str, Any]) -> None:
    """单条餐厅文档写入（upsert）。"""
    es = get_es()
    rid = doc.get("restaurant_id")
    if not rid:
        raise ValueError("document must have 'restaurant_id'")
    if "geo" in doc and isinstance(doc["geo"], dict):
        g = doc["geo"]
        doc = dict(doc)
        doc["geo"] = {"lat": g.get("lat", 0), "lon": g.get("lng", 0)}
    await es.index(index=_INDEX, id=rid, document=doc)
