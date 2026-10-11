"""将现有 Milvus 长期记忆正文一次性回填到 MySQL。"""

import asyncio
from hashlib import sha256

from app.utils.storage.milvus import MEMORY_COLLECTION, close_milvus, get_milvus
from app.utils.storage.mysql import AsyncSessionLocal, close_mysql, init_mysql
from app.models.long_term_memory import LongTermMemory
from app.repositories import long_term_memory as memory_repository


def normalize_content(content: str) -> str:
    return " ".join(content.split())


async def migrate_batch(rows: list[dict]) -> tuple[int, int]:
    created = 0
    skipped = 0
    seen_ids: set[str] = set()
    seen_facts: set[tuple[str, str]] = set()
    async with AsyncSessionLocal() as db:
        for row in rows:
            memory_id = str(row.get("id") or "")
            user_id = str(row.get("user_id") or "")
            content = normalize_content(str(row.get("text") or ""))
            if not memory_id or not user_id or not content:
                skipped += 1
                continue
            content_hash = sha256(content.encode("utf-8")).hexdigest()
            fact_key = (user_id, content_hash)
            if memory_id in seen_ids or fact_key in seen_facts:
                skipped += 1
                continue
            existing = await db.get(LongTermMemory, memory_id)
            if existing is None:
                existing = await memory_repository.get_by_hash(
                    db,
                    user_id,
                    content_hash,
                )
            if existing is not None:
                skipped += 1
                continue
            db.add(
                LongTermMemory(
                    id=memory_id,
                    user_id=user_id,
                    content=content,
                    content_hash=content_hash,
                    index_status="ready",
                )
            )
            seen_ids.add(memory_id)
            seen_facts.add(fact_key)
            created += 1
        await db.commit()
    return created, skipped


async def main() -> None:
    await init_mysql()
    iterator = get_milvus().query_iterator(
        collection_name=MEMORY_COLLECTION,
        batch_size=500,
        filter="",
        output_fields=["id", "user_id", "text"],
    )
    created = 0
    skipped = 0
    try:
        while True:
            rows = iterator.next()
            if not rows:
                break
            batch_created, batch_skipped = await migrate_batch(rows)
            created += batch_created
            skipped += batch_skipped
    finally:
        iterator.close()
        close_milvus()
        await close_mysql()
    print(f"迁移完成：新增 {created} 条，跳过 {skipped} 条。")


if __name__ == "__main__":
    asyncio.run(main())
