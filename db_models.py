"""ORM 模型：一张表 = 一个类，一个字段 = 一个属性。

命名注意：本文件叫 db_models，routers/users.py 里的 User 是 Pydantic 模型。
两者同名不同物：
    ORM 模型（这里）  —— 描述「数据库里的行」，生命周期跟着 Session 走
    Pydantic 模型     —— 描述「HTTP 请求/响应里的 JSON」，生命周期只到一次序列化
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class User(Base):
    __tablename__ = "users"

    # ① 主键：MySQL 上 autoincrement 对应 AUTO_INCREMENT
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ② 用户名：唯一 + 索引。登录时按它查，没索引 = 全表扫描
    #    长度 50 是给索引留的余量：utf8mb4 下 50*4=200 字节，
    #    远小于 InnoDB 单列索引上限 3072 字节，不会建表失败
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    # ③ 存哈希，永不存明文。bcrypt 结果固定 60 字符，255 足够
    hashed_password: Mapped[str] = mapped_column(String(255))

    # ④ 角色：RBAC 鉴权就靠它（admin / user）
    role: Mapped[str] = mapped_column(String(20), default="user")

    # ⑤ 软禁用：停用账号不删记录，登录时判一下就 401
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ⑥ 创建时间：server_default 让「数据库」填，不用 Python 算
    #    （多实例部署时各机器时钟不一致，交给 DB 才统一）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # MySQL 专用建表参数：
    #   本机 phpstudy 的 my.ini 写着 default-storage-engine=MyIsam，
    #   而 MyISAM 不支持事务 —— 不显式指定 InnoDB，commit/rollback 会变成摆设。
    #   非 MySQL 方言（SQLite）会自动忽略这两个参数。
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

    def __repr__(self) -> str:  # 调试时打印对象不显示内存地址
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"
