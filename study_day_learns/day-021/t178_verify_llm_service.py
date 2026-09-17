# study_day_learns/day-021/t178_verify_llm_service.py
# t-178 验收脚本：证明 llm_service 三条能力都能用
#   ① 换厂商只需改一个字符串  ② 流式逐 token  ③ 并发不退化

import sys
import time
import asyncio
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from llm_service import LLMClient


async def main():
    print("=" * 50)
    print("① 单次调用 + 换厂商（只改一个参数）")
    print("=" * 50)

    ds = LLMClient("deepseek")
    print("deepseek:", await ds.one("用一句话说明什么是 FastAPI，不要代码"))

    ag = LLMClient("agnes")
    print("agnes   :", await ag.one("用一句话说明什么是 FastAPI，不要代码"))

    print()
    print("=" * 50)
    print("② 流式：逐 token 打印")
    print("=" * 50)
    t0 = time.perf_counter()
    first_token_at = None
    count = 0
    async for piece in ds.stream("用三句话介绍什么是异步编程"):
        if first_token_at is None:
            first_token_at = time.perf_counter() - t0
        print(piece, end="", flush=True)
        count += 1
    total = time.perf_counter() - t0
    print(f"\n\n[首 token 延迟 {first_token_at:.2f}s | 共 {count} 块 | 总耗时 {total:.2f}s]")

    print()
    print("=" * 50)
    print("③ 并发 many()：3 条 prompt，看是否 ≈ 最慢单个")
    print("=" * 50)
    prompts = [
        "用一句话解释什么是向量",
        "用一句话解释什么是余弦相似度",
        "用一句话解释什么是 RAG",
    ]

    t0 = time.perf_counter()
    serial = []
    for p in prompts:
        serial.append(await ds.one(p))
    serial_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    concurrent = await ds.many(prompts, max_concurrency=3)
    concurrent_time = time.perf_counter() - t0

    print(f"串行耗时   : {serial_time:.2f}s")
    print(f"并发耗时   : {concurrent_time:.2f}s")
    print(f"提速倍数   : {serial_time / concurrent_time:.2f}x")
    print(f"结果顺序一致: {serial[0][:8] == concurrent[0][:8]}")
    for i, r in enumerate(concurrent, 1):
        print(f"  {i}. {r[:40]}...")


if __name__ == "__main__":
    asyncio.run(main())
