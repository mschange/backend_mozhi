"""业务对话与 LangChain Agent 之间的运行时边界。"""

import logging
from collections.abc import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agent.chat_agent import ChatAgent
from app.agent.messages import history_to_lc
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools.registry import DEFAULT_TOOL_NAMES
from app.models.message import Message
from app.utils.enums import ErrorCode
from app.utils.exceptions import AppError

logger = logging.getLogger(__name__)


class AgentRuntime:
    """一次对话请求一个实例，隔离用户工具上下文。"""

    def __init__(
        self,
        user_id: str,
        checkpointer: AsyncPostgresSaver,
        thread_id: str,
        tool_names: list[str] | None = None,
    ) -> None:
        self.thread_id = thread_id
        self.agent = ChatAgent(
            system_prompt=SYSTEM_PROMPT,
            tool_names=tool_names or DEFAULT_TOOL_NAMES,
            user_id=user_id,
            checkpointer=checkpointer,
        )

    async def astream(
        self,
        history: list[Message],
    ) -> AsyncIterator[str]:
        try:
            async for token in self.agent.astream_tokens(
                history_to_lc(history),
                self.thread_id,
            ):
                yield token
        except Exception as exc:
            logger.exception("Agent 流式调用失败")
            raise AppError(
                ErrorCode.LLM_ERROR,
                "模型服务暂时不可用，请稍后重试",
            ) from exc
