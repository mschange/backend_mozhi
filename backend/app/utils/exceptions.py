"""可预期的业务异常，由 handlers 转成 {code, message, data}。"""

from app.utils.enums import ErrorCode


class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
