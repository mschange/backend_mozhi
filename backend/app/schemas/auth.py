"""鉴权相关入参/出参。

RegisterIn / LoginIn / RefreshIn 是请求体；
UserOut / TokenBundle 是成功响应里的 data。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    """能从 SQLAlchemy ORM 实例直接 model_validate 的基类。"""

    model_config = ConfigDict(from_attributes=True)


class UserOut(ORMModel):
    """对外暴露的用户信息，不含密码哈希。"""

    id: str = Field(description="用户 UUID")
    username: str = Field(description="用户名")
    email: EmailStr = Field(description="邮箱")
    created_at: datetime | None = Field(default=None, description="注册时间")


class RegisterIn(BaseModel):
    """注册请求。用户名、邮箱都不能与已有账号重复。"""

    username: str = Field(min_length=2, max_length=64, description="用户名，2–64 个字符，全局唯一")
    email: EmailStr = Field(description="邮箱，全局唯一")
    password: str = Field(min_length=6, max_length=72, description="明文密码，服务端 bcrypt 后入库，最长 72（bcrypt 限制）")


class LoginIn(BaseModel):
    """登录请求。username 字段同时接受用户名或邮箱。"""

    username: str = Field(min_length=1, description="用户名或邮箱")
    password: str = Field(min_length=1, description="明文密码")


class RefreshIn(BaseModel):
    """用 refresh_token 换新的 access_token。"""

    refresh_token: str = Field(min_length=10, description="登录时下发的刷新令牌")


class TokenBundle(BaseModel):
    """注册/登录成功后的令牌包。"""

    access_token: str = Field(description="访问令牌，默认 30 分钟，放 Authorization: Bearer")
    refresh_token: str = Field(description="刷新令牌，默认 7 天")
    token_type: str = Field(default="bearer", description="令牌类型，固定 bearer")
    user: UserOut = Field(description="当前用户信息")
