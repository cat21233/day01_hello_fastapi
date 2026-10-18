"""数据库层测试 —— 验证「接进真库」之后必须守住的几条契约。

注意这些测试全都跑在 conftest 提供的内存 SQLite 上，
所以既不需要本机 MySQL 开着，也不会碰你的真实数据。
"""

from sqlalchemy import func, select

from db import seed_default_users
from db_models import User


def test_seed_is_idempotent(db_session):
    """种子数据必须幂等：conftest 已经种过一次，再种一次应该新增 0 条。"""
    assert seed_default_users(db_session) == 0
    total = db_session.scalar(select(func.count()).select_from(User))
    assert total == 2


def test_password_is_hashed_not_plaintext(db_session):
    """库里存的必须是哈希：泄漏了库也不等于泄漏了密码。"""
    user = db_session.scalar(select(User).where(User.username == "zihao"))
    assert user.hashed_password != "123456"
    assert user.hashed_password.startswith("$2b$")  # bcrypt 的固定前缀
    assert user.role == "admin"


def test_inactive_user_cannot_login(client, db_session):
    """is_active=False 的账号一律拒绝（软禁用，不删数据）。"""
    user = db_session.scalar(select(User).where(User.username == "test"))
    user.is_active = False
    db_session.commit()

    resp = client.post("/token", json={"username": "test", "password": "123456"})
    assert resp.status_code == 401


def test_role_change_takes_effect_from_database(client, db_session):
    """角色改库即生效：证明登录时角色真的是从表里读的，不是内存里写死的。"""
    user = db_session.scalar(select(User).where(User.username == "test"))
    user.role = "admin"
    db_session.commit()

    resp = client.post("/token", json={"username": "test", "password": "123456"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
