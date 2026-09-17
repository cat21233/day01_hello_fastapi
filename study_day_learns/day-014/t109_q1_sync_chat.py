import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio
# 脚本在 study_day_learns/ 子目录，.env 在项目根，先手动加载
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from config import settings  # ← 这行原本就有，确保放在 load_dotenv 之后
from openai import AsyncOpenAI
# ... 其余不变


client = AsyncOpenAI(
    api_key=settings.agnes_api_key,
    base_url=settings.agnes_base_url
)
async def once_request(prompt:str):
    messages = [{"role": "user", "content": prompt}]
    stream =await client.chat.completions.create(
        model=settings.agnes_model,
        messages=messages,
        stream=True
    )
    try:
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            print(delta, end="")
    except RuntimeError as e:
        if "athrow" in str(e):
            print(f"\n[收尾异常,忽略]{e}", file=sys.stderr)
        else:
            raise


if __name__ == '__main__':
    asyncio.run(once_request("你是谁"))