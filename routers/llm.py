from fastapi import APIRouter, Query, Request, Depends

from common.sse import sse_response
from routers.auth import get_current_user
from routers.limits import limiter
from llm_service import LLMClient
from config import settings

import asyncio
import time

router = APIRouter()

# 路由层不认识 openai：厂商名 / base_url / model 全藏进 LLMClient。
# 用哪家由 .env 的 LLM_PROVIDER 决定，换厂商不用动这个文件。
llm = LLMClient(settings.llm_provider)


class _Stream:
    """一次生成的全部状态。

    核心思想：SSE 连接只是这个对象的「观众」。观众走了，生成还在继续；
    观众回来，先把错过的那段补给它。所以断线重连不需要重跑模型。
    """

    __slots__ = ("chunks", "done", "changed")

    def __init__(self):
        self.chunks: list[str] = []      # 已生成的全部内容，下标 i 对应 SSE 的 id = i + 1
        self.done: bool = False          # 生成结束（正常 / 超时 / 异常都算结束）
        self.changed = asyncio.Event()   # 有新内容或已结束 → set，用于唤醒正在 tail 的连接


_STREAMS: dict[str, _Stream] = {}
_EXPIRE_SECONDS = 120        # 生成完成后缓存保留时长，到点清掉，避免内存无限涨


async def _produce(stream_id: str, prompt: str) -> None:
    """后台生产：把上游 chunk 一块块写进 _Stream，写一块 set 一次事件。

    这是独立的 asyncio.Task —— 生命周期和 HTTP 连接无关。
    客户端断开时 Starlette 只会取消「看」它的那个连接，生产任务照跑。
    """
    st = _STREAMS[stream_id]
    try:
        gen = llm.stream(prompt)
        async with asyncio.timeout(10.0):        # 只保护首块：上游 10s 不吐字就是有问题
            first = await anext(gen)
        st.chunks.append(first)
        st.changed.set()

        try:
            async for delta in gen:
                st.chunks.append(delta)
                st.changed.set()
        finally:
            await gen.aclose()  # 正常/异常都要关掉上游，别让连接挂着
    except StopAsyncIteration:
        pass
    except TimeoutError:
        st.chunks.append("上游接口响应超时,请稍后重试")
    except Exception as exc:
        # 关键：异常要变成「一条普通 chunk」，绝不能让它把 SSE 连接炸断。
        # agnes 额度打满时的 429 就走这里，前端看到的是提示而不是断流。
        st.chunks.append(f"[上游异常] {type(exc).__name__}: {exc}")
    finally:
        st.done = True
        st.changed.set()
        asyncio.create_task(_expire(stream_id, _EXPIRE_SECONDS))


async def _expire(stream_id: str, delay: float) -> None:
    await asyncio.sleep(delay)
    _STREAMS.pop(stream_id, None)


async def _tail(stream_id: str, resume_from: int):
    """观众视角：从 resume_from 之后开始，把 _Stream 里的内容一块块交给这个连接。

    已生成好的部分立刻返回（读缓存，秒到）；还没生成好的部分等事件唤醒。
    """
    st = _STREAMS.get(stream_id)
    if st is None:
        return

    sent = resume_from
    while True:
        # clear() 必须调，但位置不关键（这是实测结论，不是猜的）：
        #   · 必须 clear：asyncio.Event 一旦 set 就永远保持 set，wait() 每次立刻返回
        #     且不让出控制权 → 循环里再没有 await 点 → 整个事件循环被这一个协程独占，
        #     连别的任务的定时器都放不出来 = 死锁。实测删掉 clear：收到第 1 块就卡死。
        #   · clear 放 drain 之前或之后都能正确工作：chunks 是共享真源，drain 会自己
        #     追平，被 clear 抹掉的那个 set() 已无信息价值。放前面只是少一次空转。
        st.changed.clear()
        while sent < len(st.chunks):
            yield st.chunks[sent]
            sent += 1
        if st.done:
            return
        await st.changed.wait()


def _resume_from(request: Request) -> int:
    """断点 = 客户端上次收到的最后一个 id（EventSource 断线重连会自动带）。"""
    raw = request.headers.get("last-event-id", "0")
    return int(raw) if raw.isdigit() else 0


@router.get("/llm/chat")
@limiter.limit("10/minute")
async def llm_chat(
    request: Request,
    prompt: str = Query(..., min_length=1),
    stream_id: str = Query(..., min_length=1, description="会话 id，断线重连必须用同一个"),
    current_user: dict = Depends(get_current_user),
):
    """可断点续传的 LLM 流式接口。

    stream_id 由客户端生成（uuid 即可）：
      · 第一次带进来 → 起一个后台生成任务
      · 断线后重连（同一个 stream_id + Last-Event-ID 头）→ 从断点接着收，
        错过的那段直接读缓存补发，不重跑模型、不重复扣费
    """
    st = _STREAMS.get(stream_id)
    if st is None:
        _STREAMS[stream_id] = _Stream()
        asyncio.create_task(_produce(stream_id, prompt))
        resume_from = 0
    else:
        # 客户端报的断点可能超前（它记的数比我们已生成的还多）→ 夹紧，别把内容跳过去
        resume_from = min(_resume_from(request), len(st.chunks))

    return sse_response(_tail(stream_id, resume_from), start_id=resume_from)


@router.get("/slow-async")
async def slow_async():
    await asyncio.sleep(3)
    return {"mode": "async", "slept": 3}


@router.get("/slow-block")
async def slow_block():
    time.sleep(3)
    return {"mode": "block", "slept": 3}
