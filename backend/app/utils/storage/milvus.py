"""Milvus 向量索引适配器。

knowledge_chunks 保存文档切片，long_term_memory 保存用户事实。默认连接
backend/milvus.db 的 Lite 实例，也接受 config.milvus_path() 返回的 HTTP URI。
检索始终带 user_id 过滤；业务所有权和状态仍由 MySQL 回查确认。
"""

from __future__ import annotations

import os
from typing import Any

# 禁止 pymilvus 使用宿主机遗留的默认 URI，连接目标只由显式配置决定。
os.environ.pop("MILVUS_URI", None)

from pymilvus import DataType, MilvusClient

from app.config import EMBEDDING_DIM, milvus_path

KNOWLEDGE_COLLECTION = "knowledge_chunks"
MEMORY_COLLECTION = "long_term_memory"

# 客户端按进程复用；close_milvus() 后清空，以便测试或新生命周期重新初始化。
_client: MilvusClient | None = None


def get_milvus() -> MilvusClient:
    """返回惰性单例客户端；uri 可以是 Lite 本地路径或 HTTP/HTTPS 服务地址。"""
    global _client
    if _client is None:
        _client = MilvusClient(uri=milvus_path())
    return _client


def _validate_collection(
    client: MilvusClient,
    name: str,
    extra_fields: list[tuple[str, int]],
) -> None:
    """拒绝缺字段或向量维度不兼容的既有 collection，避免破坏性重建。"""
    description = client.describe_collection(name)
    fields = {field["name"]: field for field in description.get("fields", [])}
    required_fields = {"id", "user_id", "text", "embedding"}
    required_fields.update(field_name for field_name, _ in extra_fields)
    missing = required_fields.difference(fields)
    dimension = fields.get("embedding", {}).get("params", {}).get("dim")
    if missing or int(dimension or 0) != EMBEDDING_DIM:
        raise RuntimeError(
            f"Milvus collection {name} schema 不兼容："
            f"missing={sorted(missing)}, embedding_dim={dimension}"
        )


def _ensure_collection(client: MilvusClient, name: str, extra_fields: list[tuple[str, int]]) -> None:
    """校验现有 collection，或以固定 schema/index 创建后加载到可搜索状态。"""
    if client.has_collection(name):
        _validate_collection(client, name, extra_fields)
    else:
        # 禁用 auto_id 和动态字段，使写入结构、主键及跨库映射保持可预测。
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("user_id", DataType.VARCHAR, max_length=64)
        for field_name, max_len in extra_fields:
            schema.add_field(field_name, DataType.VARCHAR, max_length=max_len)
        schema.add_field("text", DataType.VARCHAR, max_length=8192)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)

        # 当前规模使用 COSINE + FLAT 精确扫描，不引入近似索引的召回参数。
        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="FLAT",
            metric_type="COSINE",
        )
        client.create_collection(
            collection_name=name,
            schema=schema,
            index_params=index_params,
        )
    # 新建和已存在 collection 都显式 load，确保后续 search 可立即使用。
    client.load_collection(name)


def init_milvus() -> None:
    """确保知识切片和长期记忆两个 collection 存在、兼容且已加载。"""
    client = get_milvus()
    _ensure_collection(client, KNOWLEDGE_COLLECTION, [("document_id", 64)])
    _ensure_collection(client, MEMORY_COLLECTION, [])


def close_milvus() -> None:
    """关闭客户端并清空单例；不删除 collection 或其中数据。"""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def upsert_rows(collection: str, rows: list[dict[str, Any]]) -> None:
    """按外部主键写入或更新向量行；空批次不向 Milvus 发请求。"""
    if not rows:
        return
    get_milvus().upsert(collection_name=collection, data=rows)


def delete_by_filter(collection: str, expr: str) -> None:
    """按调用方构造的过滤表达式删除索引；业务层负责同时约束 user_id。"""
    get_milvus().delete(collection_name=collection, filter=expr)


def search_vectors(
    collection: str,
    vector: list[float],
    user_id: str,
    limit: int = 5,
    extra_filter: str | None = None,
) -> list[dict[str, Any]]:
    """检索当前用户向量；知识命中额外携带 document_id 供 MySQL 回查。"""
    client = get_milvus()
    # user_id 是所有向量查询的强制条件，extra_filter 只能在此基础上继续收窄。
    expr = f'user_id == "{user_id}"'
    if extra_filter:
        expr = f"{expr} && {extra_filter}"
    results = client.search(
        collection_name=collection,
        data=[vector],
        filter=expr,
        limit=limit,
        output_fields=["id", "user_id", "text", "document_id"]
        if collection == KNOWLEDGE_COLLECTION
        else ["id", "user_id", "text"],
    )
    hits: list[dict[str, Any]] = []
    if not results:
        return hits
    # 兼容 pymilvus 返回 dict 或带属性对象的两种命中表示。
    for hit in results[0]:
        entity = hit.get("entity") if isinstance(hit, dict) else getattr(hit, "entity", {})
        if hasattr(entity, "items"):
            entity = dict(entity)
        elif entity is None:
            entity = {}
        distance = hit.get("distance") if isinstance(hit, dict) else getattr(hit, "distance", None)
        hits.append(
            {
                "id": entity.get("id"),
                "text": entity.get("text"),
                "document_id": entity.get("document_id"),
                "distance": distance,
            }
        )
    return hits
