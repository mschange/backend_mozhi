"""会话创建、查询、删除与改名接口。"""

from fastapi import APIRouter, Depends
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.utils.http.dependencies import get_checkpointer, get_db
from app.utils.http.response import success_response
from app.models.user import User
from app.schemas.conversation import ChatCreateIn, ChatIdIn, ChatRenameIn
from app.services.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation_detail,
    list_conversations,
    rename_conversation,
)

router = APIRouter(prefix="/api/chat", tags=["对话"])


@router.post("/create")
async def create_chat(
    body: ChatCreateIn,
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
):
    data = await create_conversation(db, current, body)
    return success_response(message="创建成功", data=data)


@router.get("/list")
async def list_chat(
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
):
    data = await list_conversations(db, current)
    return success_response(message="获取成功", data=data)


@router.get("/detail")
async def chat_detail(
    chat_id: str,
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
):
    data = await get_conversation_detail(db, current, chat_id)
    return success_response(message="获取成功", data=data)


@router.post("/delete")
async def delete_chat(
    body: ChatIdIn,
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
    checkpointer: AsyncPostgresSaver = Depends(get_checkpointer),
):
    await delete_conversation(db, current, body.chat_id, checkpointer)
    return success_response(message="删除成功", data=None)


@router.post("/rename")
async def rename_chat(
    body: ChatRenameIn,
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
):
    data = await rename_conversation(db, current, body.chat_id, body.title)
    return success_response(message="修改成功", data=data)
