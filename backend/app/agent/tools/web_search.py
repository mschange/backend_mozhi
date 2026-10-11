"""可选的公开互联网搜索工具。"""

from langchain_core.tools import BaseTool

from app.config import TAVILY_API_KEY


def build_web_search_tool() -> BaseTool | None:
    """仅在配置 Tavily 时注册，依赖缺失不影响其他 Agent 工具。"""
    if not TAVILY_API_KEY:
        return None
    try:
        from langchain_tavily import TavilySearch

        tool = TavilySearch(max_results=3, tavily_api_key=TAVILY_API_KEY)
    except Exception:
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults

            tool = TavilySearchResults(
                max_results=3,
                tavily_api_key=TAVILY_API_KEY,
            )
        except Exception:
            return None
    tool.name = "web_search"
    tool.description = "在互联网上搜索最新公开信息。仅在知识库无法回答、且问题需要外部资料时使用。"
    return tool
