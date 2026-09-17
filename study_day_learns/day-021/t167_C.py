import sys,json,asyncio
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/".env")
from llm_service import LLMClient

TEXT = "张三，男，1998年出生，住在重庆市渝北区，职业是软件工程师。"

PROMPT_C ="""从下面这段话里提取个人信息，只输出 JSON。

字段要求：
- name: 姓名，字符串
- gender: 性别，字符串
- birth_year: 出生年份，整数（不要带"年"字）
- city: 所在城市，字符串
- job: 职业，字符串

输出示例：
{"name": "张三", "gender": "男", "birth_year": 1998, "city": "重庆市", "job": "软件工程师"}

规则：
1. 只输出 JSON 本身，不要任何解释文字
2. 不要用 ```json 代码块包裹
3. 键名必须严格按上面的英文写

文本："""+ TEXT

async def main():
    llm = LLMClient("deepseek")
    a = await llm.one(PROMPT_C)
    print("=== C 版·强制 JSON ===")  # 标签改成 C（现在写的是 b 版·裸问）
    print(a)
    try:
        print("✅ 解析成功:", json.loads(a))
    except json.JSONDecodeError as e:
        print("❌ 解析失败:", e)


if __name__ == "__main__":
    asyncio.run(main())
