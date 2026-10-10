"""对话相关入参/出参，接口资源名为 chat。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatCreateIn(BaseModel):
    """创建会话。标题可空，空则用「新对话」；若已有空会话则复用，不新建。"""

    title: str | None = Field(default=None, max_length=128, description="可选标题，最多 128 字；空则「新对话」")


class ChatIdIn(BaseModel):
    """只带会话 ID 的请求，例如删除。"""

    chat_id: str = Field(description="会话 ID（conversations.id）")


class ChatRenameIn(BaseModel):
    """手动修改会话标题。改完后首条消息不会再覆盖，除非标题仍是「新对话」。"""

    chat_id: str = Field(description="要改名的会话 ID")
    title: str = Field(min_length=1, max_length=128, description="新标题，去空白后不能为空，最多 128 字")


class ChatSendIn(BaseModel):
    """发送一条用户消息（非流式 / 流式共用）。"""

    chat_id: str = Field(description="目标会话 ID")
    content: str = Field(min_length=1, max_length=8000, description="用户输入正文，1–8000 字")


class MessageOut(BaseModel):
    """一条消息的对外形状。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="消息 UUID")
    role: str = Field(description="user 或 assistant")
    content: str = Field(description="消息正文")
    citations: list[dict] | None = Field(default=None, description="引用片段列表，无则为 null")
    created_at: datetime | None = Field(default=None, description="写入时间")


class ChatOut(BaseModel):
    """会话列表项。message_count 来自聚合，不是表字段。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="会话 UUID，即 chat_id")
    title: str = Field(description="会话标题")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="最近活跃时间")
    message_count: int = Field(default=0, description="该会话消息条数，用于判断是否空会话")


class ChatDetailOut(ChatOut):
    """会话详情：列表字段 + 全部消息（按时间正序）。"""

    messages: list[MessageOut] = Field(default_factory=list, description="该会话下的全部消息")
