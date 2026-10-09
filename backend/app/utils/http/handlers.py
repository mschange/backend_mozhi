"""全局异常处理：AppError、校验、HTTP、SQL 都收成同一信封。DEBUG_MODE 时附带 traceback。"""

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import DEBUG_MODE
from app.utils.enums import ErrorCode
from app.utils.exceptions import AppError
from app.utils.http.response import fail

logger = logging.getLogger(__name__)


def _json(payload: dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=payload, status_code=status_code)


def _debug_data(request: Request, exc: Exception, extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not DEBUG_MODE:
        return None
    data = {
        "error_type": type(exc).__name__,
        "error_detail": str(exc),
        "traceback": traceback.format_exc(),
        "path": str(request.url),
    }
    if extra:
        data.update(extra)
    return data


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return _json(fail(exc.code, exc.message))


async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    messages = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        messages.append(f"{loc}: {err.get('msg', '校验失败')}" if loc else err.get("msg", "校验失败"))
    detail = "；".join(messages) if messages else "请求参数不合法"
    return _json(fail(ErrorCode.VALIDATION_ERROR, f"请求参数不合法：{detail}"))


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) and exc.detail else "请求失败"
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = ErrorCode.UNAUTHORIZED
        message = message or "未授权，请先登录"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = ErrorCode.FORBIDDEN
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        code = ErrorCode.NOT_FOUND
    elif exc.status_code == status.HTTP_400_BAD_REQUEST:
        code = ErrorCode.VALIDATION_ERROR
        if "已注册" in message or "已存在" in message:
            code = ErrorCode.DUPLICATE_USER
    else:
        code = ErrorCode.INTERNAL
    return _json(fail(code, message), status_code=exc.status_code)


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    error_msg = str(getattr(exc, "orig", exc))
    if "username" in error_msg.lower() or "Duplicate entry" in error_msg:
        detail = "用户名已存在"
        code = ErrorCode.DUPLICATE_USER
    elif "email" in error_msg.lower():
        detail = "邮箱已存在"
        code = ErrorCode.DUPLICATE_USER
    elif "FOREIGN KEY" in error_msg:
        detail = "关联数据不存在"
        code = ErrorCode.VALIDATION_ERROR
    else:
        detail = "数据约束冲突，请检查输入"
        code = ErrorCode.VALIDATION_ERROR
    logger.warning("数据库完整性错误: %s", error_msg)
    return _json(fail(code, detail, _debug_data(request, exc, {"error_detail": error_msg})))


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("数据库操作失败: %s", exc)
    return _json(
        fail(ErrorCode.DATABASE_ERROR, "数据库操作失败，请稍后重试", _debug_data(request, exc)),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未捕获异常: %s", exc)
    return _json(
        fail(ErrorCode.INTERNAL, "服务器内部错误", _debug_data(request, exc)),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """顺序有意义：更具体的异常要先于 Exception。"""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)
