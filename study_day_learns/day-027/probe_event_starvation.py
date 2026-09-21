"""探针：Event 不 clear 时，到底是「自己空转」还是「饿死整个事件循环」？

判别方法：在同一个 event loop 里另起一个【心跳任务】，每 0.5s 打印一次。
  · 如果只是"自己空转"（CPU 高但还在让出）→ 心跳照常打印
  · 如果是"独占 event loop"（饿死别人）    → 心跳一次都不会打印

跑法：
    python probe_event_starvation.py A     # 正常版（clear 在 drain 之前）
    python probe_event_starvation.py B     # 删掉 clear 的坏版
B 会卡死，必须用外部 timeout 兜住（本文件自己救不了自己）。

历史背景：day-022 时 AI 曾断言 B 是"忙碌轮询"，实测推翻了 —— 本探针是那个结论的补强证据。
"""
import asyncio
import sys
import time

N = 12          # 一共生产 12 块
GAP = 0.05      # 每块之间的间隔（模拟模型在慢慢吐字）


async def produce(chunks, ev, state):
    for i in range(N):
        await asyncio.sleep(GAP)
        chunks.append(f"块{i + 1}")
        ev.set()                       # 写完就敲门
    state["done"] = True
    ev.set()                           # 收工也要敲


def make_tail(use_clear: bool):
    """返回一个 tail 异步生成器；use_clear=False 即模拟"删掉 clear"。"""

    if use_clear:
        async def tail(chunks, ev, state):
            sent = 0
            while True:
                ev.clear()                     # ① 先把闹钟按下去
                while sent < len(chunks):
                    yield chunks[sent]
                    sent += 1
                if state["done"]:
                    return
                await ev.wait()                # ② 真的能睡
    else:
        async def tail(chunks, ev, state):
            sent = 0
            while True:
                while sent < len(chunks):
                    yield chunks[sent]
                    sent += 1
                if state["done"]:
                    return
                await ev.wait()                # 已 set → 立刻返回，不让出

    return tail


async def main(which: str):
    t0 = time.perf_counter()
    beats = []

    async def heartbeat():
        """旁观者：每隔 0.5s 敲一次钟。如果它哑了，说明事件循环被独占了。"""
        for i in range(4):
            await asyncio.sleep(0.5)
            beats.append(i + 1)
            print(f"  [心跳] 第 {i + 1} 次 @ {time.perf_counter() - t0:4.2f}s", flush=True)

    chunks, state = [], {"done": False}
    ev = asyncio.Event()
    tail = make_tail(which == "A")

    hb = asyncio.create_task(heartbeat())
    prod = asyncio.create_task(produce(chunks, ev, state))

    got = []
    print(f"=== 变体 {which} ===", flush=True)
    async for item in tail(chunks, ev, state):
        got.append(item)
        print(f"  [tail] 发出 {item} @ {time.perf_counter() - t0:4.2f}s", flush=True)

    print(f"  tail 正常结束，共 {len(got)} 块 @ {time.perf_counter() - t0:.2f}s", flush=True)
    print(f"  心跳记录: {beats}", flush=True)
    await prod
    await hb


if __name__ == "__main__":
    asyncio.run(main((sys.argv[1] if len(sys.argv) > 1 else "A").upper()))
