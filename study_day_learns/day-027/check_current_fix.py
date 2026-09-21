"""探针：空流场景下，_produce 到底往 chunks 里塞了什么？

只打印、不判断 —— 让事实说话。
修对了应该是 []，修错了是 ['上游异常']。
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))          # 必须在 import 根模块之前（坑 #11）

import routers.llm as rl               # noqa: E402


async def _empty_gen():
    """假的「空上游」：一个字都不吐。"""
    if False:
        yield ""


async def _normal_gen():
    """对照：正常吐两块的流。"""
    yield "你好"
    yield "，世界"


class _FakeClient:
    """把 stream() 换成指定的生成器，不连网络。"""

    def __init__(self, factory):
        self._factory = factory

    def stream(self, prompt):
        return self._factory()


async def _run(factory, label):
    rl.llm = _FakeClient(factory)

    async def _noop(*args, **kwargs):
        return None

    rl._expire = _noop                 # 关掉 120s 定时器，避免残留 pending task

    sid = f"probe-{label}"
    rl._STREAMS[sid] = rl._Stream()
    try:
        await rl._produce(sid, "hi")
        st = rl._STREAMS[sid]
        print(f"  {label:<6} chunks = {st.chunks!r}")
        return st.chunks
    finally:
        rl._STREAMS.pop(sid, None)


async def main():
    print("=== _produce 的产出对照 ===")
    empty = await _run(_empty_gen, "空流")
    normal = await _run(_normal_gen, "正常流")
    print()

    print("=== 断言检查（这就是测试文件里那一行要干的事）===")
    print(f"  assert chunks == []   ->  {empty == []}"
          f"   {'通过 ✓' if empty == [] else '失败 ✗'}（空流场景）")
    print()

    print("=== 前端实际会渲染出什么 ===")
    print(f"  空流时用户看到: {''.join(empty)!r}")
    print(f"  正常流用户看到: {''.join(normal)!r}")


asyncio.run(main())
