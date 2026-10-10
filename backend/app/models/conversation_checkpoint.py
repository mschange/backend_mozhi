"""MySQL 中的 LangGraph checkpoint 同步水位。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ConversationCheckpoint(Base):
    __tablename__ = "conversation_checkpoints"
    __table_args__ = {"comment": "MySQL 消息与 PostgreSQL checkpoint 的同步水位"}

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    thread_id: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        unique=True,
    )
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False)
    last_message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
