# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
from io import BytesIO
from types import SimpleNamespace

import pytest

from app.services import knowledge_ingestion, knowledge_service
from app.utils.enums import DocumentStatus, ErrorCode
from app.utils.exceptions import AppError
from app.utils.storage import milvus


def test_ingestion_uses_deterministic_chunk_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    path = tmp_path / "document.txt"
    path.write_text("第一段。第二段。", encoding="utf-8")
    batches: list[list[dict]] = []

    monkeypatch.setattr(
        knowledge_ingestion,
        "embed_documents",
        lambda chunks: [[0.1] for _ in chunks],
    )
    monkeypatch.setattr(
        knowledge_ingestion,
        "upsert_rows",
        lambda _collection, rows: batches.append(rows),
    )

    knowledge_ingestion.ingest_document("user-1", "document-1", path, ".txt")
    knowledge_ingestion.ingest_document("user-1", "document-1", path, ".txt")

    assert [row["id"] for row in batches[0]] == [row["id"] for row in batches[1]]


@pytest.mark.asyncio
async def test_failed_ingestion_cleans_partial_vectors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR", logger=knowledge_service.__name__)
    deleted: list[str] = []

    monkeypatch.setattr(
        knowledge_service,
        "delete_by_filter",
        lambda _collection, expr: deleted.append(expr),
    )
    monkeypatch.setattr(
        knowledge_service,
        "ingest_document",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("embedding failed")),
    )

    status, error = await knowledge_service._ingest(
        "user-1",
        "document-1",
        tmp_path / "document.txt",
        ".txt",
    )

    assert status == DocumentStatus.FAILED
    assert error == "embedding failed"
    assert deleted == [
        'user_id == "user-1" && document_id == "document-1"',
        'user_id == "user-1" && document_id == "document-1"',
    ]
    assert "知识文档入库失败: document_id=document-1" in caplog.text
    assert "RuntimeError: embedding failed" in caplog.text


@pytest.mark.asyncio
async def test_failed_ingestion_logs_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("ERROR", logger=knowledge_service.__name__)
    delete_calls = 0

    def delete_vectors(*_args):
        nonlocal delete_calls
        delete_calls += 1
        if delete_calls == 2:
            raise RuntimeError("cleanup failed")

    monkeypatch.setattr(knowledge_service, "delete_by_filter", delete_vectors)
    monkeypatch.setattr(
        knowledge_service,
        "ingest_document",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("embedding failed")),
    )

    status, error = await knowledge_service._ingest(
        "user-1",
        "document-1",
        tmp_path / "document.txt",
        ".txt",
    )

    assert status == DocumentStatus.FAILED
    assert error == "embedding failed; 清理失败: cleanup failed"
    assert "知识向量清理失败: document_id=document-1" in caplog.text
    assert "RuntimeError: cleanup failed" in caplog.text


@pytest.mark.asyncio
async def test_delete_knowledge_scopes_vector_cleanup_to_user(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    path = tmp_path / "document.txt"
    path.write_text("content", encoding="utf-8")
    document = SimpleNamespace(id="document-1", file_path=str(path), status="ready")
    filters: list[str] = []
    deleted_documents: list[str] = []

    class FakeSession:
        def add(self, _item):
            return None

        async def commit(self):
            return None

    async def get_owned(_db, document_id, user_id):
        assert (document_id, user_id) == ("document-1", "user-1")
        return document

    async def delete_document(_db, item):
        deleted_documents.append(item.id)

    monkeypatch.setattr(knowledge_service.knowledge_repository, "get_owned", get_owned)
    monkeypatch.setattr(knowledge_service.knowledge_repository, "delete", delete_document)
    monkeypatch.setattr(
        knowledge_service,
        "delete_by_filter",
        lambda _collection, expr: filters.append(expr),
    )

    await knowledge_service.delete_knowledge(
        FakeSession(),
        SimpleNamespace(id="user-1"),
        "document-1",
    )

    assert document.status == DocumentStatus.DELETING
    assert filters == ['user_id == "user-1" && document_id == "document-1"']
    assert deleted_documents == ["document-1"]
    assert not path.exists()


def test_store_upload_reads_in_chunks(tmp_path) -> None:
    class RecordingStream(BytesIO):
        def __init__(self, content: bytes) -> None:
            super().__init__(content)
            self.read_sizes: list[int] = []

        def read(self, size: int = -1) -> bytes:
            self.read_sizes.append(size)
            return super().read(size)

    source = RecordingStream(b"x" * (1024 * 1024 + 10))
    destination = tmp_path / "upload.txt"

    knowledge_service._store_upload(source, destination, 2 * 1024 * 1024)

    assert destination.stat().st_size == 1024 * 1024 + 10
    assert set(source.read_sizes) == {1024 * 1024}


def test_store_upload_removes_partial_file_when_too_large(tmp_path) -> None:
    destination = tmp_path / "upload.txt"

    with pytest.raises(AppError) as exc_info:
        knowledge_service._store_upload(
            BytesIO(b"too large"),
            destination,
            4,
        )

    assert exc_info.value.code == ErrorCode.FILE_TOO_LARGE
    assert not destination.exists()


def test_existing_milvus_collection_schema_is_validated() -> None:
    class FakeClient:
        def describe_collection(self, _name):
            return {
                "fields": [
                    {"name": "id"},
                    {"name": "user_id"},
                    {"name": "text"},
                    {"name": "embedding", "params": {"dim": 1}},
                ]
            }

    with pytest.raises(RuntimeError, match="schema 不兼容"):
        milvus._validate_collection(
            FakeClient(),
            milvus.KNOWLEDGE_COLLECTION,
            [("document_id", 64)],
        )
