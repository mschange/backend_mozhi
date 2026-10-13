"""版本一 API 路由汇总，版本号不进入公开 URL。"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.messages import router as messages_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(conversations_router)
api_router.include_router(messages_router)
api_router.include_router(knowledge_router)
