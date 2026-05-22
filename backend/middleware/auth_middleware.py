from __future__ import annotations

"""
轻量级请求日志中间件（认证状态由 session cookie 在各 router 内校验）。
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        uid = request.session.get("user_id", "-") if hasattr(request, "session") else "-"
        logger.info(
            "%s %s %d %.1fms user=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            uid,
        )
        return response
