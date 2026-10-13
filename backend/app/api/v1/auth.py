"""鉴权接口：注册 / 登录 / 刷新 access token / 当前用户。"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginIn, RefreshIn, RegisterIn
from app.services.auth_service import get_profile, login_user, refresh_access_token, register_user
from app.utils.http.dependencies import get_db
from app.utils.http.response import success_response

router = APIRouter(prefix="/api/auth", tags=["鉴权"])


@router.post("/register")
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db, scope="function")):
    data = await register_user(db, body)
    return success_response(message="注册成功", data=data)


@router.post("/login")
async def login(body: LoginIn, db: AsyncSession = Depends(get_db, scope="function")):
    data = await login_user(db, body)
    return success_response(message="登录成功", data=data)


@router.post("/refresh")
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db, scope="function")):
    data = await refresh_access_token(db, body.refresh_token)
    return success_response(message="刷新成功", data=data)


@router.get("/me")
async def me(current: User = Depends(get_current_user)):
    return success_response(message="获取成功", data=get_profile(current))
