# day-020/t145_async_integration.py —— t-145 验证脚本
# 验证 common/llm_client.py 的 chat_one(重试) + chat_many(gather 并发) 是否生产可用。
# 跑通后对比「gather 并发」与「串行 await」的耗时，验证并发把网络等待压平。
#
# 运行：.\.venv\Scripts\python.exe study_day_learns\day-020\t145_async_integration.py
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # 必须在 import common.llm_client 之前

from common.llm_client import chat_one, chat_many

PROMPTS = [
    "用一句话解释什么是闭包",
    "用一句话解释什么是装饰器",
    "用一句话解释什么是生成器",
    "用一句话解释什么是协程",
    "用一句话解释什么是异步 IO",
]


async def serial(prompts: list[str]):
    """串行对照：for 循环逐条 await chat_one。返回 (结果, 总耗时)。"""
    t0 = time.monotonic()
    results = [await chat_one(p) for p in prompts]
    return results, time.monotonic() - t0


async def main():
    print("=== chat_many（gather 并发，每个带重试）===")
    t0 = time.monotonic()
    results = await chat_many(PROMPTS)
    t_conc = time.monotonic() - t0
    print(f"并发总耗时: {t_conc:.2f}s")
    for p, r in zip(PROMPTS, results):
        print(f"  [{len(r):>2}字符] {p[:8]}... → {r[:24]}")

    print("\n=== 串行对照（逐条 await chat_one）===")
    _, t_serial = await serial(PROMPTS)
    print(f"串行总耗时: {t_serial:.2f}s")
    print(f"\n加速比: 串行 / 并发 = {t_serial / t_conc:.2f}x")


if __name__ == "__main__":
    asyncio.run(main())
