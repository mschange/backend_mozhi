"""知识库文档元数据表。向量本身在 Milvus，这里只存文件状态。"""

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeDocument


async def create(
    db: AsyncSession,
    user_id: str,
    filename: str,
    content_type: str,
    file_path: str,
    status: str,
) -> KnowledgeDocument:
    doc = KnowledgeDocument(
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        file_path=file_path,
        status=status,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc


async def list_by_user(db: AsyncSession, user_id: str) -> list[KnowledgeDocument]:
    stmt = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.user_id == user_id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def get_owned(db: AsyncSession, document_id: str, user_id: str) -> KnowledgeDocument | None:
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.id == document_id,
        KnowledgeDocument.user_id == user_id,
    )
    return await db.scalar(stmt)


async def get_ready_owned_by_ids(
    db: AsyncSession,
    user_id: str,
    document_ids: list[str],
) -> list[KnowledgeDocument]:
    if not document_ids:
        return []
    stmt = select(KnowledgeDocument).where(
        KnowledgeDocument.user_id == user_id,
        KnowledgeDocument.id.in_(document_ids),
        KnowledgeDocument.status == "ready",
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def delete(db: AsyncSession, doc: KnowledgeDocument) -> None:
    await db.execute(sql_delete(KnowledgeDocument).where(KnowledgeDocument.id == doc.id))
    await db.flush()
