import asyncio
async def slow_api():
    await asyncio.sleep(3)
    return "result"
async def safe_call():
    try:
        result = await asyncio.wait_for(slow_api(),timeout=2)
    except asyncio.TimeoutError:
        result = "超时兜底"
    return result
asyncio.run(safe_call())

async def worker(name,delay):
    await asyncio.sleep(delay)
    print(f"{name}")
    return name
async def main():
    task_a = asyncio.create_task(worker("A", 2))
    task_b = asyncio.create_task(worker("B", 1))
    print("两个任务已在后台跑,主协程干别的事")

    await asyncio.sleep(0.3)
    result_a = await task_a
    result_b = await task_b

    print(f"最终结果: {result_a}, {result_b}")
asyncio.run(main())