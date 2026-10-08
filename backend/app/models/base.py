"""SQLAlchemy 声明式模型基类。

这里只定义唯一 Base，不在此处导入业务模型；具体表由 app.models 聚合注册。
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """六张业务表共享的声明式基类和 metadata 容器。"""

    pass
