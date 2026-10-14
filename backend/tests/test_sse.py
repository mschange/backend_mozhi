# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
import json

import pytest

from app.utils.http.sse import SSE_HEADERS, encode_sse, encode_sse_events


def test_encode_sse_preserves_unicode_and_delimiter() -> None:
    encoded = encode_sse({"type": "delta", "content": "你好"})

    assert encoded.startswith("data: ")
    assert encoded.endswith("\n\n")
    assert json.loads(encoded.removeprefix("data: ").strip()) == {
        "type": "delta",
        "content": "你好",
    }


@pytest.mark.asyncio
async def test_encode_sse_events_preserves_event_order() -> None:
    async def events():
        yield {"type": "delta", "content": "你"}
        yield {"type": "done", "message": {"content": "你好"}}

    encoded = [item async for item in encode_sse_events(events())]
    payloads = [json.loads(item.removeprefix("data: ").strip()) for item in encoded]

    assert payloads == [
        {"type": "delta", "content": "你"},
        {"type": "done", "message": {"content": "你好"}},
    ]


def test_sse_headers_disable_buffering() -> None:
    assert SSE_HEADERS["Cache-Control"] == "no-cache"
    assert SSE_HEADERS["X-Accel-Buffering"] == "no"
