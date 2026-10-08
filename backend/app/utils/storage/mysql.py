"""MySQL 异步引擎、session 工厂与应用生命周期操作。"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import mysql_async_dsn
from app.models.base import Base

# engine 是进程级对象。echo=False 避免把 SQL 参数和潜在用户数据写入普通日志。
async_engine = create_async_engine(
    mysql_async_dsn(),
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# autoflush=False 让 service/repository 明确决定 flush 时机；
# expire_on_commit=False 保证提交后仍可序列化刚写入的 ORM 对象。
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def init_mysql() -> None:
    """注册全部模型并按 metadata 建表；已有表跳过，连接或 DDL 失败会中止启动。"""
    # 导入的副作用是让六个 ORM 模型注册进同一个 Base.metadata。
    import app.models  # noqa: F401

    # begin() 为启动 DDL 提供连接事务，run_sync 桥接 SQLAlchemy 同步 metadata API。
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_mysql() -> None:
    """关闭连接池中的连接；不删除表，也不改变已提交业务数据。"""
    await async_engine.dispose()
