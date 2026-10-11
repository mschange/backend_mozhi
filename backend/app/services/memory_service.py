"""长期记忆事实写入、检索与向量索引修复。"""

import asyncio
import logging
from hashlib import sha256

from app.agent.providers.embeddings import embed_documents, embed_query
from app.models.long_term_memory import LongTermMemory
from app.repositories import long_term_memory as memory_repository
from app.utils.storage.milvus import MEMORY_COLLECTION, search_vectors, upsert_rows
from app.utils.storage.mysql import AsyncSessionLocal

logger = logging.getLogger(__name__)


def normalize_content(content: str) -> str:
    return " ".join(content.split())


def content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def _index_memories(memories: list[LongTermMemory]) -> None:
    if not memories:
        return
    vectors = embed_documents([memory.content for memory in memories])
    upsert_rows(
        MEMORY_COLLECTION,
        [
            {
                "id": memory.id,
                "user_id": memory.user_id,
                "text": memory.content[:2000],
                "embedding": vector,
            }
            for memory, vector in zip(memories, vectors, strict=True)
        ],
    )


def _index_memory(memory: LongTermMemory) -> None:
    _index_memories([memory])


async def _set_index_result(
    user_id: str,
    memory_id: str,
    error: Exception | None,
) -> None:
    async with AsyncSessionLocal() as db:
        memory = await memory_repository.get_owned(db, memory_id, user_id)
        if memory is None:
            return
        if error is None:
            await memory_repository.mark_ready(db, memory)
        else:
            await memory_repository.mark_failed(db, memory, str(error))
        await db.commit()


async def _retry_indexes(user_id: str) -> None:
    async with AsyncSessionLocal() as db:
        memories = await memory_repository.list_retryable(db, user_id)
    for memory in memories:
        error: Exception | None = None
        try:
            await asyncio.to_thread(_index_memory, memory)
        except Exception as exc:
            logger.exception("长期记忆索引重试失败: memory_id=%s", memory.id)
            error = exc
        await _set_index_result(user_id, memory.id, error)


async def _rebuild_ready_indexes(user_id: str) -> None:
    async with AsyncSessionLocal() as db:
        memories = await memory_repository.list_ready(db, user_id)
    if not memories:
        return
    try:
        await asyncio.to_thread(_index_memories, memories)
    except Exception as exc:
        for memory in memories:
            await _set_index_result(user_id, memory.id, exc)
        raise


async def search_long_term_memory(user_id: str, query: str) -> str:
    """以 MySQL 为事实源过滤 Milvus 结果，并按向量顺序返回。"""
    await _retry_indexes(user_id)
    vector = await asyncio.to_thread(embed_query, query)
    hits = await asyncio.to_thread(
        search_vectors,
        MEMORY_COLLECTION,
        vector,
        user_id,
        20,
    )
    if not hits:
        await _rebuild_ready_indexes(user_id)
        hits = await asyncio.to_thread(
            search_vectors,
            MEMORY_COLLECTION,
            vector,
            user_id,
            20,
        )
    memory_ids = [str(hit["id"]) for hit in hits if hit.get("id")]
    async with AsyncSessionLocal() as db:
        memories = await memory_repository.get_owned_by_ids(
            db,
            user_id,
            memory_ids,
        )
    by_id = {memory.id: memory for memory in memories}
    ordered = [
        by_id[memory_id]
        for memory_id in memory_ids
        if memory_id in by_id
    ][:5]
    if not ordered:
        return "没有找到相关的长期记忆。"
    return "\n".join(
        f"[{index}] {memory.content}"
        for index, memory in enumerate(ordered, start=1)
    )


async def save_long_term_memory(user_id: str, fact: str) -> str:
    """先提交 MySQL 事实，再尽力维护可重建的 Milvus 索引。"""
    content = normalize_content(fact)
    if not content:
        return "未保存：内容为空。"
    async with AsyncSessionLocal() as db:
        memory, _ = await memory_repository.get_or_create(
            db,
            user_id,
            content,
            content_hash(content),
        )
        await db.commit()
        if memory.index_status == "ready":
            return "已写入长期记忆。"
        try:
            await asyncio.to_thread(_index_memory, memory)
        except Exception as exc:
            logger.exception("长期记忆索引写入失败: memory_id=%s", memory.id)
            await memory_repository.mark_failed(db, memory, str(exc))
            await db.commit()
            return "长期记忆已保存，向量索引暂时不可用。"
        await memory_repository.mark_ready(db, memory)
        await db.commit()
    return "已写入长期记忆。"
