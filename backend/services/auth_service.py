from __future__ import annotations

import logging
from typing import Optional

from passlib.context import CryptContext

from database import get_sqlite
from models.user import User, UserCreate

logger = logging.getLogger(__name__)

_pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


async def register(payload: UserCreate) -> User:
    db = get_sqlite()
    async with db.execute("SELECT 1 FROM users WHERE username = ?", (payload.username,)) as cur:
        exists = await cur.fetchone()
    if exists:
        raise ValueError(f"Username '{payload.username}' already taken")

    hashed = hash_password(payload.password)
    async with db.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (payload.username, payload.email, hashed),
    ) as cur:
        uid = cur.lastrowid
    await db.commit()

    async with db.execute(
        "SELECT id, username, email, created_at FROM users WHERE id = ?", (uid,)
    ) as cur:
        row = await cur.fetchone()

    logger.info("Registered user %s (id=%s)", payload.username, uid)
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        created_at=row["created_at"],
    )


async def authenticate(username: str, password: str) -> Optional[User]:
    db = get_sqlite()
    async with db.execute(
        "SELECT id, username, email, password_hash, created_at FROM users WHERE username = ?",
        (username,),
    ) as cur:
        row = await cur.fetchone()
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


async def delete_user(user_id) -> None:
    db = get_sqlite()
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()
    logger.info("Deleted user id=%s", user_id)


async def get_user_by_id(user_id) -> Optional[User]:
    db = get_sqlite()
    async with db.execute(
        "SELECT id, username, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        created_at=row["created_at"],
    )
