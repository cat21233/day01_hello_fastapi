"""任务③验证：断线重连不重跑模型。

三步：
  1. 带 stream_id 连上，收 5 帧就断开       —— 模拟网络断掉
  2. 干等 3 秒                              —— 这 3 秒服务端后台任务仍在继续生成
  3. 同一个 stream_id + Last-Event-ID 重连

判据（关键看第 3 步的「首帧延迟」）：
  · 走缓存补发 → 首帧几乎立刻到（<0.3s），拿得到第 1 步断开之后新生成的内容
  · 若退化回「重新调模型」→ 首帧要等 1~2s 的 TTFT，而且内容会从头重放
"""
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8010"
PROMPT = "请写一篇1500字的作文，题目我的家乡，要求分段落，内容详细"


def login() -> str:
    r = httpx.post(
        f"{BASE}/token",
        json={"username": "zihao", "password": "123456"},
        timeout=10.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def read(url: str, headers: dict, params: dict, limit: int = 0):
    """收 limit 帧后主动断开（limit=0 表示收到结束为止）。

    返回 (frames, first_delay, total_time)：frames 是 [(id, text), ...]
    """
    frames: list[tuple[int, str]] = []
    first_delay = None
    last_id = None
    t0 = time.perf_counter()
    with httpx.stream("GET", url, headers=headers, params=params, timeout=60.0) as resp:
        if resp.status_code != 200:
            print(f"  !! HTTP {resp.status_code}: {resp.read().decode()[:200]}")
            return frames, first_delay, 0.0
        for line in resp.iter_lines():
            if line.startswith("event: end"):
                print(f"  [{time.perf_counter() - t0:6.2f}s] ← event: end")
                break
            if line.startswith("id: "):
                last_id = int(line[4:])
            elif line.startswith("data: "):
                if first_delay is None:
                    first_delay = time.perf_counter() - t0
                frames.append((last_id, line[6:]))
                if len(frames) <= 3 or len(frames) % 20 == 0:
                    print(f"  [{time.perf_counter() - t0:6.2f}s] id={last_id}  {line[6:]}")
                if limit and len(frames) >= limit:
                    print("  （主动断开连接）")
                    break
    return frames, first_delay, time.perf_counter() - t0


def main():
    token = login()
    sid = uuid.uuid4().hex[:8]
    url = f"{BASE}/llm/chat"
    params = {"prompt": PROMPT, "stream_id": sid}
    auth = {"Authorization": f"Bearer {token}"}
    print(f"stream_id = {sid}\n")

    print("== 第1次连接：收 5 帧后断开 ==")
    a, _, _ = read(url, auth, params, limit=5)
    if not a:
        print("第1次就没拿到数据，后面的测试没意义，先排查上游")
        return
    cut_id = a[-1][0]
    print(f"  最后收到的 id = {cut_id}")

    print("\n== 干等 3 秒：服务端后台任务继续生成 ==")
    time.sleep(3)

    print("\n== 第2次连接：同一个 stream_id + Last-Event-ID 续传 ==")
    b, first_delay, _ = read(url, {**auth, "Last-Event-ID": str(cut_id)}, params)

    print("\n== 结果 ==")
    seen: set[int] = set()
    dropped = 0
    final: list[int] = []
    for i, _ in a + b:
        if i in seen:
            dropped += 1
            continue
        seen.add(i)
        final.append(i)
    final.sort()
    print(f"  第1段 {len(a)} 块，第2段 {len(b)} 块；客户端按 id 去重丢弃 {dropped} 块")
    print(f"  最终编号 {final[0]}..{final[-1]}，共 {len(final)} 块", end="  ")
    print("连续无缺失 ✅" if final == list(range(final[0], final[-1] + 1)) else "有缺口 ❌")
    print(f"  重连后首帧延迟 {first_delay:.2f}s（走缓存应 <0.3s；重跑模型会是 1s+ 的 TTFT）")


if __name__ == "__main__":
    main()
