from main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _login():
    resp = client.post("/token", json={"username": "zihao", "password": "123456"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_protected_stream_no_token():
    resp = client.get("/stream/protected")
    assert resp.status_code == 401


def test_protected_stream_with_token():
    token = _login()
    resp = client.get(
        "/stream/protected",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "受保护的第1条" in resp.text
    assert "event: end" in resp.text


def test_llm_chat_no_token():
    resp = client.get("/llm/chat", params={"prompt": "你好"})
    assert resp.status_code == 401
