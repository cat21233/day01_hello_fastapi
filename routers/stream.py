from fastapi import APIRouter, Query, Request, Depends
from fastapi.responses import StreamingResponse
import asyncio
from routers.auth import get_current_user
from routers.limits import limiter

router = APIRouter()


# ---------- 公开 SSE demo 1：逐字符问候 ----------
async def greet_stream_generator(name: str):
    for ch in f"hello,{name}":
        yield f"data: {ch}\n\n"
        await asyncio.sleep(0.1)
    yield "event: end\ndata: done\n\n"


@router.get("/stream/greet")
async def stream_greet(name: str = Query(..., description="你的名字")):
    return StreamingResponse(
        greet_stream_generator(name),
        media_type="text/event-stream",
    )


# ---------- 公开 SSE demo 2：带 id 的计数器（支持断线续传） ----------
async def counter_stream_generator(start_from: int):
    for n in range(start_from, 11):
        yield f"id:{n}\ndata:第{n}条\n\n"
        await asyncio.sleep(0.3)
    yield "event: end\ndata: done\n\n"


@router.get("/stream/counter")
async def stream_counter(request: Request):
    last_id = request.headers.get("last-event-id")
    start_from = int(last_id) + 1 if last_id else 1
    return StreamingResponse(
        counter_stream_generator(start_from),
        media_type="text/event-stream",
    )


# ---------- 受保护 SSE：认证 + 限流 + 流式 三件套合体 ----------
async def protected_stream_generator():
    for n in range(1, 6):
        yield f"data: 受保护的第{n}条\n\n"
        await asyncio.sleep(0.2)
    yield "event: end\ndata: done\n\n"


@router.get("/stream/protected")
@limiter.limit("20/minute")
async def stream_protected(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    return StreamingResponse(
        protected_stream_generator(),
        media_type="text/event-stream",
    )
