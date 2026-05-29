from __future__ import annotations

import asyncio
import logging
import logging.config
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config import cfg
from database import (
    close_all,
    init_es,
    init_pg,
    init_redis,
    init_sqlite,
)
from db import init_sqlite_schema
from middleware.auth_middleware import RequestLogMiddleware
from routers import auth, cities, diet, feedback, food, internal, restaurants, search
from services.index_service import ensure_index
from services.search_service import init_search_components

# ── 日志配置 ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── 生命周期 ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting DietSearch backend...")

    # SQLite is always required
    await init_sqlite()
    from database import get_sqlite
    conn = get_sqlite()
    await init_sqlite_schema(conn)

    # PostgreSQL, Redis, Elasticsearch are optional for local dev
    try:
        await init_pg()
    except Exception as exc:
        logger.warning("PostgreSQL unavailable (%s) — skipping", exc)

    try:
        await init_redis()
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — caching disabled", exc)

    try:
        await init_es()
        await ensure_index()
    except Exception as exc:
        logger.warning("Elasticsearch unavailable (%s) — search degraded", exc)

    # 初始化搜索组件（同义词、解析器、排序器）
    init_search_components()

    logger.info("DietSearch backend started ✓")

    # ── 定时批量爬虫（每 60 分钟轮询一次）──────────────────────────────────────
    scheduler_task = asyncio.create_task(_scheduler_loop())

    yield

    # 清理
    logger.info("Shutting down...")
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    await close_all()
    logger.info("Shutdown complete")


async def _scheduler_loop() -> None:
    # Scheduled crawling disabled — run the pipeline manually:
    #   python -m crawler.pipeline --eleme --gemini
    pass


# ── 应用实例 ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DietSearch API",
    version="1.0.0",
    description="Diet-based restaurant search platform",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── 中间件 ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=cfg.session_secret,
    session_cookie="dietsearch_session",
    max_age=cfg.session_max_age,
    https_only=False,   # 开发环境 http；生产改为 True
    same_site="lax",
)

app.add_middleware(RequestLogMiddleware)

# ── 路由注册 ──────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(cities.router)
app.include_router(food.router)
app.include_router(diet.router)
app.include_router(search.router)
app.include_router(restaurants.router)
app.include_router(feedback.router)
app.include_router(internal.router)


# ── 健康检查 ──────────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}
