"""任务②真实链路验证：打真实 uvicorn，不用 TestClient。

为什么不许用 TestClient：
    TestClient 会把整个响应收完再交给你，`for line in response.iter_lines()`
    看着一样，其实帧早就全到了 —— 流式坏掉也照样“看起来正常”。
    httpx.stream + iter_lines 才是边收边打印，时间戳能证明逐帧到达。

前置：另开一个终端 `python -m uvicorn main:app --port 8010`
"""
import time

import httpx

BASE = "http://127.0.0.1:8010"


def main():
    r = httpx.post(
        f"{BASE}/token",
        json={"username": "zihao", "password": "123456"},
        timeout=10.0,
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    print(f"login ok, token 长度 = {len(token)}\n")

    t0 = time.perf_counter()
    with httpx.stream(
        "GET",
        f"{BASE}/llm/chat",
        params={"prompt": "用三句话介绍 FastAPI"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    ) as resp:
        print(f"status={resp.status_code}  content-type={resp.headers.get('content-type')}")
        for line in resp.iter_lines():
            if line.strip():
                print(f"[{time.perf_counter() - t0:6.2f}s] {line}")


if __name__ == "__main__":
    main()
