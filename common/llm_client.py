# common/llm_client.py —— 生产化 LLM 调用层（t-145 整合）
# 把 day-019 的 t-141(重试) + t-140(并发) 整合成一个可复用模块。
#
# 设计要点：
#   1. 全局单例 client：底层连接池复用 keep-alive，gather 并发时不重复建池
#      （若每次调用都 new 一个 → 每个请求各开一个连接池，并发时更浪费）
#   2. chat_one：单次调用 + tenacity 指数退避重试（应对网关偶发 503/超时）
#   3. chat_many：asyncio.gather 并发多个 chat_one，每个自带重试，结果顺序与输入一致
import asyncio

from tenacity import retry, stop_after_attempt, wait_exponential

from openai import AsyncOpenAI
from config import settings

# 全局唯一 client（模块导入时建一次）
client = AsyncOpenAI(api_key=settings.agnes_api_key, base_url=settings.agnes_base_url)


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    #     ↑ 第 n 次失败后等 multiplier * 2^(n-1) 秒：1s, 2s, 4s, 8s...（min/max 夹上下限）
    stop=stop_after_attempt(5),
    #     ↑ 最多尝试 5 次（含第一次），到数放弃
    reraise=True,
    #     ↑ 重试耗尽后抛「最后一次的原始异常」；否则抛 RetryError（包裹版，信息更绕）
)
async def chat_one(prompt: str) -> str:
    """单次 LLM 调用 + 指数退避重试。返回回复文本。"""
    resp = await client.chat.completions.create(
        model=settings.agnes_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    # strip 掉模型常带的前导/尾随空白（如 \n\n），调用方拿到干净文本
    return (resp.choices[0].message.content or "").strip()


async def chat_many(
    prompts: list[str],
    max_concurrency: int = 3,
    return_exceptions: bool = False,
) -> list[str | BaseException]:
    """并发跑多个 prompt，每个都带重试。返回与输入顺序一致的结果列表。

    max_concurrency：同时发出的请求上限。无脑全并发会打爆网关触发限流，
    反而比串行慢（已实测 0.24x）——用信号量封顶是生产常识。
    return_exceptions：True 时单个 prompt 失败不会拖垮整批，
    失败项以 Exception 对象形态留在结果列表对应位置（其余正常返回）。
    False（默认）时任一失败则整批抛异常（gather 默认行为）。
    """
    sem = asyncio.Semaphore(max_concurrency)

    async def _limited(prompt: str) -> str:
        async with sem:                      # 最多 max_concurrency 个协程同时进 chat_one
            return await chat_one(prompt)

    # gather 负责并发调度；chat_one 内部已负责重试 —— 职责分离
    # return_exceptions 透传：决定「部分失败」是拖垮整批还是降级为结果元素
    results = await asyncio.gather(
        *[_limited(p) for p in prompts],
        return_exceptions=return_exceptions,
    )
    return list(results)