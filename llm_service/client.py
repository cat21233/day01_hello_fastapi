# llm_service/client.py —— 核心类：把「怎么调」和「调什么」分开
#
# 三个方法的分工：
#   one(prompt)     单次问答，带指数退避重试          → 用于分类 / 抽取 / 判断
#   stream(prompt)  流式逐 token 产出，不重试          → 用于对话 / SSE 接口
#   many(prompts)   并发多条 one()，信号量封顶         → 用于批量实验 / RAG 批量摘要
#
# 关键设计：重试为什么只装饰 one()？
#   流式一旦已经吐出若干 token，重试会「从头再来」→ 前端收到重复内容。
#   可重试的前提是「失败时没有副作用」，流式不满足 → 不重试，交给调用方决定。
import asyncio
from typing import AsyncGenerator

from tenacity import retry, stop_after_attempt, wait_exponential,retry_if_exception_type
from openai import APIConnectionError,APITimeoutError,RateLimitError
from llm_service.factory import get_client, get_model
from common.logger import log_llm


class LLMClient:
    """LLM 统一调用入口。上层只依赖这个类，不碰 openai SDK。"""

    def __init__(self, provider: str = "deepseek", temperature: float = 0.0):
        self.provider = provider
        self.temperature = temperature
        # client 从工厂拿（复用连接池）；存为实例属性方便调用
        self._client = get_client(provider)
        self._model = get_model(provider)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((APITimeoutError,APIConnectionError,RateLimitError)),
        reraise=True,
    )
    async def one(self, prompt: str, system: str | None = None) -> str:
        """单次调用。失败按 1s → 2s → 4s 退避重试，共 3 次。

        system: 可选的 system prompt（t-235 动态选择用）。传 None 就退化成原来的纯 user 提问。
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self.temperature,
        )
        # ✍️ 闭卷复盘点（t-240）：resp.usage 里有本次调用的 token 用量，
        #    把它记进结构化日志。下面这行是参考答案，待会儿你自己重推一遍：
        if resp.usage:
            log_llm(
                provider=self.provider,
                model=self._model,
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
            )
        return (resp.choices[0].message.content or "").strip()

    async def stream(self, prompt: str, system: str | None = None) -> AsyncGenerator[str, None]:
        """流式产出增量文本。只 yield 非空内容，SSE 帧由 common/sse.py 负责。

        注意：这是 async generator（async def + yield），调用方必须 `async for` 消费。
        对它 `await` 不是「拿到生成器对象」，而是直接抛
        TypeError: object async_generator can't be used in 'await' expression。
        判据：async def 里有 yield → async generator（async for 驱动）
              async def 里没 yield → coroutine      （await 驱动）

        system: 可选的 system prompt（t-235 动态选择用）。
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self.temperature,
            stream=True,
            stream_options={"include_usage": True},   # 让最后一个 chunk 带上 usage（token 数）
        )
        prompt_tokens = 0
        completion_tokens = 0
        async for chunk in stream:
            # 流式下 usage 只在最后一个 chunk 返回（需上面 stream_options 开启）
            if getattr(chunk, "usage", None):
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens
            delta = chunk.choices[0].delta.content or ""
            if delta.strip():
                yield delta
        # ✍️ 闭卷复盘点（t-240）：流式结束，把累计的 token 用量记进日志。
        if prompt_tokens or completion_tokens:
            log_llm(
                provider=self.provider,
                model=self._model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

    async def many(
        self,
        prompts: list[str],
        max_concurrency: int = 3,
        return_exceptions: bool = False,
    ) -> list[str | BaseException]:
        """并发多条 prompt，结果顺序与输入一致。

        max_concurrency 用 Semaphore 封顶：无脑全并发会打爆网关触发限流，
        实测比串行还慢（0.24x）。
        """
        sem = asyncio.Semaphore(max_concurrency)

        async def _limited(p: str):
            async with sem:
                return await self.one(p)

        results = await asyncio.gather(
            *[_limited(p) for p in prompts],
            return_exceptions=return_exceptions,
        )
        return list(results)
