from fastapi import APIRouter,Query
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()

async def greet_stream_generator(name: str):
    for ch in f"hello,{name}":
        yield f"data:{ch}\n\n"
        await asyncio.sleep(0.1)


@router.get("/stream/greet")
def stream_greet(name: str = Query(..., description="你的名字")):
    return StreamingResponse(
        greet_stream_generator(name),
        media_type="text/event-stream",
    )