# day-019/t141_tenacity_retry.py —— tenacity 指数退避重试（t-141）
# 场景：LLM 网关偶发 503/超时 → 自动重试，指数退避（1s → 2s → 4s...封顶）
# 两个实验：
#   A = 前 2 次失败第 3 次成功（看重试怎么把调用救回来）
#   B = 永远失败（看重试耗尽后抛什么、怎么兜底）
import asyncio
import time

from tenacity import retry, stop_after_attempt, wait_exponential


class FakeAPIError(Exception):
    """模拟网关错误（503/超时）"""


# ===== 实验 A：失败 2 次后第 3 次成功 =====
call_count_a = 0


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    #     ↑ 第 n 次失败后等 multiplier * 2^(n-1) 秒：1s, 2s, 4s, 8s...（min/max 夹住上下限）
    stop=stop_after_attempt(5),
    #     ↑ 最多尝试 5 次（含第一次），到数就放弃
    reraise=True,
    #     ↑ 重试耗尽后抛「最后一次的原始异常」；不写则抛 tenacity.RetryError（包裹版，信息更绕）
)
async def flaky_llm(prompt: str) -> str:
    global call_count_a
    call_count_a += 1
    print(f"  [A] 第 {call_count_a} 次调用...")
    await asyncio.sleep(0.2)  # 模拟网络往返
    if call_count_a < 3:
        raise FakeAPIError("模拟网关 503")
    return f"「{prompt}」的回复"


# ===== 实验 B：永远失败，看重试耗尽 =====
call_count_b = 0


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def dead_llm(prompt: str) -> str:
    global call_count_b
    call_count_b += 1
    print(f"  [B] 第 {call_count_b} 次调用...")
    await asyncio.sleep(0.1)
    raise FakeAPIError("模拟网关永久 503")


async def main():
    print("=== 实验 A：前 2 次失败，第 3 次成功 ===")
    t0 = time.monotonic()
    result = await flaky_llm("用一句话解释重试")
    print(f"A 成功: {result}")
    print(f"A 总耗时: {time.monotonic() - t0:.2f}s（预期 ≈ 3.6s = 0.2*3 次调用 + 退避 1s+2s）\n")

    print("=== 实验 B：永远失败，3 次后放弃 ===")
    t0 = time.monotonic()
    try:
        await dead_llm("必然失败")
    except FakeAPIError as e:
        # reraise=True → 这里捕获的是原始 FakeAPIError
        # 若去掉 reraise → 这里要捕 tenacity.RetryError 才接得住
        print(f"B 放弃，捕获原始异常: {e}")
    print(f"B 总耗时: {time.monotonic() - t0:.2f}s（预期 ≈ 3.3s = 0.1*3 + 退避 1s+2s）")


if __name__ == "__main__":
    asyncio.run(main())
