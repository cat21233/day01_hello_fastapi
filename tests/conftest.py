"""测试夹具（fixtures）—— 所有测试共用的「准备 + 收尾」动作。

核心思想：
    fixtures 用「依赖注入」代替「每个测试自己写 setup/teardown」。
    测试函数只要把夹具名写进参数表，pytest 就自动帮你准备好再清理。

本文件干两件大事：
    1. 把数据库从「.env 里配的 MySQL」换成「内存 SQLite」
       —— 测试永远不碰真实库，跑一万次也不会污染你的数据
    2. 关掉限流、塞一个假的 LLM key，免得老测试互相撞 429 / 401
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db_models  # noqa: F401  必须先 import，User 才会注册进 Base.metadata

from db import Base, get_db, seed_default_users
from main import app


@pytest.fixture
def sqlite_engine():
    """每个测试一套全新的内存库：测试之间绝对隔离。"""
    engine = create_engine(
        "sqlite://",  # 不写文件名 = 内存库，进程退出即消失
        connect_args={"check_same_thread": False},
        # 内存库的关键：默认池会给每次连接开一个新的空库，
        # StaticPool 强制所有 session 复用「同一条」连接，表才在。
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def override_db(sqlite_engine):
    """autouse=True：每个测试自动生效，不用手动声明。

    原理：FastAPI 的 app.dependency_overrides 是个字典，
    把「依赖函数」映射到「替代函数」。路由里写的是 Depends(get_db)，
    请求进来时 FastAPI 先查这张表，查到了就用替代品 —— 路由代码一个字不用改。
    """
    TestingSession = sessionmaker(
        bind=sqlite_engine, autoflush=False, expire_on_commit=False
    )
    # 建表后先塞默认账号，登录相关测试才有数据可查
    with TestingSession() as session:
        seed_default_users(session)

    def _get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(sqlite_engine):
    """给需要直接操作数据库的测试用（断言表里的数据，而不是只看 HTTP 响应）。"""
    TestingSession = sessionmaker(
        bind=sqlite_engine, autoflush=False, expire_on_commit=False
    )
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """所有测试默认禁用限流，避免老测试互相撞 429；
    只有 test_rate_limit.py 显式启用限流测试。"""
    from routers.limits import limiter
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(autouse=True)
def stub_llm_config(monkeypatch):
    from config import settings
    import llm_service.factory as factory

    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(factory, "_cache", {})
