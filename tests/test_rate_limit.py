from main import app
from fastapi.testclient import TestClient
from routers.limits import limiter
client = TestClient(app)

def test_items_limited_to_5_per_minute():
    limiter.enabled = True
    limiter.reset()
    try:
        for i in range(5):
            resp = client.get('/items/')
            assert resp.status_code == 200
        resp = client.get('/items/')
        assert resp.status_code == 429
    finally:
        limiter.enabled = False

def test_token_limited_to_3_per_minute():
    limiter.enabled = True
    limiter.reset()
    try:
        for i in range(3):
            resp = client.post('/token', json={"username":'zihao', "password":"123456" })
            assert resp.status_code == 200
        resp = client.post('/token', json={"username": 'zihao', "password": "123456"})
        assert resp.status_code == 429
    finally:
        limiter.enabled = False
