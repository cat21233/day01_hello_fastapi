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
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url
)
async def ai_chat(prompt:str):

    messages = [{"role": "user","content": prompt}]
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=0
    )
    return resp.choices[0].message.content.strip()
async def run():
    QUESTION = "一个三位数，各位数字之和 15，个位比十位大 3，百位是十位的 2 倍，求这个三位数"

    PROMPT_A = QUESTION + "\n直接给出答案，不要解释。"  # 无 CoT
    PROMPT_B = QUESTION + "\n请一步一步推理，最后再给出答案。"  # 有 CoT

    a = await ai_chat(PROMPT_A)
    b = await ai_chat(PROMPT_B)
    print(a)
    print(b)
if __name__ == '__main__':
    asyncio.run(run())