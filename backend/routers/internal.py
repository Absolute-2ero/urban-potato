from __future__ import annotations

"""
内部管理接口（不暴露给前端，仅供运维/开发使用）。
生产环境应通过 nginx 限制只允许 127.0.0.1 访问 /internal/*。
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from services import index_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"])


class BulkIndexRequest(BaseModel):
    documents: List[Dict[str, Any]]


@router.post("/index/rebuild")
async def rebuild_index() -> dict:
    """删除并重建 ES 索引（开发/测试用）。"""
    await index_service.rebuild_index()
    return {"message": "Index rebuilt"}


@router.post("/index/ensure")
async def ensure_index() -> dict:
    await index_service.ensure_index()
    return {"message": "Index ensured"}


@router.post("/index/bulk")
async def bulk_index(payload: BulkIndexRequest) -> dict:
    count = await index_service.bulk_index(payload.documents)
    return {"indexed": count}
