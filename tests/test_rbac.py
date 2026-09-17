from main import app
from fastapi.testclient import TestClient
client = TestClient(app)
def get_token(username,password):
    resp = client.post('/token', json={"username": username, 'password': password})
    return resp.json()['access_token']
def test_admin_can_delete_item():
    token = get_token('zihao', '123456')
    resp = client.delete("/items/1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
def test_user_cannot_delete_item():
    token = get_token('test', '123456')
    resp = client.delete("/items/2", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert "需要管理员权限" in resp.json()["detail"]
def test_unauthenticated_cannot_delete_item():
    resp = client.delete("/items/3")
    assert resp.status_code == 401
