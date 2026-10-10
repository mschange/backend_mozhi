"""知识库文档元数据表 knowledge_documents。

这里只记文件身份、本地路径和处理状态。
切片文本与向量在 Milvus collection `knowledge_chunks`，用 document_id + user_id 关联。
status：processing → ready / failed，删除时为 deleting；失败时 error_message 写原因。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class KnowledgeDocument(Base):
    """用户上传的一份知识库文件。删除时同步清 Milvus 切片和本地 uploads 文件。"""

    __tablename__ = "knowledge_documents"
    __table_args__ = {"comment": "知识库文档元数据，向量本体在 Milvus"}

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="文档主键 UUID，写入 Milvus 时作为 document_id",
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="所属用户 ID，检索与删除必须按用户隔离",
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="用户上传时的原始文件名，用于列表展示",
    )
    content_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="",
        comment="MIME 或后缀，如 application/pdf、.md",
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="服务器本地存储路径（uploads/ 下 UUID 文件名，不是原始名）",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="processing",
        comment="处理状态：processing=解析嵌入中，ready=可检索，failed=失败，deleting=删除中",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="status=failed 时的错误摘要，成功则为 NULL",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="上传时间（UTC），列表按此倒序",
    )

    user = relationship("User", back_populates="documents")
