"""用户表 users。

只存账号标识和密码哈希，不存明文。
一对多：一个用户拥有多条会话、多份知识库文档；用户删除时级联删掉。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    """登录用户。username、email 全局唯一，登录框两者都能用。"""

    __tablename__ = "users"
    __table_args__ = {"comment": "用户账号表：登录身份与密码哈希"}

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="用户主键 UUID",
    )
    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="登录用户名，唯一，长度 2–64",
    )
    email: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        comment="登录邮箱，唯一，可用于用户名栏登录",
    )
    password_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="bcrypt 密码哈希，禁止存明文",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="账号创建时间（UTC）",
    )

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    documents = relationship(
        "KnowledgeDocument", back_populates="user", cascade="all, delete-orphan"
    )
