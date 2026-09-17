# day-019/t140_gather_concurrent.py —— asyncio.gather 并发批量调 prompt（t-140）
# 目标：同一组 5 个 prompt，分别用「串行 await」和「asyncio.gather 并发」跑，
#       对比总耗时，验证并发能把网络等待压平。
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # ⚠️ 必须在 from config import settings 之前！否则根目录不在 sys.path

from config import settings
from openai import AsyncOpenAI

# 客户端只建一次：底层有连接池、复用 keep-alive 连接。
# 若每次调用都 new 一个 → 每个请求各开一个连接池，gather 并发时更浪费。
client = AsyncOpenAI(base_url=settings.agnes_base_url, api_key=settings.agnes_api_key)

# 5 个待调用的 prompt
PROMPTS = [
    "用一句话解释什么是闭包",
    "用一句话解释什么是装饰器",
    "用一句话解释什么是生成器",
    "用一句话解释什么是协程",
    "用一句话解释什么是异步 IO",
]


async def call_one(prompt: str) -> tuple[str, float]:
    """单次 LLM 调用。返回 (prompt, 本次耗时秒)。"""
    t0 = time.monotonic()
    resp = await client.chat.completions.create(
        model=settings.agnes_model, messages=[{"role": "user", "content": prompt}]
    )
    _ = resp.choices[0].message.content
    cost = time.monotonic() - t0
    return (prompt, cost)


async def serial() -> float:
    """串行跑完 5 个 prompt：for 循环逐条 await。返回总耗时（秒）。"""
    t0 = time.monotonic()
    for p in PROMPTS:
        await call_one(p)
    return time.monotonic() - t0


async def concurrent() -> float:
    """gather 一次性并发 5 个 prompt。返回总耗时（秒）。"""
    t0 = time.monotonic()
    results = await asyncio.gather(*[call_one(p) for p in PROMPTS])
    return time.monotonic() - t0


if __name__ == "__main__":
    print("=== 串行 ===")
    t_serial = asyncio.run(serial())
    print(f"串行总耗时: {t_serial:.2f}s")

    print("=== 并发 ===")
    t_conc = asyncio.run(concurrent())
    print(f"并发总耗时: {t_conc:.2f}s")

    print(f"\n加速比: 串行 / 并发 = {t_serial / t_conc:.2f}x")
