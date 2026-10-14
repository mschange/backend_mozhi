# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
from types import SimpleNamespace

import pytest

from app.utils.storage import checkpoint


def test_thread_id_is_stable_and_isolated() -> None:
    assert checkpoint.build_thread_id("user-1", "chat-1") == checkpoint.build_thread_id(
        "user-1", "chat-1"
    )
    assert checkpoint.build_thread_id("user-1", "chat-1") != checkpoint.build_thread_id(
        "user-2", "chat-1"
    )
    assert checkpoint.build_thread_id("user-1", "chat-1") != checkpoint.build_thread_id(
        "user-1", "chat-2"
    )


@pytest.mark.asyncio
async def test_checkpoint_lifespan_sets_up_and_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakePool:
        def __init__(self, **_kwargs):
            pass

        async def open(self, wait: bool):
            assert wait is True
            calls.append("open")

        async def close(self):
            calls.append("close")

    class FakeSaver:
        def __init__(self, pool):
            assert isinstance(pool, FakePool)

        async def setup(self):
            calls.append("setup")

    monkeypatch.setattr(checkpoint, "AsyncConnectionPool", FakePool)
    monkeypatch.setattr(checkpoint, "AsyncPostgresSaver", FakeSaver)

    async with checkpoint.checkpoint_lifespan() as saver:
        assert isinstance(saver, FakeSaver)
        calls.append("yield")

    assert calls == ["open", "setup", "yield", "close"]


@pytest.mark.asyncio
async def test_checkpoint_lifespan_closes_when_open_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakePool:
        def __init__(self, **_kwargs):
            pass

        async def open(self, wait: bool):
            assert wait is True
            calls.append("open")
            raise RuntimeError("postgres unavailable")

        async def close(self):
            calls.append("close")

    monkeypatch.setattr(checkpoint, "AsyncConnectionPool", FakePool)

    with pytest.raises(RuntimeError, match="postgres unavailable"):
        async with checkpoint.checkpoint_lifespan():
            pass

    assert calls == ["open", "close"]


@pytest.mark.asyncio
async def test_get_latest_checkpoint_id() -> None:
    class FakeSaver:
        async def aget_tuple(self, config):
            assert config == {"configurable": {"thread_id": "thread-1"}}
            return SimpleNamespace(
                config={"configurable": {"checkpoint_id": "checkpoint-1"}}
            )

    assert (
        await checkpoint.get_latest_checkpoint_id(FakeSaver(), "thread-1")
        == "checkpoint-1"
    )
