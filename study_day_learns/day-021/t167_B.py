import sys,json,asyncio
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/".env")
from llm_service import LLMClient

TEXT = "张三，男，1998年出生，住在重庆市渝北区，职业是软件工程师。"

PROMPT_A = f"从下面这段话里提取信息：要求明确抽出姓名,性别,出生年份,住址,职业5个字段。输出格式为字段:值\n{TEXT}"      # ← 你的第一步：就写这一行

async def main():
    llm = LLMClient("deepseek")
    a = await llm.one(PROMPT_A)
    print("=== b 版·裸问 ===")
    print(a)

if __name__ == "__main__":
    asyncio.run(main())
