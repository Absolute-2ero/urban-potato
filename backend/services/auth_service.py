from __future__ import annotations

import logging
import uuid
from typing import Optional

from passlib.context import CryptContext

from database import get_pg
from models.user import User, UserCreate

logger = logging.getLogger(__name__)

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


async def register(payload: UserCreate) -> User:
    """注册新用户，用户名重复时抛 ValueError。"""
    pool = get_pg()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE username = $1", payload.username
        )
        if exists:
            raise ValueError(f"Username '{payload.username}' already taken")

        uid = str(uuid.uuid4())
        hashed = hash_password(payload.password)
        row = await conn.fetchrow(
            """
            INSERT INTO users (id, username, email, password_hash)
            VALUES ($1, $2, $3, $4)
            RETURNING id, username, email, created_at
            """,
            uid,
            payload.username,
            payload.email,
            hashed,
        )
    logger.info("Registered user %s (%s)", payload.username, uid)
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        created_at=row["created_at"],
    )


async def authenticate(username: str, password: str) -> Optional[User]:
    """验证用户名+密码，成功返回 User，失败返回 None。"""
    pool = get_pg()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, email, password_hash, created_at FROM users WHERE username = $1",
            username,
        )
    if row is None:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        created_at=row["created_at"],
    )


async def get_user_by_id(user_id: str) -> Optional[User]:
    pool = get_pg()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, username, email, created_at FROM users WHERE id = $1",
            user_id,
        )
    if row is None:
        return None
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        created_at=row["created_at"],
    )
