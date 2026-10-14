# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
from types import SimpleNamespace

import pytest

from app.services import conversation_service


@pytest.mark.asyncio
async def test_delete_conversation_removes_thread_before_mysql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation = SimpleNamespace(id="chat-1")
    order: list[str] = []

    async def get_owned(*_args):
        return conversation

    async def remove_thread(_checkpointer, thread_id):
        assert thread_id == "user:user-1:conversation:chat-1"
        order.append("postgres")

    async def delete_mysql(_db, item):
        assert item is conversation
        order.append("mysql")

    monkeypatch.setattr(
        conversation_service,
        "get_owned_conversation_for_update",
        get_owned,
    )
    monkeypatch.setattr(conversation_service, "delete_thread", remove_thread)
    monkeypatch.setattr(
        conversation_service.conversation_repository,
        "delete",
        delete_mysql,
    )

    await conversation_service.delete_conversation(
        SimpleNamespace(),
        SimpleNamespace(id="user-1"),
        "chat-1",
        SimpleNamespace(),
    )

    assert order == ["postgres", "mysql"]
