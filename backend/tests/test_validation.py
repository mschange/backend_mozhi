# 本测试使用替身隔离外部基础设施，重点验证契约、顺序与失败恢复。
import pytest
from pydantic import ValidationError

from app.schemas.auth import RegisterIn
from app.schemas.conversation import ChatRenameIn, ChatSendIn


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (RegisterIn, {"username": "a", "email": "invalid", "password": "123"}),
        (ChatRenameIn, {"chat_id": "id", "title": ""}),
        (ChatSendIn, {"chat_id": "id", "content": ""}),
    ],
)
def test_invalid_payloads_are_rejected(model, payload) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)
