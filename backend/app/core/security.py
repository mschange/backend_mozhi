"""JWT 与密码。access 默认 30 分钟，refresh 默认 7 天。"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET, REFRESH_TOKEN_EXPIRE_DAYS
from app.utils.enums import ErrorCode, TokenType
from app.utils.exceptions import AppError


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _encode(user_id: str, token_type: str, delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "token_type": token_type,
        "iat": now,
        "exp": now + delta,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str) -> str:
    return _encode(
        user_id,
        TokenType.ACCESS,
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    return _encode(
        user_id,
        TokenType.REFRESH,
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str) -> str:
    """校验签名、过期和 token_type，返回 user_id（payload.sub）。"""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise AppError(ErrorCode.TOKEN_EXPIRED, "登录已过期，请重新登录") from exc
    except InvalidTokenError as exc:
        raise AppError(ErrorCode.INVALID_TOKEN, "无效的访问令牌") from exc

    if payload.get("token_type") != expected_type:
        raise AppError(ErrorCode.INVALID_TOKEN, "无效的访问令牌")
    user_id = payload.get("sub")
    if not user_id:
        raise AppError(ErrorCode.INVALID_TOKEN, "无效的访问令牌")
    return str(user_id)
