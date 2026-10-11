"""嵌入模型接入与本地哈希回退。"""

from __future__ import annotations

import hashlib
import logging

import numpy as np
from langchain_openai import OpenAIEmbeddings

from app.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DEEPSEEK_API_KEY,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    deepseek_openai_base_url,
)

logger = logging.getLogger(__name__)
DASHSCOPE_EMBED_BATCH = 10
_use_local_embeddings: bool | None = None


def _remote_embeddings() -> OpenAIEmbeddings:
    api_key = DASHSCOPE_API_KEY or DEEPSEEK_API_KEY or OPENAI_API_KEY
    base_url = (
        DASHSCOPE_BASE_URL
        if DASHSCOPE_API_KEY
        else deepseek_openai_base_url()
    )
    return OpenAIEmbeddings(
        api_key=api_key,
        base_url=base_url,
        model=EMBEDDING_MODEL,
        check_embedding_ctx_length=False,
        chunk_size=DASHSCOPE_EMBED_BATCH,
        max_retries=1,
    )


def _hash_embed(text: str) -> list[float]:
    """外部服务不可用时生成维度兼容的可检索向量。"""
    vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    cleaned = text.strip()
    grams = [*cleaned.split(), *cleaned]
    grams.extend(
        cleaned[index : index + 2]
        for index in range(max(len(cleaned) - 1, 0))
    )
    for token in grams:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        position = int.from_bytes(digest[:4], "little") % EMBEDDING_DIM
        vector[position] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = float(np.linalg.norm(vector))
    if norm:
        vector /= norm
    return vector.tolist()


def init_embeddings() -> None:
    """启动时探测嵌入服务，避免首次上传或检索才失败。"""
    _choose_embeddings()


def _choose_embeddings() -> None:
    global _use_local_embeddings
    if _use_local_embeddings is not None:
        return
    try:
        _remote_embeddings().embed_query("ping")
        _use_local_embeddings = False
        logger.info("使用远程嵌入模型 %s", EMBEDDING_MODEL)
    except Exception as exc:
        _use_local_embeddings = True
        logger.warning("远程嵌入不可用，回退本地哈希向量：%s", exc)


def embed_query(text: str) -> list[float]:
    _choose_embeddings()
    if _use_local_embeddings:
        return _hash_embed(text)
    return _remote_embeddings().embed_query(text)


def embed_documents(texts: list[str]) -> list[list[float]]:
    """按远端限制分批嵌入，单批最多十条。"""
    if not texts:
        return []
    _choose_embeddings()
    if _use_local_embeddings:
        return [_hash_embed(text) for text in texts]
    embeddings = _remote_embeddings()
    vectors: list[list[float]] = []
    for index in range(0, len(texts), DASHSCOPE_EMBED_BATCH):
        batch = texts[index : index + DASHSCOPE_EMBED_BATCH]
        vectors.extend(embeddings.embed_documents(batch))
    return vectors
