from main import app
from fastapi.testclient import TestClient
import routers.llm as rl
client = TestClient(app)
def _login():
    resp = client.post("/token", json={"username": "zihao", "password": "123456"})
    assert resp.status_code == 200
    return resp.json()["access_token"]
async def _normal_gen():
    """正常流：吐两块。"""
    yield "你好"
    yield "，世界"
class _FakeClient():
    def __init__(self,factory):
        self._factory = factory
    def stream(self,prompt):
        return self._factory()

def _setup(monkeypatch, factory):
    """摆现场：换掉真客户端 + 关掉 120s 定时器。"""
    monkeypatch.setattr(rl, "llm", _FakeClient(factory))

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(rl, "_expire", _noop)
def test_llm_chat_resume(monkeypatch):
    token = _login()
    _setup(monkeypatch, _normal_gen)
    headers = {"Authorization": f"Bearer {token}"}
    params = {"prompt": "hi", "stream_id": "resume-1"}
    resp1 = client.get("/llm/chat",headers=headers,params=params)
    print(repr(resp1.text))
    resp = client.get(
        "/llm/chat",
        headers={"Authorization": f"Bearer {token}", "Last-Event-ID": "1"},
        params=params,
    )

    resp3 = client.get(
        "/llm/chat",
        headers={"Authorization": f"Bearer {token}", "Last-Event-ID": "99"},
        params=params,
    )
    frame3 = resp3.text.split("\n\n")
    print(repr(resp3.text))
    print(frame3)
    assert frame3[0] == "event: end\ndata: done"
    assert len(frame3) == 2
    assert frame3[-1] == ""
    print(repr(resp.text))
    frames = resp.text.split('\n\n')
    print(frames)
    print(len(frames))
    assert "id: 1" not in resp.text
    assert frames[0] == "id: 2\ndata: ，世界"
    assert len(frames) == 3
    assert frames[1] == "event: end\ndata: done"
    assert frames[2] == ""