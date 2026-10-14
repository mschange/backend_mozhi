# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import mysql

from app.agent.tools import memory
from app.repositories import long_term_memory as memory_repository
from app.services import memory_service
from scripts import migrate_milvus_memories


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_memory_save_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    record = SimpleNamespace(
        id="memory-1",
        user_id="user-1",
        content="喜欢 Python",
        index_status="pending",
        error_message=None,
    )
    indexed: list[str] = []

    async def get_or_create(_db, user_id, content, hash_value):
        assert user_id == "user-1"
        assert content == "喜欢 Python"
        assert len(hash_value) == 64
        return record, record.index_status == "pending"

    async def mark_ready(_db, item):
        item.index_status = "ready"

    monkeypatch.setattr(memory_service, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(
        memory_service.memory_repository,
        "get_or_create",
        get_or_create,
    )
    monkeypatch.setattr(
        memory_service.memory_repository,
        "mark_ready",
        mark_ready,
    )
    monkeypatch.setattr(
        memory_service,
        "_index_memory",
        lambda item: indexed.append(item.id),
    )

    assert (
        await memory_service.save_long_term_memory(
            "user-1",
            "  喜欢   Python  ",
        )
        == "已写入长期记忆。"
    )
    assert (
        await memory_service.save_long_term_memory("user-1", "喜欢 Python")
        == "已写入长期记忆。"
    )
    assert indexed == ["memory-1"]


@pytest.mark.asyncio
async def test_memory_save_preserves_fact_when_index_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR", logger=memory_service.__name__)
    record = SimpleNamespace(
        id="memory-1",
        user_id="user-1",
        content="长期事实",
        index_status="pending",
        error_message=None,
    )

    async def get_or_create(*_args):
        return record, True

    async def mark_failed(_db, item, error_message):
        item.index_status = "failed"
        item.error_message = error_message

    def fail_index(_item):
        raise RuntimeError("milvus unavailable")

    monkeypatch.setattr(memory_service, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(
        memory_service.memory_repository,
        "get_or_create",
        get_or_create,
    )
    monkeypatch.setattr(
        memory_service.memory_repository,
        "mark_failed",
        mark_failed,
    )
    monkeypatch.setattr(memory_service, "_index_memory", fail_index)

    result = await memory_service.save_long_term_memory(
        "user-1",
        "长期事实",
    )

    assert result == "长期记忆已保存，向量索引暂时不可用。"
    assert record.index_status == "failed"
    assert record.error_message == "milvus unavailable"
    assert "长期记忆索引写入失败: memory_id=memory-1" in caplog.text
    assert "RuntimeError: milvus unavailable" in caplog.text


@pytest.mark.asyncio
async def test_memory_search_preserves_vector_order_and_filters_orphans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def skip_retry(_user_id):
        return None

    async def get_memories(_db, user_id, memory_ids):
        assert user_id == "user-1"
        assert memory_ids == ["memory-2", "orphan", "memory-1"]
        return [
            SimpleNamespace(id="memory-1", content="第一条事实"),
            SimpleNamespace(id="memory-2", content="第二条事实"),
        ]

    monkeypatch.setattr(memory_service, "_retry_indexes", skip_retry)
    monkeypatch.setattr(memory_service, "embed_query", lambda _query: [0.1])
    monkeypatch.setattr(
        memory_service,
        "search_vectors",
        lambda *_args: [
            {"id": "memory-2"},
            {"id": "orphan"},
            {"id": "memory-1"},
        ],
    )
    monkeypatch.setattr(memory_service, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(
        memory_service.memory_repository,
        "get_owned_by_ids",
        get_memories,
    )

    result = await memory_service.search_long_term_memory("user-1", "偏好")

    assert result.splitlines() == ["[1] 第二条事实", "[2] 第一条事实"]
    assert "orphan" not in result


@pytest.mark.asyncio
async def test_retryable_memory_is_reindexed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = SimpleNamespace(
        id="memory-1",
        user_id="user-1",
        content="待重试事实",
        index_status="failed",
    )
    indexed: list[str] = []

    async def list_retryable(*_args):
        return [record]

    async def get_owned(*_args):
        return record

    async def mark_ready(_db, item):
        item.index_status = "ready"

    monkeypatch.setattr(memory_service, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(
        memory_service.memory_repository,
        "list_retryable",
        list_retryable,
    )
    monkeypatch.setattr(
        memory_service.memory_repository,
        "get_owned",
        get_owned,
    )
    monkeypatch.setattr(
        memory_service.memory_repository,
        "mark_ready",
        mark_ready,
    )
    monkeypatch.setattr(
        memory_service,
        "_index_memory",
        lambda item: indexed.append(item.id),
    )

    await memory_service._retry_indexes("user-1")

    assert indexed == ["memory-1"]
    assert record.index_status == "ready"


@pytest.mark.asyncio
async def test_retryable_memory_logs_index_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR", logger=memory_service.__name__)
    record = SimpleNamespace(
        id="memory-1",
        user_id="user-1",
        content="待重试事实",
        index_status="failed",
        error_message=None,
    )

    async def list_retryable(*_args):
        return [record]

    async def get_owned(*_args):
        return record

    async def mark_failed(_db, item, error_message):
        item.error_message = error_message

    def fail_index(_item):
        raise RuntimeError("milvus unavailable")

    monkeypatch.setattr(memory_service, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(
        memory_service.memory_repository,
        "list_retryable",
        list_retryable,
    )
    monkeypatch.setattr(memory_service.memory_repository, "get_owned", get_owned)
    monkeypatch.setattr(memory_service.memory_repository, "mark_failed", mark_failed)
    monkeypatch.setattr(memory_service, "_index_memory", fail_index)

    await memory_service._retry_indexes("user-1")

    assert record.error_message == "milvus unavailable"
    assert "长期记忆索引重试失败: memory_id=memory-1" in caplog.text
    assert "RuntimeError: milvus unavailable" in caplog.text


@pytest.mark.asyncio
async def test_ready_memories_can_rebuild_an_empty_vector_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        SimpleNamespace(id="memory-1", user_id="user-1", content="长期事实"),
    ]
    indexed: list[list[str]] = []

    async def list_ready(_db, user_id):
        assert user_id == "user-1"
        return records

    monkeypatch.setattr(memory_service, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(
        memory_service.memory_repository,
        "list_ready",
        list_ready,
    )
    monkeypatch.setattr(
        memory_service,
        "_index_memories",
        lambda items: indexed.append([item.id for item in items]),
    )

    await memory_service._rebuild_ready_indexes("user-1")

    assert indexed == [["memory-1"]]


@pytest.mark.asyncio
async def test_memory_tool_forwards_user_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    async def search(user_id, query):
        calls.append(("search", user_id, query))
        return "记忆"

    async def save(user_id, fact):
        calls.append(("save", user_id, fact))
        return "已保存"

    monkeypatch.setattr(
        memory.memory_service,
        "search_long_term_memory",
        search,
    )
    monkeypatch.setattr(
        memory.memory_service,
        "save_long_term_memory",
        save,
    )
    tools = {tool.name: tool for tool in memory.build_memory_tools("user-1")}

    assert await tools["search_long_term_memory"].ainvoke({"query": "偏好"}) == "记忆"
    assert await tools["save_long_term_memory"].ainvoke({"fact": "事实"}) == "已保存"
    assert calls == [
        ("search", "user-1", "偏好"),
        ("save", "user-1", "事实"),
    ]


@pytest.mark.asyncio
async def test_memory_get_or_create_uses_atomic_mysql_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = SimpleNamespace(id="memory-new")

    class FakeDb:
        def __init__(self) -> None:
            self.executed = None

        async def execute(self, statement):
            self.executed = statement

        async def scalar(self, _statement):
            return record

    db = FakeDb()
    monkeypatch.setattr(memory_repository, "uuid4", lambda: "memory-new")

    item, created = await memory_repository.get_or_create(
        db,
        "user-1",
        "长期事实",
        "a" * 64,
    )

    sql = str(db.executed.compile(dialect=mysql.dialect()))
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert item is record
    assert created is True


@pytest.mark.asyncio
async def test_memory_migration_deduplicates_rows_within_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    added = []

    class MigrationSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args):
            return None

        def add(self, item):
            added.append(item)

        async def commit(self):
            return None

    async def get_by_hash(*_args):
        return None

    monkeypatch.setattr(
        migrate_milvus_memories,
        "AsyncSessionLocal",
        MigrationSession,
    )
    monkeypatch.setattr(
        migrate_milvus_memories.memory_repository,
        "get_by_hash",
        get_by_hash,
    )

    created, skipped = await migrate_milvus_memories.migrate_batch(
        [
            {"id": "memory-1", "user_id": "user-1", "text": "长期  事实"},
            {"id": "memory-2", "user_id": "user-1", "text": "长期 事实"},
            {"id": "memory-1", "user_id": "user-1", "text": "其他事实"},
        ]
    )

    assert (created, skipped) == (1, 2)
    assert [item.id for item in added] == ["memory-1"]
