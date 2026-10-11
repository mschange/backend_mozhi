"""业务消息与模型消息之间的转换。"""

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.models.message import Message


def history_to_lc(history: list[Message]) -> list[BaseMessage]:
    """按数据库时间顺序转换历史消息。"""
    messages: list[BaseMessage] = []
    for item in history:
        if item.role == "user":
            messages.append(HumanMessage(content=item.content, id=item.id))
        elif item.role == "assistant":
            messages.append(AIMessage(content=item.content, id=item.id))
    return messages


def chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part if isinstance(part, str) else str(part.get("text") or "")
            for part in content
            if isinstance(part, str)
            or isinstance(part, dict) and part.get("type") == "text"
        )
    return ""
