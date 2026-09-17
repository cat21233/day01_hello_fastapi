"""SSE 断点续传最小示例（纯合成数据，不调 LLM，跑 10 秒就能看懂）。

两个端点 = 两种真实做法：

  /stateless  无状态：重连时「从头重新生成，跳过已发过的部分」
              适合内容能精确重放的数据源 —— 数据库分页、日志文件、固定序列。
              缺点：重新生成有代价（耗时 / 花钱 / 结果可能变）

  /buffered   有缓存：服务端把已生成的 chunk 存下来，重连时直接从断点切片补发
              适合 LLM —— 同一个 prompt 重跑不保真（temperature>0 结果会变），
              而且每次重跑都是真金白银。

启动：cd study_day_learns/day-022/sse_resume_demo
      python -m uvicorn demo_server:app --port 8020
"""
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()
TOTAL = 8          # 一共 8 块
DELAY = 0.4        # 每块之间的间隔，用来模拟「模型在慢慢生成」


def _resume_from(request: Request) -> int:
    """断点 = 客户端上次收到的最后一个 id。

    浏览器原生 EventSource 断线重连时会自动带 Last-Event-ID 头；
    手写客户端（httpx / fetch）必须自己带 —— 这是最容易漏的一步。
    """
    raw = request.headers.get("last-event-id", "0")
    return int(raw) if raw.isdigit() else 0


@app.get("/stateless")
async def stateless(request: Request):
    start = _resume_from(request) + 1

    async def gen():
        for i in range(start, TOTAL + 1):
            await asyncio.sleep(DELAY)          # 假装在算
            yield f"id: {i}\ndata: 第 {i} 块\n\n"
        yield "event: end\ndata: done\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# 服务端缓存：{会话 id: [已生成的所有 chunk]}
# buf 的下标 i 对应 id = i + 1，这个换算关系是补发的核心。
_BUFFERS: dict[str, list[str]] = {}


@app.get("/buffered")
async def buffered(request: Request, sid: str = "demo"):
    start = _resume_from(request)
    buf = _BUFFERS.setdefault(sid, [])

    async def gen():
        # ① 补发：断点之后「已经生成过」的，直接从缓存切片吐回去，不重算
        for i in range(start, len(buf)):
            yield f"id: {i + 1}\ndata: {buf[i]}\n\n"

        # ② 续生成：从缓存末尾接着往下，边生成边入缓存
        for i in range(len(buf), TOTAL):
            await asyncio.sleep(DELAY)
            buf.append(f"第 {i + 1} 块（新生成）")
            yield f"id: {i + 1}\ndata: {buf[i]}\n\n"

        yield "event: end\ndata: done\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
