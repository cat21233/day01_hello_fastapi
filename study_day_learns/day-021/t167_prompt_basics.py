import sys, json, asyncio
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from llm_service import LLMClient

TEXT = "张三，男，1998年出生，住在重庆市渝北区，职业是软件工程师。"

# ============ 三版 Prompt：单变量 = 只改约束强度 ============

# A 版·裸问：零约束
PROMPT_A = f"从下面这段话里提取信息：\n{TEXT}"

# B 版·清晰指令：指定字段名 + 输出格式
PROMPT_B = (
    "从下面这段话里提取信息："
    "要求明确抽出姓名,性别,出生年份,住址,职业5个字段。"
    f"输出格式为字段:值\n{TEXT}"
)

# C 版·强制 JSON：字段清单（含类型）+ 输出示例 + 死规则
# 注意：用普通字符串 + 拼接，避免 f-string 的花括号与 JSON 冲突
PROMPT_C = """从下面这段话里提取个人信息，只输出 JSON。

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

文本：""" + TEXT


async def main():
    llm = LLMClient("deepseek")

    a = await llm.one(PROMPT_A)
    b = await llm.one(PROMPT_B)
    c = await llm.one(PROMPT_C)

    print("=== A 版·裸问 ===")
    print(a)
    print("\n=== B 版·清晰指令 ===")
    print(b)
    print("\n=== C 版·强制 JSON ===")
    print(c)

    # C 版关键验收：能不能被下游代码消费
    print("\n--- C 版可消费性验收 ---")
    try:
        data = json.loads(c)
        print("✅ json.loads 成功:", data)
        print("   birth_year 类型:", type(data["birth_year"]).__name__)
    except json.JSONDecodeError as e:
        print("❌ json.loads 失败:", e)


if __name__ == "__main__":
    asyncio.run(main())
