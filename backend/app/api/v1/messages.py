"""消息发送与流式响应接口。"""

from fastapi import APIRouter, Depends
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.utils.http.dependencies import get_checkpointer, get_db
from app.utils.http.response import success_response
from app.utils.http.sse import sse_response
from app.models.user import User
from app.schemas.conversation import ChatSendIn
from app.services.chat_service import send_message, stream_chat_events

router = APIRouter(prefix="/api/chat", tags=["对话"])


@router.post("/send")
async def send_chat(
    body: ChatSendIn,
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
    checkpointer: AsyncPostgresSaver = Depends(get_checkpointer),
):
    data = await send_message(
        db,
        current,
        body.chat_id,
        body.content,
        checkpointer,
    )
    return success_response(message="发送成功", data=data)


@router.post("/stream")
async def stream_chat(
    body: ChatSendIn,
    current: User = Depends(get_current_user),
    checkpointer: AsyncPostgresSaver = Depends(get_checkpointer),
):
    return sse_response(
        stream_chat_events(
            current.id,
            body.chat_id,
            body.content,
            checkpointer,
        )
    )
