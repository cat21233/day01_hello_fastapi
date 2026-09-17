from fastapi.responses import StreamingResponse
from typing import AsyncGenerator


def sse_response(
    content_gen: AsyncGenerator[str, None],
    *,
    end_event: str = "end",
    end_data: str = "done",
    start_id: int = 0,
):
    """把『只 yield 原始文本』的生成器，包成标准 SSE 响应。

    自动负责：
      1. 给每个 chunk 编号（`id: n`，从 start_id + 1 开始）+ `data:` 前缀 + `\\n\\n` 帧分隔
      2. 流结束后补 `event: end` 结束信号

    为什么要 id：
      浏览器原生 EventSource 断线重连时，会自动把「最后收到的那个 id」放进
      Last-Event-ID 请求头。服务端据此知道该从哪续 —— 这是断点续传的全部秘密。
      start_id 就是给「重连后接着编号」用的：续传时传上次的断点，
      这样新帧的编号能和第 1 次连接无缝衔接。

    业务生成器只需关心『吐什么内容』，编号和 SSE 格式都由这里统一处理。
    """
    async def _frame():
        idx = start_id
        async for chunk in content_gen:
            if chunk:
                idx += 1
                yield f"id: {idx}\ndata: {chunk}\n\n"
        yield f"event: {end_event}\ndata: {end_data}\n\n"

    return StreamingResponse(_frame(), media_type="text/event-stream")
