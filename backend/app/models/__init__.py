"""SQLAlchemy ORM 模型。

表与对外 API 的对应关系：
- users              → 注册/登录用户
- conversations      → 对话（接口资源名是 /api/chat）
- messages           → 对话里的一条消息
- knowledge_documents → 知识库文件元数据（向量在 Milvus，不在这张表）
"""

from app.models.base import Base
from app.models.conversation import Conversation
from app.models.conversation_checkpoint import ConversationCheckpoint
from app.models.knowledge import KnowledgeDocument
from app.models.long_term_memory import LongTermMemory
from app.models.message import Message
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Conversation",
    "ConversationCheckpoint",
    "Message",
    "KnowledgeDocument",
    "LongTermMemory",
]
