import sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from openai import AsyncOpenAI
from config import settings
import asyncio
client = AsyncOpenAI(
    api_key=settings.agnes_api_key,
    base_url=settings.agnes_base_url
)
async def ai_chat(prompt:str):
    messages = [{"role": "user","content":prompt}]
    resp = await client.chat.completions.create(
        model=settings.agnes_model,
        messages=messages
    )
    return resp.choices[0].message.content.strip()
if __name__ == '__main__':
    print(asyncio.run(ai_chat("关于deepseek hermees你了多少")))