"""
tests/test_infra.py —— t-235 / t-236 / t-237 / t-238 的接口与配置测试

`/health` 那条用 `with TestClient(app) as c:` —— 只有带 `with`，lifespan 才会跑
（启动协程只在 starlette/testclient.py 的 `TestClient.__enter__` 里被 start），
所以那条顺带覆盖了启动校验；其余测试用裸 `TestClient(app)`，省掉重复启动开销。

测试覆盖：
  · /health 返回新增的指标字段（t-238）
  · /prompts 列表 / /prompts/{name} / /prompts/preview（t-235）
  · validate_settings() 在当前 .env 下不应抛错（t-236，未实现前会是红测试）
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from config import validate_settings


# ============ t-238：健康检查指标 ============
def test_health_returns_metrics():
    with TestClient(app) as c:
        resp = c.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "uptime_seconds" in body
    assert "llm_provider" in body
    assert "version" in body


# ============ t-235：Prompt 管理路由 ============
def test_prompts_list():
    client = TestClient(app)
    resp = client.get("/prompts")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "default" in names
    # 列表页只给前 50 字预览，不该返回完整长文本
    assert len(resp.json()[0]["preview"]) <= 50


def test_prompts_get_one():
    client = TestClient(app)
    resp = client.get("/prompts/concise")
    assert resp.status_code == 200
    assert "简洁" in resp.json()["text"]


def test_prompts_preview_messages():
    client = TestClient(app)
    resp = client.post(
        "/prompts/preview",
        json={"name": "code_reviewer", "user_message": "帮我看这段代码"},
    )
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "帮我看这段代码"


# ============ t-236：启动配置校验（闭卷题驱动的红测试） ============
# 当前 .env 里 deepseek 配了 key，llm_provider=deepseek，
# 所以 validate_settings() 实现正确后应「什么都不抛」。
# 未实现时它 raise NotImplementedError → 这条测试红，等你补全逻辑后转绿。
def test_validate_settings_ok():
    # 当前 .env 下不应抛任何异常
    validate_settings()
