# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessageChunk, HumanMessage

from app.agent import chat_agent, messages, runtime
from app.utils.enums import ErrorCode
from app.utils.exceptions import AppError


@pytest.mark.asyncio
async def test_agent_receives_checkpointer_and_thread_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    class FakeGraph:
        async def astream(self, inputs, **kwargs):
            captured["inputs"] = inputs
            captured.update(kwargs)
            yield AIMessageChunk(content="回答"), {"langgraph_node": "model"}

    def fake_create_agent(**kwargs):
        captured["create"] = kwargs
        return FakeGraph()

    checkpointer = SimpleNamespace()
    monkeypatch.setattr(chat_agent, "create_agent", fake_create_agent)
    monkeypatch.setattr(chat_agent, "get_chat_model", lambda: SimpleNamespace())
    monkeypatch.setattr(chat_agent, "get_tools_by_names", lambda *_args: [])

    agent = chat_agent.ChatAgent("system", [], "user-1", checkpointer)
    tokens = [
        token
        async for token in agent.astream_tokens(
            [HumanMessage(content="问题", id="message-1")],
            "thread-1",
        )
    ]

    assert tokens == ["回答"]
    assert captured["create"]["checkpointer"] is checkpointer
    assert captured["config"] == {"configurable": {"thread_id": "thread-1"}}


def test_history_to_lc_preserves_mysql_message_ids() -> None:
    history = messages.history_to_lc(
        [
            SimpleNamespace(id="user-message", role="user", content="问题"),
            SimpleNamespace(id="assistant-message", role="assistant", content="回答"),
        ]
    )

    assert [message.id for message in history] == [
        "user-message",
        "assistant-message",
    ]


@pytest.mark.asyncio
async def test_runtime_maps_agent_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingAgent:
        def __init__(self, **_kwargs):
            pass

        async def astream_tokens(self, _history, _thread_id):
            raise RuntimeError("provider unavailable")
            yield

    monkeypatch.setattr(runtime, "ChatAgent", FailingAgent)
    agent_runtime = runtime.AgentRuntime(
        "user-1",
        SimpleNamespace(),
        "thread-1",
    )

    with pytest.raises(AppError) as exc_info:
        await anext(agent_runtime.astream([]))

    assert exc_info.value.code == ErrorCode.LLM_ERROR
