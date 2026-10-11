"""DeepSeek 聊天模型构造与进程级复用。"""

import logging

from langchain.chat_models import init_chat_model

from app.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    apply_runtime_env,
    deepseek_openai_base_url,
)

logger = logging.getLogger(__name__)
_chat_model = None


def _build_chat_model():
    apply_runtime_env()
    common = {
        "model": DEEPSEEK_MODEL,
        "model_provider": "openai",
        "api_key": DEEPSEEK_API_KEY,
        "base_url": deepseek_openai_base_url(),
        "streaming": True,
        "temperature": 0.3,
    }
    try:
        return init_chat_model(
            **common,
            extra_body={"thinking": {"type": "disabled"}},
        )
    except TypeError:
        return init_chat_model(**common)


def get_chat_model():
    global _chat_model
    if _chat_model is None:
        _chat_model = _build_chat_model()
    return _chat_model


def init_chat_provider() -> None:
    apply_runtime_env()
    if not DEEPSEEK_API_KEY:
        logger.warning("未配置 DEEPSEEK_API_KEY / OPENAI_API_KEY，对话模型未预热")
        return
    get_chat_model()
    logger.info("聊天模型已就绪：%s", DEEPSEEK_MODEL)
