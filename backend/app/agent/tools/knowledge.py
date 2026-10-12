"""知识库检索的 LangChain 工具适配器。"""

from langchain_core.tools import BaseTool, StructuredTool

from app.services import knowledge_retrieval_service


def build_knowledge_tool(user_id: str) -> BaseTool:
    async def search_knowledge_base(query: str) -> str:
        return await knowledge_retrieval_service.search_knowledge_base(
            user_id,
            query,
        )

    return StructuredTool.from_function(
        coroutine=search_knowledge_base,
        name="search_knowledge_base",
        description="在当前用户的知识库中检索与问题相关的文档片段。当用户问题可能与已上传资料有关时使用。",
    )
