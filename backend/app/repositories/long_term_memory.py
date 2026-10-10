"""长期记忆事实与 Milvus 索引状态访问。"""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.long_term_memory import LongTermMemory


async def get_by_hash(
    db: AsyncSession,
    user_id: str,
    content_hash: str,
) -> LongTermMemory | None:
    stmt = select(LongTermMemory).where(
        LongTermMemory.user_id == user_id,
        LongTermMemory.content_hash == content_hash,
    )
    return await db.scalar(stmt)


async def get_owned(
    db: AsyncSession,
    memory_id: str,
    user_id: str,
) -> LongTermMemory | None:
    stmt = select(LongTermMemory).where(
        LongTermMemory.id == memory_id,
        LongTermMemory.user_id == user_id,
    )
    return await db.scalar(stmt)


async def get_or_create(
    db: AsyncSession,
    user_id: str,
    content: str,
    content_hash: str,
) -> tuple[LongTermMemory, bool]:
    memory_id = str(uuid4())
    insert_stmt = mysql_insert(LongTermMemory).values(
        id=memory_id,
        user_id=user_id,
        content=content,
        content_hash=content_hash,
        index_status="pending",
    )
    await db.execute(
        insert_stmt.on_duplicate_key_update(id=LongTermMemory.id)
    )
    select_stmt = (
        select(LongTermMemory)
        .where(
            LongTermMemory.user_id == user_id,
            LongTermMemory.content_hash == content_hash,
        )
        .with_for_update()
    )
    memory = await db.scalar(select_stmt)
    if memory is None:
        raise RuntimeError("长期记忆写入后无法读取")
    return memory, memory.id == memory_id


async def list_retryable(
    db: AsyncSession,
    user_id: str,
    limit: int = 10,
) -> list[LongTermMemory]:
    stmt = (
        select(LongTermMemory)
        .where(
            LongTermMemory.user_id == user_id,
            LongTermMemory.index_status.in_(("pending", "failed")),
        )
        .order_by(LongTermMemory.updated_at.asc())
        .limit(limit)
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def list_ready(
    db: AsyncSession,
    user_id: str,
    limit: int = 100,
) -> list[LongTermMemory]:
    stmt = (
        select(LongTermMemory)
        .where(
            LongTermMemory.user_id == user_id,
            LongTermMemory.index_status == "ready",
        )
        .order_by(LongTermMemory.updated_at.desc())
        .limit(limit)
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def get_owned_by_ids(
    db: AsyncSession,
    user_id: str,
    memory_ids: list[str],
) -> list[LongTermMemory]:
    if not memory_ids:
        return []
    stmt = select(LongTermMemory).where(
        LongTermMemory.user_id == user_id,
        LongTermMemory.id.in_(memory_ids),
        LongTermMemory.index_status == "ready",
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def mark_ready(db: AsyncSession, memory: LongTermMemory) -> None:
    memory.index_status = "ready"
    memory.error_message = None
    db.add(memory)
    await db.flush()


async def mark_failed(
    db: AsyncSession,
    memory: LongTermMemory,
    error_message: str,
) -> None:
    memory.index_status = "failed"
    memory.error_message = error_message[:2000]
    db.add(memory)
    await db.flush()
