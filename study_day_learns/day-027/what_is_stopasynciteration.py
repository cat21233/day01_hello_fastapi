"""StopAsyncIteration 到底是什么？—— 一次解剖。

结论预告：它不是「假异常」，它是「说完了」这个信号本身。
"""
import asyncio


async def _empty_gen():
    if False:
        yield ""


async def _main():
    print("=== ① 它的真身：类型继承链 ===")
    for cls in StopAsyncIteration.__mro__:
        print("     ", cls.__name__)
    print()
    print("     它确实是 Exception 的子孙 —— 这就是它会掉进 except Exception 的原因。")
    print("     这是 Python 的类型层级决定的，不是你写错了。")
    print()

    print("=== ② 同步版：你写过几百个 for 循环，每个都在用同一套机制 ===")
    lst = []
    print("     直接对空列表调 next()：")
    try:
        next(iter(lst))
    except StopIteration:
        print("        -> 抛出了 StopIteration")
    print("     但放进 for 里：")
    for x in lst:
        print("        循环体", x)
    print("        -> 什么都没发生、没报错。因为 for 内部替你接住了它。")
    print()

    print("=== ③ for 循环的手写等价物 ===")
    print("        it = iter(lst)")
    print("        while True:")
    print("            try:")
    print("                x = next(it)")
    print("            except StopIteration:")
    print("                break          <- 接住，什么都不做，正常退出")
    print()

    print("=== ④ 你的场景：异步版，同一套机制 ===")
    gen = _empty_gen()
    try:
        await anext(gen)
    except StopAsyncIteration:
        print("     空异步生成器 -> 抛 StopAsyncIteration")
    print("     我们的处理：pass（= 接住，什么都不做）")
    print("     结果：chunks 保持 []，前端什么都收不到 —— 这正是「上游没内容」该有的样子")


asyncio.run(_main())
