"""会话 CRUD。空会话会复用，避免侧边栏堆一堆「新对话」。"""

import json

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.storage.checkpoint import build_thread_id, delete_thread
from app.models.conversation import Conversation
from app.models.user import User
from app.repositories import conversation as conversation_repository
from app.schemas.conversation import ChatCreateIn, ChatDetailOut, ChatOut, MessageOut
from app.utils.enums import ErrorCode
from app.utils.exceptions import AppError


def _parse_citations(raw: str | None) -> list[dict] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        return None


def to_message_out(msg) -> MessageOut:
    return MessageOut(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        citations=_parse_citations(msg.citations),
        created_at=msg.created_at,
    )


async def create_conversation(db: AsyncSession, user: User, payload: ChatCreateIn) -> ChatOut:
    """已有 0 条消息的会话则直接返回，否则新建。"""
    empty = await conversation_repository.find_empty(db, user.id)
    if empty is not None:
        return ChatOut.model_validate(empty).model_copy(update={"message_count": 0})
    title = (payload.title or "").strip() or "新对话"
    conv = await conversation_repository.create(db, user.id, title)
    return ChatOut.model_validate(conv).model_copy(update={"message_count": 0})


async def list_conversations(db: AsyncSession, user: User) -> list[ChatOut]:
    items = await conversation_repository.list_by_user(db, user.id)
    return [
        ChatOut.model_validate(conv).model_copy(update={"message_count": count})
        for conv, count in items
    ]


async def get_owned_conversation(db: AsyncSession, conversation_id: str, user: User) -> Conversation:
    conv = await conversation_repository.get_owned(db, conversation_id, user.id)
    if conv is None:
        raise AppError(ErrorCode.NOT_FOUND, "会话不存在")
    return conv


async def get_owned_conversation_for_update(
    db: AsyncSession,
    conversation_id: str,
    user: User,
) -> Conversation:
    conv = await conversation_repository.get_owned_for_update(db, conversation_id, user.id)
    if conv is None:
        raise AppError(ErrorCode.NOT_FOUND, "会话不存在")
    return conv


async def delete_conversation(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    checkpointer: AsyncPostgresSaver,
) -> None:
    conv = await get_owned_conversation_for_update(db, conversation_id, user)
    await delete_thread(checkpointer, build_thread_id(user.id, conversation_id))
    await conversation_repository.delete(db, conv)


async def rename_conversation(
    db: AsyncSession, user: User, conversation_id: str, title: str
) -> ChatOut:
    """用户手动改标题。之后首条消息不会再覆盖（除非标题仍是「新对话」）。"""
    conv = await get_owned_conversation(db, conversation_id, user)
    name = title.strip()
    if not name:
        raise AppError(ErrorCode.VALIDATION_ERROR, "标题不能为空")
    conv = await conversation_repository.update_title(db, conv, name[:128])
    return ChatOut.model_validate(conv)


async def get_conversation_detail(
    db: AsyncSession, user: User, conversation_id: str
) -> ChatDetailOut:
    conv = await conversation_repository.get_owned_with_messages(db, conversation_id, user.id)
    if conv is None:
        raise AppError(ErrorCode.NOT_FOUND, "会话不存在")
    return ChatDetailOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[to_message_out(m) for m in conv.messages],
    )


def maybe_rename_conversation(conv: Conversation, first_content: str) -> None:
    """首条用户消息把默认标题「新对话」换成内容前 24 字。"""
    if conv.title == "新对话":
        conv.title = first_content.strip()[:24] or "新对话"
