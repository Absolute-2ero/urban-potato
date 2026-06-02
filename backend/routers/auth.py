from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from models.user import User, UserCreate, UserLogin
from services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, request: Request) -> User:
    try:
        user = await auth_service.register(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    # 注册成功后自动登录
    request.session["user_id"] = user.id
    return user


@router.post("/login", response_model=User)
async def login(payload: UserLogin, request: Request) -> User:
    user = await auth_service.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    request.session["user_id"] = user.id
    return user


@router.post("/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"message": "Logged out"}


@router.delete("/me")
async def delete_me(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    await auth_service.delete_user(user_id)
    request.session.clear()
    return {"message": "Account deleted"}


@router.get("/me", response_model=User)
async def me(request: Request) -> User:
    user_id: str | None = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = await auth_service.get_user_by_id(user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
