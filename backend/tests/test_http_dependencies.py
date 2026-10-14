# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
import pytest

from app.utils.http import dependencies


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __aenter__(self):
        self.calls.append("enter")
        return self

    async def __aexit__(self, *_args):
        self.calls.append("exit")

    async def commit(self) -> None:
        self.calls.append("commit")

    async def rollback(self) -> None:
        self.calls.append("rollback")


@pytest.mark.asyncio
async def test_get_db_commits_successful_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        dependencies,
        "AsyncSessionLocal",
        lambda: session,
    )
    generator = dependencies.get_db()

    assert await anext(generator) is session
    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert session.calls == ["enter", "commit", "exit"]


@pytest.mark.asyncio
async def test_get_db_rolls_back_failed_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        dependencies,
        "AsyncSessionLocal",
        lambda: session,
    )
    generator = dependencies.get_db()

    assert await anext(generator) is session
    with pytest.raises(RuntimeError, match="request failed"):
        await generator.athrow(RuntimeError("request failed"))

    assert session.calls == ["enter", "rollback", "exit"]
