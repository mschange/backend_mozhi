# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import chat_service
from app.utils.enums import ErrorCode
from app.utils.exceptions import AppError


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.order: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1
        self.order.append("commit")

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_stream_message_rejects_blank_content() -> None:
    events = chat_service.stream_message(
        FakeSession(),
        SimpleNamespace(id="user-1"),
        "chat-1",
        "   ",
        SimpleNamespace(),
    )

    with pytest.raises(AppError) as exc_info:
        await anext(events)

    assert exc_info.value.code == ErrorCode.EMPTY_MESSAGE


@pytest.mark.asyncio
@pytest.mark.parametrize("synchronized", [False, True])
async def test_stream_message_bootstraps_or_appends(
    monkeypatch: pytest.MonkeyPatch,
    synchronized: bool,
) -> None:
    conversation = SimpleNamespace(title="新对话")
    user_message = SimpleNamespace(id="user-message", role="user", content="问题")
    assistant = SimpleNamespace(
        id="assistant-message",
        role="assistant",
        content="你好",
        citations=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    watermark = (
        SimpleNamespace(
            thread_id="user:user-1:conversation:chat-1",
            last_message_id="old-message",
            checkpoint_id="checkpoint-old",
            message_count=1,
        )
        if synchronized
        else None
    )
    checkpoint_ids = iter(
        ["checkpoint-old" if synchronized else None, "checkpoint-new"]
    )
    deleted: list[str] = []
    runtime_histories: list[list] = []
    saved_watermarks: list[tuple] = []

    async def get_owned(*_args):
        return conversation

    async def get_checkpoint(*_args):
        return watermark

    async def message_count(*_args):
        return 1 if synchronized else 0

    async def contains_message(*_args):
        return synchronized

    async def latest_checkpoint(*_args):
        return next(checkpoint_ids)

    async def delete_checkpoint_thread(_saver, thread_id):
        deleted.append(thread_id)

    async def add_message(_db, _conversation_id, role, _content, citations=None):
        return assistant if role == "assistant" else user_message

    async def touch(*_args):
        return None

    async def recent_messages(*_args):
        return [SimpleNamespace(id="old-message"), user_message]

    async def set_checkpoint(*args):
        saved_watermarks.append(args)

    class FakeRuntime:
        def __init__(self, _user_id, _checkpointer, _thread_id):
            pass

        async def astream(self, history):
            runtime_histories.append(history)
            yield "你"
            yield "好"

    monkeypatch.setattr(chat_service, "get_owned_conversation_for_update", get_owned)
    monkeypatch.setattr(chat_service.conversation_repository, "get_checkpoint", get_checkpoint)
    monkeypatch.setattr(chat_service.conversation_repository, "message_count", message_count)
    monkeypatch.setattr(
        chat_service.conversation_repository,
        "contains_message",
        contains_message,
    )
    monkeypatch.setattr(chat_service, "get_latest_checkpoint_id", latest_checkpoint)
    monkeypatch.setattr(chat_service, "delete_thread", delete_checkpoint_thread)
    monkeypatch.setattr(chat_service.conversation_repository, "add_message", add_message)
    monkeypatch.setattr(chat_service.conversation_repository, "touch", touch)
    monkeypatch.setattr(chat_service.conversation_repository, "recent_messages", recent_messages)
    monkeypatch.setattr(chat_service.conversation_repository, "set_checkpoint", set_checkpoint)
    monkeypatch.setattr(chat_service, "AgentRuntime", FakeRuntime)

    events = [
        event
        async for event in chat_service.stream_message(
            FakeSession(),
            SimpleNamespace(id="user-1"),
            "chat-1",
            "问题",
            SimpleNamespace(),
        )
    ]

    assert [event["type"] for event in events] == ["delta", "delta", "done"]
    assert events[-1]["message"]["content"] == "你好"
    assert events[-1]["message"]["created_at"] == "2026-01-01T00:00:00Z"
    assert conversation.title == "问题"
    assert runtime_histories == (
        [[user_message]]
        if synchronized
        else [[SimpleNamespace(id="old-message"), user_message]]
    )
    assert bool(deleted) is not synchronized
    assert saved_watermarks[0][-3:] == (
        "checkpoint-new",
        "assistant-message",
        (1 if synchronized else 0) + 2,
    )


@pytest.mark.asyncio
async def test_stream_done_is_emitted_after_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()

    async def get_user(*_args):
        return SimpleNamespace(id="user-1")

    async def fake_stream(*_args):
        yield {"type": "delta", "content": "答"}
        yield {"type": "done", "message": {"content": "答案"}}

    monkeypatch.setattr(chat_service, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(chat_service.user_repository, "get_by_id", get_user)
    monkeypatch.setattr(chat_service, "stream_message", fake_stream)

    events = []
    async for event in chat_service.stream_chat_events(
        "user-1",
        "chat-1",
        "问题",
        SimpleNamespace(),
    ):
        session.order.append(f"yield:{event['type']}")
        events.append(event)

    assert [event["type"] for event in events] == ["delta", "done"]
    assert session.order == ["yield:delta", "commit", "yield:done"]
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_stream_commit_failure_emits_error_instead_of_done(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR", logger=chat_service.__name__)

    class FailingCommitSession(FakeSession):
        async def commit(self) -> None:
            self.order.append("commit")
            raise RuntimeError("mysql unavailable")

    session = FailingCommitSession()

    async def get_user(*_args):
        return SimpleNamespace(id="user-1")

    async def fake_stream(*_args):
        yield {"type": "delta", "content": "答"}
        yield {"type": "done", "message": {"content": "答案"}}

    monkeypatch.setattr(chat_service, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(chat_service.user_repository, "get_by_id", get_user)
    monkeypatch.setattr(chat_service, "stream_message", fake_stream)

    events = [
        event
        async for event in chat_service.stream_chat_events(
            "user-1",
            "chat-1",
            "问题",
            SimpleNamespace(),
        )
    ]

    assert [event["type"] for event in events] == ["delta", "error"]
    assert session.rollbacks == 1
    assert "对话流处理失败: chat_id=chat-1" in caplog.text
    assert "RuntimeError: mysql unavailable" in caplog.text
