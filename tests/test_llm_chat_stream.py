from main import app
from fastapi.testclient import TestClient
import routers.llm as rl
client = TestClient(app)


def _login():
    resp = client.post("/token", json={"username": "zihao", "password": "123456"})
    assert resp.status_code == 200
    return resp.json()["access_token"]
def test_llm_chat_first_connection(monkeypatch):
    token = _login()
    _setup(monkeypatch, _normal_gen)
    resp = client.get(
        "/llm/chat",
        headers={"Authorization": f"Bearer {token}"},
        params={"prompt":"hi", "stream_id":"alien"}

    )

    print(repr(resp.text))
    frames = resp.text.split("\n\n")
    assert frames[0] =='id: 1\ndata: 你好'
    print(len(frames))
    assert frames[1] =='id: 2\ndata: ，世界'
    assert frames[2] =="event: end\ndata: done"
    assert frames[3] == ""

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
