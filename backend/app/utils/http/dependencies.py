"""应用级请求依赖。"""

from collections.abc import AsyncGenerator

from fastapi import Request
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.storage.mysql import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """为普通 HTTP 请求提供统一事务边界。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_checkpointer(request: Request) -> AsyncPostgresSaver:
    return request.app.state.checkpointer
