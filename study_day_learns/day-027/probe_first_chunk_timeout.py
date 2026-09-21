"""探针：首块超时（上游一直挂着不吐字也不结束）时，上游生成器被关闭了吗？

这决定了「超时」这条路是不是也藏着一个 bug。
"""
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import routers.llm as rl  # noqa: E402

CLOSED = []


async def _hang_gen():
    """首块永远不来：既不吐字，也不结束。"""
    try:
        await asyncio.sleep(600)
        yield "never"
    finally:
        CLOSED.append("上游生成器的 finally 执行了")


class _FakeClient:
    def __init__(self, factory):
        self._factory = factory

    def stream(self, prompt):
        return self._factory()


async def main():
    rl.llm = _FakeClient(_hang_gen)

    async def _noop(*args, **kwargs):
        return None

    rl._expire = _noop

    sid = "probe-timeout"
    rl._STREAMS[sid] = rl._Stream()
    try:
        t0 = time.time()
        await rl._produce(sid, "hi")
        dt = time.time() - t0

        st = rl._STREAMS[sid]
        print(f"耗时    : {dt:.1f}s  (asyncio.timeout 设的是 10s)")
        print(f"chunks  : {st.chunks!r}")
        print(f"done    : {st.done}")
        print()
        if CLOSED:
            print(f"上游生成器的 finally : {CLOSED}  -> 已关闭 ✓")
        else:
            print("上游生成器的 finally : 没有执行  -> 生成器还挂着 ✗")
    finally:
        rl._STREAMS.pop(sid, None)


asyncio.run(main())
