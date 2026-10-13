"""墨知 FastAPI 入口。

启动时：读 .env、配 LangSmith、建 uploads 目录、建 MySQL 表、初始化 Milvus Lite、预热 Agent。
分层：api（HTTP）→ services（业务）→ repositories（SQL），模型与工具组装位于 agent。
所有业务接口统一信封 `{code, message, data}`。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.providers.chat import init_chat_provider
from app.agent.providers.embeddings import init_embeddings
from app.api.v1.router import api_router
from app.config import apply_runtime_env, upload_path
from app.core.logging import configure_file_logging, configure_langsmith
from app.utils.http.handlers import register_exception_handlers
from app.utils.http.response import success_response
from app.utils.storage.checkpoint import checkpoint_lifespan
from app.utils.storage.milvus import close_milvus, init_milvus
from app.utils.storage.mysql import close_mysql, init_mysql

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """进程生命周期：启动资源初始化，关闭时 FastAPI 会走到 yield 之后。"""
    configure_file_logging()
    apply_runtime_env()
    configure_langsmith()
    upload_path().mkdir(parents=True, exist_ok=True)
    try:
        await init_mysql()
        init_milvus()
        init_chat_provider()
        init_embeddings()
        async with checkpoint_lifespan() as checkpointer:
            app.state.checkpointer = checkpointer
            yield
    except Exception:
        logger.exception("应用启动或运行失败")
        raise
    finally:
        try:
            close_milvus()
            await close_mysql()
        except Exception:
            logger.exception("应用资源关闭失败")
            raise


app = FastAPI(title="墨知", description="AI 对话知识库平台", lifespan=lifespan)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
async def health():
    """探活，前端/运维用来确认服务已起来。"""
    return success_response(message="服务正常", data={"name": "墨知"})
