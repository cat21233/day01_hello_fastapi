"""asyncio.Event 在「生产者 / 消费者」模型里的三种写法对照。

背景：routers/llm.py 的 _tail 里有 `st.changed.clear()`，位置在 drain 之前。
本脚本用同一套骨架（生产者 append + set / 消费者 drain + wait）跑三种写法，
量化它们的差别 —— 尤其是「删掉 clear 会怎样」。

三个变体结构完全一样，只差 clear() 的位置：
  A  ✅ clear 在 drain 之前（= routers/llm.py 现在的写法）
  B  ❌ 删掉 clear
  C  ❌ clear 在 drain 之后

必须每个变体单独跑一个进程（会用 /usr/bin/timeout 或 Git Bash 的 timeout 兜底），
因为卡死的变体会**阻塞整个事件循环**，连 wait_for 的定时器都放不出来。
跑法：python event_clear_demo.py A -v
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


async def tail_A(chunks, ev, state, stats):
    """✅ 正确：先 clear 再 drain（= routers/llm.py 现在的写法）"""
    sent = 0
    while True:
        stats["loops"] += 1
        ev.clear()                     # ① 先把闹钟按下去
        while sent < len(chunks):      # ② 再把已有的全发出去
            yield chunks[sent]
            sent += 1
        if state["done"]:              # ③ 生产完了 → 收工
            return
        await ev.wait()                # ④ 真的能睡


async def tail_B(chunks, ev, state, stats):
    """❌ 删掉 clear：Event 一旦 set 就永远保持 set，wait() 立刻返回"""
    sent = 0
    while True:
        stats["loops"] += 1
        while sent < len(chunks):
            yield chunks[sent]
            sent += 1
        if state["done"]:
            return
        await ev.wait()


async def tail_C(chunks, ev, state, stats):
    """❌ clear 放在 drain 之后：清标记可能与「新内容到达」交错"""
    sent = 0
    while True:
        stats["loops"] += 1
        while sent < len(chunks):
            yield chunks[sent]
            sent += 1
        if state["done"]:
            return
        ev.clear()                     # ← 位置挪到了 drain 之后
        await ev.wait()


VARIANTS = {"A": tail_A, "B": tail_B, "C": tail_C}


async def drive(name, tail_fn, verbose):
    chunks, stats = [], {"loops": 0}
    ev = asyncio.Event()
    state = {"done": False}
    prod = asyncio.create_task(produce(chunks, ev, state))

    got = []
    t0, cpu0 = time.perf_counter(), time.process_time()
    print(f"变体 {name}", flush=True)
    async for item in tail_fn(chunks, ev, state, stats):
        got.append(item)
        if verbose:
            print(f"    [{time.perf_counter() - t0:5.2f}s] 收到 {item}", flush=True)
    wall, cpu = time.perf_counter() - t0, time.process_time() - cpu0

    await prod
    print(f"    结果     : 正常完成", flush=True)
    print(f"    收到块数 : {len(got)} / {N}", flush=True)
    print(f"    消费者循环次数: {stats['loops']:,}", flush=True)
    print(f"    墙钟 / CPU: {wall:.2f}s / {cpu:.2f}s  → CPU 占用 {cpu / max(wall, 1e-9) * 100:.0f}%",
          flush=True)


async def drive_serial(verbose):
    """❌ 对照：路由里写成 `await _produce(...)` 再 return —— 生成期间响应根本没开始"""
    chunks, stats = [], {"loops": 0}
    ev = asyncio.Event()
    state = {"done": False}
    t0 = time.perf_counter()
    await produce(chunks, ev, state)        # ← 卡在这里，直到全部生成完
    first = time.perf_counter() - t0
    got = []
    async for item in tail_A(chunks, ev, state, stats):
        got.append(item)
    total = time.perf_counter() - t0
    print("变体 D：先 await 生产完再返回（等价于 await _produce(...)）", flush=True)
    print(f"    首块延迟 : {first:.2f}s   ← 用户干等这么久才看到第一个字", flush=True)
    print(f"    收到块数 : {len(got)} / {N}", flush=True)
    print(f"    总耗时   : {total:.2f}s", flush=True)


if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
    if which == "D":
        asyncio.run(drive_serial("-v" in sys.argv))
    else:
        asyncio.run(drive(which, VARIANTS[which], "-v" in sys.argv))
