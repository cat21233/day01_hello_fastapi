"""诊断：agnes 网关到底是「真流式」还是「伪流式」。

现象：走我们自己的 /llm/chat，首帧 4.22s，剩下 60 个 chunk 30ms 内全到齐。
两种可能：
  A. 上游网关自己攒完再吐（伪流式）→ 我们链路没问题，锅在厂商
  B. 我们中间有东西在缓冲（中间件 / uvicorn / httpx）→ 得当 bug 修

这里绕开 FastAPI，直接拿 SDK 打上游，看 chunk 的到达间隔。
如果这里也是「一大坨同时到」，那就是 A。
"""
import asyncio
import sys
import time
from pathlib import Path

# 坑 #12：sys.path.insert 必须在 from llm_service import ... 之前！
# 模块 import 是按行顺序执行的：写后面 = import 那一刻根目录还没进搜索路径。
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from llm_service import LLMClient  # noqa: E402


async def main():
    provider = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
    print(f"provider = {provider}\n")
    llm = LLMClient(provider)
    t0 = time.perf_counter()
    last = t0
    n = 0
    stamps: list[float] = []
    async for delta in llm.stream("用三句话介绍 FastAPI"):
        now = time.perf_counter()
        stamps.append(now)
        gap = now - last
        last = now
        n += 1
        if n <= 5 or gap > 0.05:          # 只打印前 5 块 + 任何间隔 >50ms 的块
            print(f"#{n:<3} t={now - t0:6.2f}s  gap={gap:6.3f}s  {delta!r}")

    total_ms = (stamps[-1] - stamps[0]) * 1000
    print(f"\n共 {n} 块，总耗时 {time.perf_counter() - t0:.2f}s")

    # 量化判据：把所有到达时刻按 10ms 分桶，数「有内容的桶」有多少个。
    # 真流式 → 块分散在很多个桶里；伪流式（上游攒完一次吐）→ 全挤在 1~2 个桶。
    buckets = {int(t * 100) for t in stamps}   # 10ms 一个桶
    print(f"首块→末块跨度 {total_ms:.0f}ms，落在 {len(buckets)} 个 10ms 桶里")
    if len(buckets) <= 2:
        print("判定：伪流式（上游攒完再吐），token 级体验为 0")
    else:
        print(f"判定：真流式，平均块间隔 {total_ms / max(n - 1, 1):.1f}ms")


asyncio.run(main())
