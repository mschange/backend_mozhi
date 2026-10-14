# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
from types import SimpleNamespace

import pytest

from app import main as main_module
from app.config import BACKEND_DIR, upload_path
from app.core.security import create_access_token, decode_token
from app.main import app
from app.utils.enums import TokenType
from app.utils.http.response import success


EXPECTED_PATHS = {
    "/api/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/me",
    "/api/chat/create",
    "/api/chat/list",
    "/api/chat/detail",
    "/api/chat/delete",
    "/api/chat/rename",
    "/api/chat/send",
    "/api/chat/stream",
    "/api/knowledge/list",
    "/api/knowledge/upload",
    "/api/knowledge/delete",
}


def test_public_api_paths_are_unchanged() -> None:
    assert set(app.openapi()["paths"]) == EXPECTED_PATHS


def test_success_envelope() -> None:
    assert success({"id": 1}, "成功") == {
        "code": 0,
        "message": "成功",
        "data": {"id": 1},
    }


def test_config_paths_are_relative_to_backend() -> None:
    assert BACKEND_DIR.name == "backend"
    assert upload_path() == BACKEND_DIR / "uploads"


def test_access_token_round_trip() -> None:
    token = create_access_token("user-test-001")

    assert decode_token(token, TokenType.ACCESS) == "user-test-001"


@pytest.mark.asyncio
async def test_lifespan_preserves_resource_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    calls: list[str] = []

    async def init_mysql() -> None:
        calls.append("init_mysql")

    async def close_mysql() -> None:
        calls.append("close_mysql")

    class CheckpointContext:
        async def __aenter__(self):
            calls.append("checkpoint_open")
            return SimpleNamespace()

        async def __aexit__(self, *_args):
            calls.append("checkpoint_close")

    monkeypatch.setattr(
        main_module,
        "configure_file_logging",
        lambda: calls.append("file_logging"),
    )
    monkeypatch.setattr(main_module, "apply_runtime_env", lambda: calls.append("env"))
    monkeypatch.setattr(main_module, "configure_langsmith", lambda: calls.append("langsmith"))
    monkeypatch.setattr(main_module, "upload_path", lambda: tmp_path / "uploads")
    monkeypatch.setattr(main_module, "init_mysql", init_mysql)
    monkeypatch.setattr(main_module, "init_milvus", lambda: calls.append("init_milvus"))
    monkeypatch.setattr(
        main_module,
        "init_chat_provider",
        lambda: calls.append("init_chat"),
    )
    monkeypatch.setattr(
        main_module,
        "init_embeddings",
        lambda: calls.append("init_embeddings"),
    )
    monkeypatch.setattr(
        main_module,
        "checkpoint_lifespan",
        CheckpointContext,
    )
    monkeypatch.setattr(main_module, "close_milvus", lambda: calls.append("close_milvus"))
    monkeypatch.setattr(main_module, "close_mysql", close_mysql)
    application = SimpleNamespace(state=SimpleNamespace())

    async with main_module.lifespan(application):
        calls.append("yield")
        assert application.state.checkpointer is not None

    assert calls == [
        "file_logging",
        "env",
        "langsmith",
        "init_mysql",
        "init_milvus",
        "init_chat",
        "init_embeddings",
        "checkpoint_open",
        "yield",
        "checkpoint_close",
        "close_milvus",
        "close_mysql",
    ]
