"""请求级依赖：解析 Bearer JWT，得到当前登录用户。"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.http.dependencies import get_db
from app.models.user import User
from app.services.auth_service import resolve_current_user

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> User:
    """FastAPI Depends：Authorization 缺失或无效时由 service 抛 AppError(40100)。"""
    token = creds.credentials if creds is not None else None
    return await resolve_current_user(db, token)
