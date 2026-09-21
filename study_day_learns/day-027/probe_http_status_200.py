"""day-027 实验：用 HTTP 状态码 200 来断言，有判别力吗？

做法：不修代码，直接造「上游空流」，然后用 TestClient 请求 /llm/chat，
看返回的 status_code 和 body 长什么样。

如果 200 在【有 bug 的代码】上也能通过，那它就没有判别力 —— 测了等于没测。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))                 # 必须在 import 根模块之前（坑 #12）

from fastapi.testclient import TestClient  # noqa: E402

import routers.llm as rl  # noqa: E402
from main import app  # noqa: E402
from routers.limits import limiter  # noqa: E402

limiter.enabled = False


async def _empty_gen():
    """空流：一个字都不吐。"""
    if False:
        yield ""


class FakeClient:
    def stream(self, prompt):
        return _empty_gen()


def main():
    rl.llm = FakeClient()                     # 注入假客户端，不碰真网络

    client = TestClient(app)
    token = client.post(
        "/token", json={"username": "zihao", "password": "123456"}
    ).json()["access_token"]

    resp = client.get(
        "/llm/chat",
        params={"prompt": "你好", "stream_id": "probe-http-200"},
        headers={"Authorization": f"Bearer {token}"},
    )

    print("=== HTTP 层看到的结果 ===")
    print("status_code =", resp.status_code)
    print("body 原文   =", repr(resp.text))
    print()

    print("=== 判别性检验 ===")
    print(f"  断言 status_code == 200 能通过吗? -> {resp.status_code == 200}")
    print(f"  但 body 里有没有假报错?          -> {'有 ⚠️' if 'StopAsyncIteration' in resp.text else '无'}")
    print()
    if resp.status_code == 200 and "StopAsyncIteration" in resp.text:
        print(">>> 结论：代码还带着 bug，200 却照样通过 ——")
        print("    status_code 没有判别力，测了等于没测 ✗")


if __name__ == "__main__":
    main()
