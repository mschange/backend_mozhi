"""知识库接口：列表 / 上传（同步解析+嵌入） / 删除（MySQL + Milvus + 本地文件）。"""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.knowledge import KnowledgeDeleteIn
from app.services.knowledge_service import delete_knowledge, list_knowledge, upload_knowledge
from app.utils.http.dependencies import get_db
from app.utils.http.response import success_response

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.get("/list")
async def list_documents(
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
):
    data = await list_knowledge(db, current)
    return success_response(message="获取成功", data=data)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
):
    data = await upload_knowledge(db, current, file)
    return success_response(message="上传成功", data=data)


@router.post("/delete")
async def delete_document(
    body: KnowledgeDeleteIn,
    db: AsyncSession = Depends(get_db, scope="function"),
    current: User = Depends(get_current_user),
):
    await delete_knowledge(db, current, body.document_id)
    return success_response(message="删除成功", data=None)
