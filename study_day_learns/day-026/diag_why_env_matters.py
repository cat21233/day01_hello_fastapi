"""诊断：服务器没起时，hit() 到底拿到了什么？为什么会抛 JSONDecodeError 而不是 ConnectError？

跑两次，唯一变量是 trust_env（是否读 HTTP_PROXY 等环境变量）：

    第 1 次  trust_env=True （httpx 默认行为，会走代理）
    第 2 次  trust_env=False（无视代理，直连 127.0.0.1:8000）

判别力：如果两次报错类型不同，说明「代理」在中间插了一脚，
        报错类型是被环境决定的，不是代码决定的。

运行：python study_day_learns/day-026/diag_why_env_matters.py
"""

import asyncio
import os

import httpx

URL = "http://127.0.0.1:8000/slow-async"


async def probe(trust_env: bool):
    label = f"trust_env={trust_env}"
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000",
                                     timeout=30,
                                     trust_env=trust_env) as client:
            r = await client.get("/slow-async")
            print(f"  r.status_code = {r.status_code}")
            print(f"  r.content     = {r.content!r}")
            try:
                print(f"  r.json()      = {r.json()}")
            except Exception as e:
                print(f"  r.json() 抛异常 -> {type(e).__name__}: {e}")
    except Exception as e:
        print(f"  请求本身就抛异常 -> {type(e).__name__}")
        print(f"     {e}")


async def main():
    print("当前进程看到的代理相关环境变量：")
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"):
        print(f"  {k} = {os.environ.get(k)}")

    await probe(True)
    await probe(False)


asyncio.run(main())
