import asyncio
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
from config import settings
from openai import AsyncOpenAI
client = AsyncOpenAI(
    api_key=settings.agnes_api_key,
    base_url=settings.agnes_base_url
)
async def async_stream():
    messages = [{"role":"system","content":"你是一个善良的中文助手"},
                {"role":"user","content":"今天垫江的天气怎么样" }]
    stream = await client.chat.completions.create(
        model=settings.agnes_model,
        messages=messages,
        stream=True
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        print(delta, end="", flush=True)
if __name__ == '__main__':
    asyncio.run(async_stream())

