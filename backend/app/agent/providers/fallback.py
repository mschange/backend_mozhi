"""聊天模型直连流式回退。"""

import asyncio
import json
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_MODEL, deepseek_openai_base_url


def _history_to_openai(
    history: list[BaseMessage],
    system_prompt: str,
) -> list[dict[str, str]]:
    rows = [{"role": "system", "content": system_prompt}]
    for item in history:
        if isinstance(item, HumanMessage):
            rows.append({"role": "user", "content": str(item.content)})
        elif isinstance(item, AIMessage):
            rows.append({"role": "assistant", "content": str(item.content or "")})
        elif isinstance(item, SystemMessage):
            continue
    return rows


def _delta_text(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if error:
        if isinstance(error, dict):
            raise RuntimeError(str(error.get("message") or error))
        raise RuntimeError(str(error))
    choices = payload.get("choices") or [{}]
    delta = choices[0].get("delta") or {}
    return str(delta.get("content") or "")


async def curl_stream(
    history: list[BaseMessage],
    system_prompt: str,
) -> AsyncIterator[str]:
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": _history_to_openai(history, system_prompt),
        "stream": True,
        "temperature": 0.3,
        "thinking": {"type": "disabled"},
    }
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as handle:
        json.dump(body, handle, ensure_ascii=False)
        body_path = handle.name

    process = await asyncio.create_subprocess_exec(
        "curl",
        "-sS",
        "-N",
        "--fail-with-body",
        deepseek_openai_base_url().rstrip("/") + "/chat/completions",
        "-H",
        f"Authorization: Bearer {DEEPSEEK_API_KEY}",
        "-H",
        "Content-Type: application/json",
        "--max-time",
        "180",
        "-d",
        f"@{body_path}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert process.stdout is not None
    try:
        while raw := await process.stdout.readline():
            line = raw.decode("utf-8", errors="ignore").strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "[DONE]":
                if line == "[DONE]":
                    break
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = _delta_text(payload)
            if text:
                yield text
        await process.wait()
        if process.returncode not in (0, None):
            error = (
                await process.stderr.read()
                if process.stderr is not None
                else b""
            )
            message = error.decode("utf-8", errors="ignore")
            raise RuntimeError(message or f"curl 退出码 {process.returncode}")
    finally:
        Path(body_path).unlink(missing_ok=True)
