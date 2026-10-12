"""知识库业务：校验文件 → 落盘 → MySQL 元数据 → ingest 向量化。"""

import asyncio
import logging
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge_ingestion import ingest_document
from app.config import MAX_UPLOAD_MB, upload_path
from app.utils.storage.milvus import KNOWLEDGE_COLLECTION, delete_by_filter
from app.models.user import User
from app.repositories import knowledge as knowledge_repository
from app.schemas.knowledge import KnowledgeDocumentOut
from app.utils.enums import DocumentStatus, ErrorCode
from app.utils.exceptions import AppError

logger = logging.getLogger(__name__)
ALLOWED_SUFFIX = {".txt", ".md", ".pdf"}


def _vector_filter(user_id: str, document_id: str) -> str:
    return f'user_id == "{user_id}" && document_id == "{document_id}"'


def _store_upload(source: BinaryIO, destination: Path, max_bytes: int) -> None:
    size = 0
    try:
        with destination.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(
                        ErrorCode.FILE_TOO_LARGE,
                        f"文件不能超过 {MAX_UPLOAD_MB} MB",
                    )
                target.write(chunk)
        if size == 0:
            raise AppError(ErrorCode.UNSUPPORTED_FILE, "文件内容为空")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


async def _ingest(
    user_id: str,
    document_id: str,
    path: Path,
    suffix: str,
) -> tuple[str, str | None]:
    vector_filter = _vector_filter(user_id, document_id)
    try:
        await asyncio.to_thread(
            delete_by_filter,
            KNOWLEDGE_COLLECTION,
            vector_filter,
        )
        await asyncio.to_thread(
            ingest_document,
            user_id,
            document_id,
            path,
            suffix,
        )
        return DocumentStatus.READY, None
    except Exception as exc:
        logger.exception("知识文档入库失败: document_id=%s", document_id)
        error_message = str(exc) or "文档解析失败"
        try:
            await asyncio.to_thread(
                delete_by_filter,
                KNOWLEDGE_COLLECTION,
                vector_filter,
            )
        except Exception as cleanup_exc:
            logger.exception("知识向量清理失败: document_id=%s", document_id)
            error_message = f"{error_message}; 清理失败: {cleanup_exc}"
        return DocumentStatus.FAILED, error_message[:500]


async def list_knowledge(db: AsyncSession, user: User) -> list[KnowledgeDocumentOut]:
    items = await knowledge_repository.list_by_user(db, user.id)
    return [KnowledgeDocumentOut.model_validate(d) for d in items]


async def upload_knowledge(db: AsyncSession, user: User, file: UploadFile) -> KnowledgeDocumentOut:
    """上传并同步入库。失败不回滚文件元数据，status=failed 并带 error_message。"""
    filename = file.filename or "未命名文件"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise AppError(ErrorCode.UNSUPPORTED_FILE, "仅支持 txt、md、pdf 文件")

    dest_dir = upload_path()
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{suffix}"
    dest = dest_dir / stored_name
    await asyncio.to_thread(
        _store_upload,
        file.file,
        dest,
        MAX_UPLOAD_MB * 1024 * 1024,
    )

    try:
        doc = await knowledge_repository.create(
            db,
            user_id=user.id,
            filename=filename,
            content_type=file.content_type or suffix,
            file_path=str(dest),
            status=DocumentStatus.PROCESSING,
        )
        await db.commit()
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    doc.status, doc.error_message = await _ingest(
        user.id,
        doc.id,
        dest,
        suffix,
    )
    db.add(doc)
    return KnowledgeDocumentOut.model_validate(doc)


async def reindex_document(
    db: AsyncSession,
    user: User,
    document_id: str,
) -> KnowledgeDocumentOut:
    doc = await knowledge_repository.get_owned(db, document_id, user.id)
    if doc is None:
        raise AppError(ErrorCode.NOT_FOUND, "文档不存在")
    path = Path(doc.file_path)
    doc.status = DocumentStatus.PROCESSING
    doc.error_message = None
    db.add(doc)
    await db.commit()
    doc.status, doc.error_message = await _ingest(
        user.id,
        doc.id,
        path,
        path.suffix.lower(),
    )
    db.add(doc)
    return KnowledgeDocumentOut.model_validate(doc)


async def delete_knowledge(db: AsyncSession, user: User, document_id: str) -> None:
    """删除元数据、向量切片和本地原文件。"""
    doc = await knowledge_repository.get_owned(db, document_id, user.id)
    if doc is None:
        raise AppError(ErrorCode.NOT_FOUND, "文档不存在")
    doc.status = DocumentStatus.DELETING
    db.add(doc)
    await db.commit()
    await asyncio.to_thread(
        delete_by_filter,
        KNOWLEDGE_COLLECTION,
        _vector_filter(user.id, document_id),
    )
    path = Path(doc.file_path)
    if path.exists():
        path.unlink()
    await knowledge_repository.delete(db, doc)
