"""用户表访问。函数都接收 db，不持有会话状态。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_id(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, user_id)


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    return await db.scalar(select(User).where(User.username == username))


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def get_by_username_or_email(db: AsyncSession, identity: str) -> User | None:
    """登录框同时支持用户名或邮箱。"""
    return await db.scalar(
        select(User).where((User.username == identity) | (User.email == identity))
    )


async def create(db: AsyncSession, username: str, email: str, password_hash: str) -> User:
    user = User(username=username, email=email, password_hash=password_hash)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
