"""Agent 模型调用中间件。"""

from collections.abc import Awaitable, Callable

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.messages import trim_messages

from app.config import SHORT_TERM_MEMORY_N


@wrap_model_call
async def trim_model_context(
    request: ModelRequest,
    handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
) -> ModelResponse:
    """仅保留最近消息，限制每次模型调用的短期上下文。"""
    messages = trim_messages(
        request.messages,
        max_tokens=SHORT_TERM_MEMORY_N,
        token_counter=len,
        strategy="last",
        start_on="human",
    )
    return await handler(request.override(messages=messages))
