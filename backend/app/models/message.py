"""消息表 messages。

一条消息属于一次会话。role 区分用户与助手。
citations 存 JSON 字符串（引用片段），不是关系表；当前流式接口多数时候为 NULL。
删会话时先删消息，避免外键卡住。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Message(Base):
    """对话中的一条消息，按 created_at 正序展示；Agent 短时记忆取最近 N 条。"""

    __tablename__ = "messages"
    __table_args__ = {"comment": "对话消息表：用户提问与助手回答"}

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="消息主键 UUID",
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
        comment="所属会话 ID（conversations.id）",
    )
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="发言角色：user=用户，assistant=助手",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息正文。用户消息来自输入框；助手消息由 Agent 流式拼完后落库",
    )
    citations: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="引用依据 JSON 数组字符串，如 [{\"source\",\"snippet\"}]；无引用则为 NULL",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="消息写入时间（UTC），列表与短时记忆按此排序",
    )

    conversation = relationship("Conversation", back_populates="messages")
