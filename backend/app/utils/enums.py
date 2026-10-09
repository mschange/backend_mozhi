"""业务错误码。HTTP 状态多数仍是 200，真正对错看 code 字段。"""

from enum import IntEnum


class ErrorCode(IntEnum):
    SUCCESS = 0

    VALIDATION_ERROR = 40001
    DUPLICATE_USER = 40002
    INVALID_CREDENTIALS = 40003
    EMPTY_MESSAGE = 40004
    UNSUPPORTED_FILE = 40005
    FILE_TOO_LARGE = 40006

    UNAUTHORIZED = 40100
    TOKEN_EXPIRED = 40101
    INVALID_TOKEN = 40102

    FORBIDDEN = 40300

    NOT_FOUND = 40400

    INTERNAL = 50000
    LLM_ERROR = 50001
    DATABASE_ERROR = 50002
    VECTOR_ERROR = 50003


class DocumentStatus:
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"


class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"
