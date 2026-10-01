from main import app
from fastapi.testclient import TestClient
client = TestClient(app)

def test_greet_stream_frames():
    resp = client.get("/stream/greet", params={"name": "梓皓"})
    assert resp.status_code == 200
    print(repr(resp.text))
    frames = resp.text.split("\n\n")
    print(frames)
    print(len(frames))
    assert len(frames) == 10
    assert frames[8] == "event: end\ndata: done"
    assert frames[9] == ""