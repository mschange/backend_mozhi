"""知识库相关入参/出参。

上传走 multipart（UploadFile），没有单独的 UploadIn。
列表/上传成功返回 KnowledgeDocumentOut；删除只需要 document_id。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentOut(BaseModel):
    """知识库文档对外信息。不含本地 file_path，避免暴露存储路径。"""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="文档 UUID，删除和 Milvus document_id 用这个")
    filename: str = Field(description="原始文件名")
    status: str = Field(description="processing / ready / failed")
    error_message: str | None = Field(default=None, description="失败原因；成功为 null")
    created_at: datetime | None = Field(default=None, description="上传时间")


class KnowledgeDeleteIn(BaseModel):
    """删除一份知识库文档。"""

    document_id: str = Field(description="要删除的文档 ID，必须属于当前用户")
