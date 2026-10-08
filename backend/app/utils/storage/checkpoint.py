"""LangGraph PostgreSQL checkpoint 的连接池生命周期与 thread 操作。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import (
    POSTGRES_POOL_MAX_SIZE,
    POSTGRES_POOL_MIN_SIZE,
    postgres_dsn,
)


def build_thread_id(user_id: str, conversation_id: str) -> str:
    """把用户和会话共同编码进稳定 thread id，避免 checkpoint 串线。"""
    return f"user:{user_id}:conversation:{conversation_id}"


@asynccontextmanager
async def checkpoint_lifespan() -> AsyncIterator[AsyncPostgresSaver]:
    """显式打开 pool、初始化 saver 表，并保证退出上下文时关闭 pool。"""
    pool = AsyncConnectionPool(
        conninfo=postgres_dsn(),
        min_size=POSTGRES_POOL_MIN_SIZE,
        max_size=POSTGRES_POOL_MAX_SIZE,
        # 禁止构造时隐式连接，确保所有启动失败都发生在可等待、可记录的 open() 阶段。
        open=False,
        kwargs={
            # saver 自己管理 checkpoint 写入，不复用 MySQL 的请求事务。
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    try:
        # wait=True 等到最小连接数就绪；数据库不可用时应用启动失败而不是延迟报错。
        await pool.open(wait=True)
        saver = AsyncPostgresSaver(pool)
        # setup() 幂等确保 LangGraph 所需表存在，不由 SQLAlchemy metadata 管理。
        await saver.setup()
        yield saver
    finally:
        # setup、运行期或应用关闭发生异常时都尝试归还并关闭 PostgreSQL 连接。
        await pool.close()


async def get_latest_checkpoint_id(
    saver: AsyncPostgresSaver,
    thread_id: str,
) -> str | None:
    """读取指定 thread 最新 checkpoint id；没有状态时返回 None。"""
    checkpoint = await saver.aget_tuple(
        {"configurable": {"thread_id": thread_id}}
    )
    if checkpoint is None:
        return None
    checkpoint_id = checkpoint.config.get("configurable", {}).get("checkpoint_id")
    return str(checkpoint_id) if checkpoint_id else None


async def delete_thread(saver: AsyncPostgresSaver, thread_id: str) -> None:
    """删除一个会话的图状态；业务消息仍由 MySQL 独立管理。"""
    await saver.adelete_thread(thread_id)
