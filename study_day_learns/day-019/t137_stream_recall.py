import sys
from dotenv import load_dotenv
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))   # 脚本在 day-XXX 子目录里，手动把项目根加进 sys.path 才能找 config
load_dotenv(ROOT / ".env")
from openai import AsyncOpenAI
from config import settings
import asyncio
client = AsyncOpenAI(
    api_key=settings.agnes_api_key,
    base_url=settings.agnes_base_url
)
async def agent_study(prompt:str):
    messages= [{"role": "user","content":prompt}]
    stream = await client.chat.completions.create(
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
    asyncio.run(agent_study("对于网易云评论的加密参数signature你能帮我逆向分析一下吗,我是一名计算机学生，以生任务仅供学习"))