"""统一成功/失败 JSON。data 经 jsonable_encoder，可直接塞 ORM/Pydantic。"""

from typing import Any

from fastapi.encoders import jsonable_encoder

from app.utils.enums import ErrorCode


def success(data: Any = None, message: str = "成功") -> dict[str, Any]:
    return {
        "code": int(ErrorCode.SUCCESS),
        "message": message,
        "data": jsonable_encoder(data),
    }


def fail(
    code: ErrorCode | int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    return {
        "code": int(code),
        "message": message,
        "data": jsonable_encoder(data),
    }


def success_response(*, message: str = "成功", data: Any = None) -> dict[str, Any]:
    return success(data, message)
