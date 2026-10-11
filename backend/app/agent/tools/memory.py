"""长期记忆的 LangChain 工具适配器。"""

from langchain_core.tools import BaseTool, StructuredTool

from app.services import memory_service


def build_memory_tools(user_id: str) -> list[BaseTool]:
    async def search_long_term_memory(query: str) -> str:
        return await memory_service.search_long_term_memory(user_id, query)

    async def save_long_term_memory(fact: str) -> str:
        return await memory_service.save_long_term_memory(user_id, fact)

    return [
        StructuredTool.from_function(
            coroutine=search_long_term_memory,
            name="search_long_term_memory",
            description="检索当前用户的长期记忆（过往偏好、身份与长期约定）。",
        ),
        StructuredTool.from_function(
            coroutine=save_long_term_memory,
            name="save_long_term_memory",
            description="仅保存稳定的用户身份、偏好和长期约定，不保存普通聊天内容或知识库片段。",
        ),
    ]
