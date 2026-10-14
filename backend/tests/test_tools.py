# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
from types import SimpleNamespace

import pytest

from app.agent.tools import knowledge, registry
from app.services import knowledge_retrieval_service


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_knowledge_search_filters_by_current_user_and_ready_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    monkeypatch.setattr(
        knowledge_retrieval_service,
        "embed_query",
        lambda query: [0.1],
    )

    def fake_search(collection, vector, user_id, limit):
        calls.append((collection, vector, user_id, limit))
        return [
            {"document_id": "ready-doc", "text": "可用片段"},
            {"document_id": "orphan-doc", "text": "孤儿片段"},
        ]

    async def get_ready(_db, user_id, document_ids):
        assert user_id == "user-123"
        assert document_ids == ["ready-doc", "orphan-doc"]
        return [SimpleNamespace(id="ready-doc")]

    monkeypatch.setattr(
        knowledge_retrieval_service,
        "search_vectors",
        fake_search,
    )
    monkeypatch.setattr(
        knowledge_retrieval_service,
        "AsyncSessionLocal",
        lambda: FakeSession(),
    )
    monkeypatch.setattr(
        knowledge_retrieval_service.knowledge_repository,
        "get_ready_owned_by_ids",
        get_ready,
    )

    result = await knowledge_retrieval_service.search_knowledge_base(
        "user-123",
        "项目资料",
    )

    assert "可用片段" in result
    assert "孤儿片段" not in result
    assert calls[0][2] == "user-123"


@pytest.mark.asyncio
async def test_knowledge_tool_forwards_user_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    async def search(user_id, query):
        calls.append((user_id, query))
        return "检索结果"

    monkeypatch.setattr(
        knowledge.knowledge_retrieval_service,
        "search_knowledge_base",
        search,
    )

    tool = knowledge.build_knowledge_tool("user-123")

    assert await tool.ainvoke({"query": "项目资料"}) == "检索结果"
    assert calls == [("user-123", "项目资料")]


def test_tool_registry_keeps_requested_order_and_skips_unavailable_web(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        registry,
        "build_knowledge_tool",
        lambda _user_id: SimpleNamespace(name="search_knowledge_base"),
    )
    monkeypatch.setattr(
        registry,
        "build_memory_tools",
        lambda _user_id: [
            SimpleNamespace(name="search_long_term_memory"),
            SimpleNamespace(name="save_long_term_memory"),
        ],
    )
    monkeypatch.setattr(registry, "build_web_search_tool", lambda: None)

    tools = registry.get_tools_by_names(
        ["save_long_term_memory", "web_search", "search_knowledge_base"],
        "user-1",
    )

    assert [tool.name for tool in tools] == [
        "save_long_term_memory",
        "search_knowledge_base",
    ]
