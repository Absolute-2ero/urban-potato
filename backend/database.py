from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from typing import AsyncGenerator, Optional

import aiosqlite
import asyncpg
import redis.asyncio as aioredis
from elasticsearch import AsyncElasticsearch

from config import cfg

logger = logging.getLogger(__name__)

# ─── 全局连接对象 ──────────────────────────────────────────────────────────────
_pg_pool: Optional[asyncpg.Pool] = None
_sqlite_conn: Optional[aiosqlite.Connection] = None
_redis: Optional[aioredis.Redis] = None
_es: Optional[AsyncElasticsearch] = None


# ─── PostgreSQL ────────────────────────────────────────────────────────────────
async def init_postgres() -> None:
    global _pg_pool
    _pg_pool = await asyncpg.create_pool(
        cfg.postgres_dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("PostgreSQL pool created")


async def close_postgres() -> None:
    if _pg_pool:
        await _pg_pool.close()


def get_pg() -> asyncpg.Pool:
    assert _pg_pool is not None, "PostgreSQL pool not initialised"
    return _pg_pool


# ─── SQLite（食物数据库）─────────────────────────────────────────────────────
async def init_sqlite() -> None:
    global _sqlite_conn
    db_path = cfg.sqlite_path
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    _sqlite_conn = await aiosqlite.connect(db_path)
    _sqlite_conn.row_factory = aiosqlite.Row
    await _sqlite_conn.execute("PRAGMA journal_mode=WAL")
    await _sqlite_conn.execute("PRAGMA foreign_keys=ON")
    await _sqlite_conn.commit()
    logger.info("SQLite connected: %s", db_path)


async def close_sqlite() -> None:
    if _sqlite_conn:
        await _sqlite_conn.close()


def get_sqlite() -> aiosqlite.Connection:
    assert _sqlite_conn is not None, "SQLite not initialised"
    return _sqlite_conn


# ─── Redis ────────────────────────────────────────────────────────────────────
async def init_redis() -> None:
    global _redis
    _redis = await aioredis.from_url(cfg.redis_url, decode_responses=True)
    await _redis.ping()
    logger.info("Redis connected")


async def close_redis() -> None:
    if _redis:
        await _redis.aclose()


def get_redis() -> aioredis.Redis:
    assert _redis is not None, "Redis not initialised"
    return _redis


# ─── Elasticsearch ────────────────────────────────────────────────────────────
async def init_elasticsearch() -> None:
    global _es
    _es = AsyncElasticsearch([cfg.elasticsearch_url])
    info = await _es.info()
    logger.info("Elasticsearch connected: %s", info["version"]["number"])


async def close_elasticsearch() -> None:
    if _es:
        await _es.close()


def get_es() -> AsyncElasticsearch:
    assert _es is not None, "Elasticsearch not initialised"
    return _es


# ─── 函数别名（供 main.py 等使用简短名称）────────────────────────────────────
init_pg = init_postgres
init_es = init_elasticsearch


# ─── 统一关闭 ─────────────────────────────────────────────────────────────────
async def close_all() -> None:
    await asyncio.gather(
        close_postgres(),
        close_sqlite(),
        close_redis(),
        close_elasticsearch(),
        return_exceptions=True,
    )
