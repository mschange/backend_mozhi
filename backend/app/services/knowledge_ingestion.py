"""知识库入库流水线：原文 → 切分 → 嵌入 → 写入 Milvus。

由 `services/knowledge.upload_knowledge` 在线程池里调用（asyncio.to_thread），
因为 PDF 解析和批量嵌入是同步、偏 CPU/IO 的工作，不能堵死事件循环。

切分策略：
- chunk_size=500、overlap=80，按中文标点和换行优先切开
- 单文档最多取前 200 段，防止超大 PDF 把嵌入配额打满
- 写入 collection=`knowledge_chunks`，字段带 user_id + document_id，检索时按用户过滤
"""

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.agent.providers.embeddings import embed_documents
from app.utils.storage.milvus import KNOWLEDGE_COLLECTION, upsert_rows


def extract_text(path: Path, suffix: str) -> str:
    """按后缀抽文本。pdf 用 pypdf 逐页 extract_text；扫描件可能抽不到字。"""
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)
    raise ValueError("不支持的文件类型")


def ingest_document(user_id: str, document_id: str, path: Path, suffix: str) -> int:
    """完成一份文档的向量化入库，返回写入的 chunk 数。失败由调用方标 status=failed。"""
    text = extract_text(path, suffix).strip()
    if not text:
        raise ValueError("未能从文件中提取到文本，请检查文件内容")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""],
    )
    chunks = splitter.split_text(text)[:200]
    if not chunks:
        raise ValueError("文档切分结果为空")

    vectors = embed_documents(chunks)
    rows = []
    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        rows.append(
            {
                "id": uuid5(NAMESPACE_URL, f"{document_id}:{index}").hex,
                "user_id": user_id,
                "document_id": document_id,
                "text": chunk[:2000],
                "embedding": vector,
            }
        )
    upsert_rows(KNOWLEDGE_COLLECTION, rows)
    return len(rows)
