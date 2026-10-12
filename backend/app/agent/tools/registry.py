"""按用户组装和筛选 Agent 工具。"""

from langchain_core.tools import BaseTool

from app.agent.tools.knowledge import build_knowledge_tool
from app.agent.tools.memory import build_memory_tools
from app.agent.tools.web_search import build_web_search_tool

DEFAULT_TOOL_NAMES = [
    "search_knowledge_base",
    "search_long_term_memory",
    "save_long_term_memory",
    "web_search",
]


def build_tools(user_id: str) -> list[BaseTool]:
    tools = [build_knowledge_tool(user_id), *build_memory_tools(user_id)]
    web_search = build_web_search_tool()
    if web_search is not None:
        tools.append(web_search)
    return tools


def get_tools_by_names(
    tool_names: list[str],
    user_id: str,
) -> list[BaseTool]:
    mapping = {tool.name: tool for tool in build_tools(user_id)}
    return [mapping[name] for name in tool_names if name in mapping]
