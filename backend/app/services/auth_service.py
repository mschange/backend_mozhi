"""鉴权业务：发 JWT、校验登录态、注册去重。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories import user as user_repository
from app.schemas.auth import LoginIn, RegisterIn, TokenBundle, UserOut
from app.utils.enums import ErrorCode, TokenType
from app.utils.exceptions import AppError


def issue_tokens(user: User) -> TokenBundle:
    """签发 access（短）+ refresh（长）以及当前用户信息。"""
    return TokenBundle(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


async def resolve_current_user(db: AsyncSession, token: str | None) -> User:
    """解码 access token 并查库；token 空/无效/用户已删都当未登录。"""
    if not token:
        raise AppError(ErrorCode.UNAUTHORIZED, "未授权，请先登录")
    user_id = decode_token(token, TokenType.ACCESS)
    user = await user_repository.get_by_id(db, user_id)
    if user is None:
        raise AppError(ErrorCode.UNAUTHORIZED, "未授权，请先登录")
    return user


async def register_user(db: AsyncSession, payload: RegisterIn) -> TokenBundle:
    """用户名、邮箱都不能重复，成功后直接发 token。"""
    if await user_repository.get_by_username(db, payload.username):
        raise AppError(ErrorCode.DUPLICATE_USER, "该用户已注册！")
    if await user_repository.get_by_email(db, str(payload.email)):
        raise AppError(ErrorCode.DUPLICATE_USER, "该邮箱已注册！")
    user = await user_repository.create(
        db,
        username=payload.username,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
    )
    return issue_tokens(user)


async def login_user(db: AsyncSession, payload: LoginIn) -> TokenBundle:
    """username 字段同时接受用户名或邮箱。"""
    user = await user_repository.get_by_username_or_email(db, payload.username)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError(ErrorCode.INVALID_CREDENTIALS, "用户名或密码错误")
    return issue_tokens(user)


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> dict:
    user_id = decode_token(refresh_token, TokenType.REFRESH)
    user = await user_repository.get_by_id(db, user_id)
    if user is None:
        raise AppError(ErrorCode.UNAUTHORIZED, "未授权，请先登录")
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }


def get_profile(user: User) -> UserOut:
    return UserOut.model_validate(user)
