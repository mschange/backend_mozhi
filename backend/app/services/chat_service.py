"""对话发送：落库用户消息 → Agent 流式生成 → 落库助手消息。

Agent 接入点在这里：`AgentRuntime(user.id).astream(history)`。
history 取最近 SHORT_TERM_MEMORY_N 条，作为短时记忆喂给模型。

SSE 必须自建 session：FastAPI 的 get_db 会在响应开始后关闭，
流还没结束就会 OperationalError。
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.runtime import AgentRuntime
from app.config import SHORT_TERM_MEMORY_N
from app.models.user import User
from app.utils.storage.checkpoint import build_thread_id, delete_thread, get_latest_checkpoint_id
from app.utils.storage.mysql import AsyncSessionLocal
from app.repositories import conversation as conversation_repository
from app.repositories import user as user_repository
from app.schemas.conversation import MessageOut
from app.services.conversation_service import (
    get_owned_conversation_for_update,
    maybe_rename_conversation,
    to_message_out,
)
from app.utils.enums import ErrorCode
from app.utils.exceptions import AppError

logger = logging.getLogger(__name__)


async def send_message(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    content: str,
    checkpointer: AsyncPostgresSaver,
) -> MessageOut:
    """非流式发送：内部仍走 stream_message，等 done 事件再返回完整助手消息。"""
    final: MessageOut | None = None
    async for event in stream_message(
        db,
        user,
        conversation_id,
        content,
        checkpointer,
    ):
        if event.get("type") == "done":
            final = MessageOut.model_validate(event["message"])
    if final is None:
        raise AppError(ErrorCode.LLM_ERROR, "模型服务暂时不可用，请稍后重试")
    return final


async def stream_chat_events(
    user_id: str,
    chat_id: str,
    content: str,
    checkpointer: AsyncPostgresSaver,
) -> AsyncIterator[dict[str, Any]]:
    """流式事件生成器：独立 session，错误也作为事件返回。"""
    async with AsyncSessionLocal() as db:
        user = await user_repository.get_by_id(db, user_id)
        if user is None:
            yield {"type": "error", "code": 40100, "message": "未授权，请先登录"}
            return
        try:
            async for event in stream_message(
                db,
                user,
                chat_id,
                content,
                checkpointer,
            ):
                if event.get("type") == "done":
                    await db.commit()
                yield event
        except AppError as exc:
            await db.rollback()
            yield {"type": "error", "code": int(exc.code), "message": exc.message}
        except Exception:
            logger.exception("对话流处理失败: chat_id=%s", chat_id)
            await db.rollback()
            yield {"type": "error", "code": 50001, "message": "模型服务暂时不可用，请稍后重试"}


async def stream_message(
    db: AsyncSession,
    user: User,
    conversation_id: str,
    content: str,
    checkpointer: AsyncPostgresSaver,
) -> AsyncIterator[dict[str, Any]]:
    """一轮对话核心：同步 thread → Agent 吐 token → 原子写助手消息和水位。"""
    text = content.strip()
    if not text:
        raise AppError(ErrorCode.EMPTY_MESSAGE, "消息不能为空")

    conv = await get_owned_conversation_for_update(db, conversation_id, user)
    thread_id = build_thread_id(user.id, conversation_id)
    watermark = await conversation_repository.get_checkpoint(db, conversation_id)
    current_message_count = await conversation_repository.message_count(
        db,
        conversation_id,
    )
    contains_last_message = (
        await conversation_repository.contains_message(
            db,
            conversation_id,
            watermark.last_message_id,
        )
        if watermark is not None
        else False
    )
    postgres_checkpoint_id = await get_latest_checkpoint_id(checkpointer, thread_id)
    synchronized = (
        watermark is not None
        and watermark.thread_id == thread_id
        and watermark.message_count == current_message_count
        and contains_last_message
        and watermark.checkpoint_id == postgres_checkpoint_id
    )
    if not synchronized:
        await delete_thread(checkpointer, thread_id)

    user_message = await conversation_repository.add_message(
        db,
        conversation_id,
        "user",
        text,
    )
    maybe_rename_conversation(conv, text)
    await conversation_repository.touch(db, conv)
    await db.flush()

    history = (
        [user_message]
        if synchronized
        else await conversation_repository.recent_messages(
            db,
            conversation_id,
            SHORT_TERM_MEMORY_N,
        )
    )
    runtime = AgentRuntime(user.id, checkpointer, thread_id)
    chunks: list[str] = []
    async for token in runtime.astream(history):
        chunks.append(token)
        yield {"type": "delta", "content": token}

    checkpoint_id = await get_latest_checkpoint_id(checkpointer, thread_id)
    if checkpoint_id is None:
        raise AppError(ErrorCode.LLM_ERROR, "模型服务暂时不可用，请稍后重试")

    answer = "".join(chunks).strip() or "我暂时没有生成有效回答，请换一种问法试试。"
    assistant = await conversation_repository.add_message(
        db,
        conversation_id,
        "assistant",
        answer,
        citations=None,
    )
    await conversation_repository.set_checkpoint(
        db,
        conversation_id,
        thread_id,
        checkpoint_id,
        assistant.id,
        current_message_count + 2,
    )
    await conversation_repository.touch(db, conv)
    yield {
        "type": "done",
        "message": to_message_out(assistant).model_dump(mode="json"),
    }
