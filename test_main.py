from main import app
from fastapi.testclient import TestClient
client = TestClient(app)
def test_read_root():
    resp = client.get('/')
    assert resp.status_code == 200
    assert resp.json() == {"message": "Hello World"}
def test_read_items():
    response = client.get("/items/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
def test_read_item_exists():
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json()["item_id"] == 1

def test_read_items_not_found():
    response = client.get('/items/999')
    assert response.status_code == 404

def test_create_items_valid():
    data = {"name": 'Foo', "price": 9.9}
    response = client.post("/items/", json=data)
    assert response.status_code in (200, 201)
    assert response.json()['name'] == 'Foo'

def test_create_items_invalid():
    data = {"price": 9.9}
    response = client.post('/items/', json=data)
    assert response.status_code == 422




