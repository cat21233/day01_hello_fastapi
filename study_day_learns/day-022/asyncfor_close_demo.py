"""验证：async for 中途退出，会不会自动关闭上游的异步生成器？

背景：routers/llm.py 的 _produce 里有个「内层 try/finally + await gen.aclose()」。
它存在的理由是一个容易忽略的事实：async for 只有在「自然耗尽」时才顺手关掉生成器，
中途 break 或抛异常时，生成器会**悬在半空**，上游连接一直挂着。

跑法：python asyncfor_close_demo.py
"""
import asyncio


async def upstream(tag: str, n: int = 5):
    try:
        for i in range(n):
            yield f"{tag}-{i}"
    finally:
        # 生成器被真正关闭时才会执行这里
        CLOSED.append(tag)


CLOSED: list[str] = []


async def case(title: str, kind: str):
    CLOSED.clear()
    gen = upstream(title)

    if kind == "正常":
        # 让 async for 自然耗尽
        got = [x async for x in gen]
    elif kind == "break":
        async for x in gen:
            break                      # 只取第 1 块就走人
    elif kind == "异常":
        try:
            async for x in gen:
                raise RuntimeError("模拟上游中途炸了")
        except RuntimeError:
            pass
    elif kind == "异常+finally":
        try:
            async for x in gen:
                raise RuntimeError("模拟上游中途炸了")
        except RuntimeError:
            pass
        finally:
            await gen.aclose()         # ← 手动关

    await asyncio.sleep(0)             # 给事件循环一个机会去做清理
    closed = "✅ 已关闭" if title in CLOSED else "❌ 仍挂着（没关）"
    print(f"  {kind:<12} → {closed}")


async def main():
    print("场景                             生成器状态")
    for kind in ("正常", "break", "异常", "异常+finally"):
        await case(kind, kind)

    print("\n再补一刀：不手动关的话，垃圾回收时才会关 —— 但那是「以后」的事")


if __name__ == "__main__":
    asyncio.run(main())
