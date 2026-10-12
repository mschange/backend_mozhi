"""知识库向量检索与 MySQL 状态对账。"""

import asyncio

from app.agent.providers.embeddings import embed_query
from app.repositories import knowledge as knowledge_repository
from app.utils.storage.milvus import KNOWLEDGE_COLLECTION, search_vectors
from app.utils.storage.mysql import AsyncSessionLocal


def _format_hits(hits: list[dict], empty_message: str) -> str:
    if not hits:
        return empty_message
    lines = []
    for index, hit in enumerate(hits, start=1):
        snippet = (hit.get("text") or "").strip().replace("\n", " ")
        document_id = hit.get("document_id") or ""
        prefix = f"[{index}]"
        if document_id:
            prefix += f" document_id={document_id}"
        lines.append(f"{prefix} {snippet}")
    return "\n".join(lines)


async def search_knowledge_base(user_id: str, query: str) -> str:
    """回查 MySQL，只返回当前用户状态为 ready 的文档片段。"""
    vector = await asyncio.to_thread(embed_query, query)
    hits = await asyncio.to_thread(
        search_vectors,
        KNOWLEDGE_COLLECTION,
        vector,
        user_id,
        20,
    )
    document_ids = list(
        dict.fromkeys(
            hit["document_id"]
            for hit in hits
            if hit.get("document_id")
        )
    )
    async with AsyncSessionLocal() as db:
        documents = await knowledge_repository.get_ready_owned_by_ids(
            db,
            user_id,
            document_ids,
        )
    ready_ids = {document.id for document in documents}
    valid_hits = [
        hit for hit in hits if hit.get("document_id") in ready_ids
    ][:5]
    return _format_hits(
        valid_hits,
        "当前用户知识库中没有检索到相关内容。",
    )
