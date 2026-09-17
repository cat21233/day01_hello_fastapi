# p0_e2e_smoke.py
# 用途：一键验证 ②→③→④→⑤ 流式链路
#   1. POST /token 拿 JWT
#   2. GET /llm/chat 带 token 流式输出
# 用法：.\.venv\Scripts\python.exe study_day_learns/p0_e2e_smoke.py
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000"


def get_token() -> str:
    body = json.dumps({"username": "zihao", "password": "123456"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/token",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    token = data.get("access_token", "")
    print(f"[1/2] 拿到 token，长度 {len(token)}（不打印内容）")
    return token


def stream_chat(token: str, prompt: str) -> None:
    req = urllib.request.Request(
        f"{BASE}/llm/chat?prompt={urllib.parse.quote(prompt)}",
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"[2/2] 流式输出 prompt='{prompt}':")
    print("--- BEGIN STREAM ---")
    with urllib.request.urlopen(req, timeout=30) as r:
        for line in r:
            sys.stdout.write(line.decode("utf-8", errors="replace"))
            sys.stdout.flush()
    print("\n--- END STREAM ---")


if __name__ == "__main__":
    token = get_token()
    stream_chat(token, "你好")
