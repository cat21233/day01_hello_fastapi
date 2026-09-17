"""断点续传演示客户端：连上 → 收几块 → 主动断开 → 带 Last-Event-ID 重连。

看点：
  · 场景1（无状态）重连后每块仍要等 0.4s —— 因为服务端在「重新生成」
  · 场景2（有缓存）回退重连时，补发的块是「唰」一下全到的 —— 证明它在读缓存
"""
import time

import httpx

BASE = "http://127.0.0.1:8020"


def read_n(url: str, n: int, headers: dict | None = None) -> list[tuple[int, str]]:
    """连上流，收 n 个 data 帧后主动断开。返回 [(id, data), ...]"""
    got: list[tuple[int, str]] = []
    last_id = 0
    t0 = time.perf_counter()
    with httpx.stream("GET", url, headers=headers or {}, timeout=30.0) as resp:
        for line in resp.iter_lines():
            if line.startswith("event: end"):
                print(f"  [{time.perf_counter() - t0:5.2f}s] ← event: end")
                break
            if line.startswith("id: "):
                last_id = int(line[4:])
            elif line.startswith("data: "):
                got.append((last_id, line[6:]))
                print(f"  [{time.perf_counter() - t0:5.2f}s] id={last_id}  {line[6:]}")
                if len(got) >= n:
                    print("  （客户端主动断开）")
                    break
    return got


def check(segments: list[list[tuple[int, str]]]) -> None:
    """把多段收到的帧拼起来。

    注意：服务端「按 Last-Event-ID 补发」是可能重发的 —— 客户端回退到更早的
    断点重连时，服务端只能老实把该点之后的都再发一遍（它不知道你手里有什么）。
    所以去重是客户端不可推卸的责任，判据就是 id 单调递增：id <= 已见过的最大 id
    一律丢弃。不去重 → 界面上会看到重复文字。
    """
    seen: set[int] = set()
    ordered: list[int] = []
    dropped = 0
    for seg in segments:
        for i, _ in seg:
            if i in seen:
                dropped += 1
                continue
            seen.add(i)
            ordered.append(i)
    ordered.sort()
    expect = list(range(1, len(ordered) + 1))
    flag = "连续且不重复" if ordered == expect else "异常"
    print(f"  → 客户端按 id 去重：丢弃 {dropped} 块重复；最终编号 {ordered}  {flag}")


def main():
    sid = str(int(time.time()))       # 每个会话独立缓存，避免上次的残留干扰

    print("===== 场景1：无状态（重新生成 + 跳过）=====")
    a = read_n(f"{BASE}/stateless", 3)
    print(f"  → 断线，最后收到 id={a[-1][0]}，带着它重连：")
    b = read_n(f"{BASE}/stateless", 99, {"Last-Event-ID": str(a[-1][0])})
    check([a, b])

    print("\n===== 场景2：有缓存（断点切片补发）=====")
    url = f"{BASE}/buffered?sid={sid}"
    c = read_n(url, 3)
    print(f"  → 断线，最后收到 id={c[-1][0]}，带着它重连：")
    d = read_n(url, 99, {"Last-Event-ID": str(c[-1][0])})
    check([c, d])

    print(f"\n  → 再断一次，这次故意回退到 Last-Event-ID=5 重连（看补发有多快）：")
    e = read_n(url, 99, {"Last-Event-ID": "5"})
    check([c, d, e])


if __name__ == "__main__":
    main()
