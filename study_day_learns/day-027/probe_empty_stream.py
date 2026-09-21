"""day-027 探针：上游返回「空流」时，_produce 会怎么表现？

背景：_produce 里有
    first = await anext(gen)
空流时 anext 会抛 StopAsyncIteration —— 而它是 Exception 的子类，
所以会掉进 `except Exception as exc` 分支。

两个怀疑：
  ① 假报错：空流被当成「上游异常」上报给前端
  ② 泄漏：gen.aclose() 写在「首块之后的 try/finally」里，
          首块就抛异常 → 永远走不到 → 上游连接没关

本探针不连网络：用假客户端 + 假生成器对象（可追踪 aclose 是否被调用）。
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import routers.llm as rl  # noqa: E402


class FakeGen:
    """模拟上游的异步生成器对象。

    mode="empty"  → 第一次 anext 就抛 StopAsyncIteration（上游一个字没吐）
    mode="normal" → 吐一块 "你好"，再结束
    """

    def __init__(self, mode: str):
        self.mode = mode
        self.aclose_called = False
        self._n = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if self.mode == "empty":
            raise StopAsyncIteration
        self._n += 1
        if self._n == 1:
            return "你好"
        raise StopAsyncIteration

    async def aclose(self):
        self.aclose_called = True


class FakeClient:
    def __init__(self, mode: str):
        self.gen = FakeGen(mode)

    def stream(self, prompt):
        return self.gen


async def run_case(mode: str):
    fake = FakeClient(mode)
    rl.llm = fake
    sid = f"probe-{mode}"
    rl._STREAMS[sid] = rl._Stream()

    await rl._produce(sid, "hello")
    st = rl._STREAMS[sid]

    print(f"--- 场景 {mode} ---")
    print(f"  chunks        = {st.chunks}")
    print(f"  aclose 被调用 = {fake.gen.aclose_called}")
    print()
    return st, fake.gen


async def main():
    print("前置事实：StopAsyncIteration 是 Exception 的子类吗? ->",
          issubclass(StopAsyncIteration, Exception), "\n")

    st_empty, gen_empty = await run_case("empty")
    st_ok, gen_ok = await run_case("normal")

    print("=== 判别性对照 ===")
    print(f"  空流   : 假报错={'是 ✗' if st_empty.chunks and 'StopAsyncIteration' in st_empty.chunks[0] else '否 ✓'}"
          f" | aclose={'有 ✓' if gen_empty.aclose_called else '未调用'}")
    print(f"  正常流 : 内容={st_ok.chunks}"
          f" | aclose={'有 ✓' if gen_ok.aclose_called else '未调用'}")
    print()
    print("注：空流时 aclose 未调用【不等于泄漏】—— 生成器已耗尽，内部 finally 早已执行，")
    print("    aclose 此时是 no-op（已单独实测确认）。真正的 bug 只有『假报错』一个。")


if __name__ == "__main__":
    asyncio.run(main())
