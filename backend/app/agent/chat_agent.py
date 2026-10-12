"""LangChain Agent 组装与正文流式输出。"""

import logging
from collections.abc import AsyncIterator

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agent.messages import chunk_text
from app.agent.middleware import trim_model_context
from app.agent.providers.chat import get_chat_model
from app.agent.providers.fallback import curl_stream
from app.agent.tools.registry import DEFAULT_TOOL_NAMES, get_tools_by_names

logger = logging.getLogger(__name__)


class ChatAgent:
    def __init__(
        self,
        system_prompt: str,
        tool_names: list[str],
        user_id: str,
        checkpointer: AsyncPostgresSaver | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.checkpointer = checkpointer
        self.agent = create_agent(
            model=get_chat_model(),
            tools=get_tools_by_names(
                tool_names or DEFAULT_TOOL_NAMES,
                user_id,
            ),
            system_prompt=system_prompt,
            middleware=[trim_model_context],
            checkpointer=checkpointer,
        )

    async def astream_tokens(
        self,
        history: list[BaseMessage],
        thread_id: str,
    ) -> AsyncIterator[str]:
        emitted = False
        try:
            async for item in self.agent.astream(
                {"messages": history},
                config={"configurable": {"thread_id": thread_id}},
                stream_mode="messages",
            ):
                chunk, metadata = (
                    item if isinstance(item, tuple) else (item, {})
                )
                node = ""
                if isinstance(metadata, dict):
                    node = str(
                        metadata.get("langgraph_node")
                        or metadata.get("checkpoint_ns")
                        or ""
                    )
                if node and "tool" in node.lower():
                    continue
                text = chunk_text(chunk)
                if text:
                    emitted = True
                    yield text
            return
        except Exception as exc:
            # checkpoint 或部分正文已产生时回退会造成状态丢失或重复输出。
            if self.checkpointer is not None or emitted:
                raise
            logger.warning("create_agent 流式失败，回退 curl 流式：%s", exc)

        async for text in curl_stream(history, self.system_prompt):
            yield text
