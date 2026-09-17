"""坑 A 实证：async generator 能不能 await？

三个要观察的现象：
  ① 「调用」一个 async generator function，函数体一行都不执行 → 说明它是惰性的
  ② await 它 → 直接 TypeError（不是「拿到生成器对象」）
  ③ 正确驱动方式：async for
"""
import asyncio


async def ticker():  # 有 yield → 这是 async generator function，不是协程函数
    print("  [ticker] 函数体开始执行了")
    for i in range(1, 4):
        yield f"chunk-{i}"


async def main():
    print("① 只是「调用」ticker()：")
    gen = ticker()
    print("   type(gen) =", type(gen).__name__)
    print("   ↑ 上面没打印『函数体开始执行』，说明调用 ≠ 执行")

    print("\n② 试着 await 它：")
    try:
        await gen
    except TypeError as e:
        print("   TypeError:", e)

    print("\n③ 正确姿势 async for：")
    async for chunk in ticker():
        print("   got:", chunk)

    print("\n④ 对照：真正的协程函数长什么样")

    async def coro_fn():
        return 1

    print("   type(ticker())   =", type(ticker()).__name__)

    c = coro_fn()
    print("   type(coro_fn())  =", type(c).__name__)
    c.close()  # 协程建了不 await 会报 never awaited 警告，这里手动关掉保持输出干净


asyncio.run(main())
