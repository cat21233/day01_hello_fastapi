import pytest


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

    monkeypatch.setattr(settings,"deepseek_api_key","test-key")
    monkeypatch.setattr(factory,"_cache",{})