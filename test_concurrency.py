import asyncio
import httpx
import time

async def hit(client, url):
    start = time.time()
    r = await client.get(url)
    return time.time() - start, r.json()

async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
        # 测 /slow-async 并发 2 个
        t0 = time.time()
        results = await asyncio.gather(
            hit(client, "/slow-async"),
            hit(client, "/slow-async"),
        )
        print(f"async 并发 2 个总耗时: {time.time()-t0:.2f}s")
        for r in results:
            print(f"  单次: {r[0]:.2f}s  返回: {r[1]}")

        # 测 /slow-block 并发 2 个
        t0 = time.time()
        results = await asyncio.gather(
            hit(client, "/slow-block"),
            hit(client, "/slow-block"),
        )
        print(f"block 并发 2 个总耗时: {time.time()-t0:.2f}s")
        for r in results:
            print(f"  单次: {r[0]:.2f}s  返回: {r[1]}")

asyncio.run(main())
