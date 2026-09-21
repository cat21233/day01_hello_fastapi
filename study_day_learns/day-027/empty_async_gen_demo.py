"""day-027 实验：怎么造一个「不吐任何东西」的异步生成器？

问的不是"怎么写测试"，而是"怎么造出那个空流"。
把三种造法摆在一起，逐一看 anext() 的行为 + 有没有 aclose()。
"""
import asyncio


async def empty_gen_1():
    """造法 1：异步生成器函数，带一个永远不执行的 yield。

    ⚠️ yield 必须存在 —— 没有 yield 的 async def 是【协程函数】，
       调用它返回的是 coroutine object，根本不是异步生成器。
    """
    if False:
        yield ""
    return


class EmptyAsyncIter:
    """造法 2：手写对象，实现异步迭代协议（__aiter__ / __anext__）。"""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


async def one_chunk_gen():
    """对照组：吐一块就结束（正常流）。"""
    yield "你好"


async def probe(label, gen):
    print(f"--- {label} ---")
    print(f"  类型           = {type(gen).__name__}")
    print(f"  有 aclose() 吗 = {hasattr(gen, 'aclose')}")
    try:
        first = await anext(gen)
        print(f"  anext 结果     = {first!r}   <- 有内容")
    except StopAsyncIteration:
        print("  anext 结果     = 抛 StopAsyncIteration   <- 空流")
    print()


async def main():
    print("=== 三种造法 ===")
    await probe("造法1 异步生成器函数", empty_gen_1())
    await probe("造法2 协议对象", EmptyAsyncIter())
    await probe("对照 正常流(吐一块)", one_chunk_gen())

    print("=== 结论 ===")
    print("  · 三种都能提供「空流」，都不碰网络 ✓")
    print("  · 只有【真异步生成器】自带 aclose()")
    print("  · 用造法2 做测试时，必须自己补一个 async def aclose()，")
    print("    否则 _produce 的 finally 里 `await gen.aclose()` 会 AttributeError")


if __name__ == "__main__":
    asyncio.run(main())
