"""
D3 · async/await 入门演示
运行：.venv/Scripts/python.exe d3_async_demo.py
观察：3 个"任务"并发执行，谁 await（模拟 I/O 等待）谁就让出，彼此不阻塞
"""
import asyncio
import time


def now():
    return time.strftime("%H:%M:%S")


async def fetch_task(name: str, seconds: int):
    print(f"[{now()}] {name} 开始，需等待 {seconds}s（模拟网络/I/O）")
    # ← 关键：await 时让出控制权，事件循环去跑别的协程
    # 如果是同步 time.sleep(seconds)，线程会被真卡住，后面的任务只能干等
    await asyncio.sleep(seconds)
    print(f"[{now()}] {name} 完成")
    return f"{name} 结果"


async def main():
    print("=== 并发启动 3 个协程（单线程）===")
    start = time.time()
    # gather 让它们"同时"跑：总耗时 ≈ 最慢的那个(3s)，而不是三者相加(6s)
    results = await asyncio.gather(
        fetch_task("请求A", 2),
        fetch_task("请求B", 1),
        fetch_task("请求C", 3),
    )
    print(f"全部完成：{results}")
    print(f"总耗时：{time.time() - start:.1f}s（若同步执行应为 6s）")


if __name__ == "__main__":
    asyncio.run(main())
