from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_read_token():
    data = {'username': 'zihao', 'password': '123456'}
    resp = client.post('/token', json=data)
    assert resp.status_code == 200
    assert resp.json()['access_token'].startswith("eyJ")

def test_read_wrong_token():
    data = {"username": 'zihao', 'password': "wrong"}
    resp = client.post("/token", json=data)
    assert resp.status_code == 401

def test_read_me():
    resp_login = client.post('/token', json={"username": "zihao", "password": "123456"})
    token = resp_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get('/me', headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == 'zihao'
def test_me_without_token():
    resp = client.get('/me')
    assert resp.status_code == 401
