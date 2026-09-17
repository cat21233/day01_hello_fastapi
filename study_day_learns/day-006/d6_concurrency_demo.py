import asyncio
import httpx
import time
async def fetch_user(user_id):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f'https://jsonplaceholder.typicode.com/users/{user_id}')
        return resp.json()
def sync_version():
    start = time.time()
    asyncio.run(_sequential_fetch())
    print(f"同步耗时:{time.time()-start: .2f}秒")
async def _sequential_fetch():
    for user_id in [1, 2, 3]:
        await fetch_user(user_id)
async def async_version():
    start = time.time()
    await asyncio.gather(
        fetch_user(1),
        fetch_user(2),
        fetch_user(3)
    )
    print(f"并发总耗时: {time.time()-start: .2f}秒")

if __name__ == "__main__":
    sync_version()
    asyncio.run(async_version())


