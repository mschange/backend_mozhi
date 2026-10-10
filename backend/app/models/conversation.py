"""会话表 conversations。

对外 HTTP 资源叫 chat（/api/chat），落库表名仍是 conversations，避免和聊天消息语义混淆。
一条会话属于一个用户，下面挂多条 messages。
默认标题「新对话」：空会话会复用；首条用户消息或手动 rename 后才会改掉。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Conversation(Base):
    """一次多轮对话。列表按 updated_at 倒序；发消息、改标题都会刷新该字段。"""

    __tablename__ = "conversations"
    __table_args__ = {"comment": "对话会话表，对应接口 /api/chat"}

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="会话主键 UUID，接口里叫 chat_id",
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="所属用户 ID，查询/改删都必须带归属校验",
    )
    title: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="新对话",
        comment="会话标题。默认「新对话」；可手动改，或首条消息自动截前 24 字",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="会话创建时间（UTC）",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="最近活跃时间（UTC）：发消息、改标题时更新，用于列表排序",
    )

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
