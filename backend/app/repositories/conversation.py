"""会话与消息表访问。API 叫 chat，表名仍是 conversations / messages。"""

from datetime import datetime, timezone

from sqlalchemy import delete as sql_delete
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.conversation_checkpoint import ConversationCheckpoint
from app.models.message import Message


async def create(db: AsyncSession, user_id: str, title: str) -> Conversation:
    conv = Conversation(user_id=user_id, title=title)
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


async def list_by_user(db: AsyncSession, user_id: str) -> list[tuple[Conversation, int]]:
    count_sub = (
        select(Message.conversation_id, func.count(Message.id).label("message_count"))
        .group_by(Message.conversation_id)
        .subquery()
    )
    stmt = (
        select(Conversation, func.coalesce(count_sub.c.message_count, 0))
        .outerjoin(count_sub, count_sub.c.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    return [(row[0], int(row[1] or 0)) for row in result.all()]


async def find_empty(db: AsyncSession, user_id: str) -> Conversation | None:
    """找该用户最新一条还没有任何消息的会话，用于「新建」复用。"""
    has_message = exists().where(Message.conversation_id == Conversation.id)
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id, ~has_message)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    return await db.scalar(stmt)


async def delete(db: AsyncSession, conv: Conversation) -> None:
    """先删同步水位和消息，再删会话。"""
    await delete_checkpoint(db, conv.id)
    await db.execute(sql_delete(Message).where(Message.conversation_id == conv.id))
    await db.execute(sql_delete(Conversation).where(Conversation.id == conv.id))
    await db.flush()


async def get_owned_with_messages(
    db: AsyncSession, conversation_id: str, user_id: str
) -> Conversation | None:
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    return await db.scalar(stmt)


async def get_owned(db: AsyncSession, conversation_id: str, user_id: str) -> Conversation | None:
    """带归属校验，防止用别人的 chat_id 读写。"""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user_id
    )
    return await db.scalar(stmt)


async def get_owned_for_update(
    db: AsyncSession,
    conversation_id: str,
    user_id: str,
) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        .with_for_update()
    )
    return await db.scalar(stmt)


async def get_checkpoint(
    db: AsyncSession,
    conversation_id: str,
) -> ConversationCheckpoint | None:
    return await db.get(ConversationCheckpoint, conversation_id)


async def set_checkpoint(
    db: AsyncSession,
    conversation_id: str,
    thread_id: str,
    checkpoint_id: str,
    last_message_id: str,
    message_count: int,
) -> ConversationCheckpoint:
    watermark = await get_checkpoint(db, conversation_id)
    if watermark is None:
        watermark = ConversationCheckpoint(conversation_id=conversation_id)
    watermark.thread_id = thread_id
    watermark.checkpoint_id = checkpoint_id
    watermark.last_message_id = last_message_id
    watermark.message_count = message_count
    db.add(watermark)
    await db.flush()
    return watermark


async def delete_checkpoint(db: AsyncSession, conversation_id: str) -> None:
    await db.execute(
        sql_delete(ConversationCheckpoint).where(
            ConversationCheckpoint.conversation_id == conversation_id
        )
    )
    await db.flush()


async def message_count(db: AsyncSession, conversation_id: str) -> int:
    stmt = select(func.count(Message.id)).where(
        Message.conversation_id == conversation_id
    )
    return int(await db.scalar(stmt) or 0)


async def contains_message(
    db: AsyncSession,
    conversation_id: str,
    message_id: str,
) -> bool:
    stmt = select(
        exists().where(
            Message.id == message_id,
            Message.conversation_id == conversation_id,
        )
    )
    return bool(await db.scalar(stmt))


async def touch(db: AsyncSession, conv: Conversation) -> None:
    conv.updated_at = datetime.now(timezone.utc)
    db.add(conv)


async def update_title(db: AsyncSession, conv: Conversation, title: str) -> Conversation:
    conv.title = title
    conv.updated_at = datetime.now(timezone.utc)
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


async def add_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    citations: str | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        citations=citations,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    return msg


async def recent_messages(db: AsyncSession, conversation_id: str, limit: int) -> list[Message]:
    """取最近 limit 条后反转成时间正序，正好作为 Agent 上下文。"""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    result = await db.scalars(stmt)
    rows = list(result.all())
    rows.reverse()
    return rows
