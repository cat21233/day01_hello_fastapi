import asyncio
import time

# ===== 异步版（已完成） =====
async def worker(i):
    print(f"开始{i}")
    await asyncio.sleep(2)
    print(f"结束{i}")

async def async_main():
    start = time.time()
    await asyncio.gather(worker(1), worker(2), worker(3))
    print(f"异步版总耗时: {time.time() - start:.2f}s")

# ===== 同步版（你填 3 个空） =====
def sync_worker(i):
    print(f"开始{i}")
    time.sleep(2)                  # ① 同步阻塞 2 秒用什么？填一个函数调用
    print(f"结束{i}")

def sync_main():
    start = time.time()
    for i in range(1, 4):
        sync_worker(i)           # ② 在循环里调用同步 worker
    print(f"同步版总耗时: {time.time() - start: .2f}s")

# 入口：先异步后同步
asyncio.run(async_main())
sync_main()
