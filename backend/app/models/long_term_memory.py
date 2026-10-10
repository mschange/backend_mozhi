"""长期记忆事实表，Milvus 仅保存对应向量索引。"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LongTermMemory(Base):
    __tablename__ = "long_term_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "content_hash", name="uq_memory_user_content_hash"),
        CheckConstraint(
            "index_status IN ('pending', 'ready', 'failed')",
            name="ck_memory_index_status",
        ),
        {"comment": "长期记忆事实正文与 Milvus 索引状态"},
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    index_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
