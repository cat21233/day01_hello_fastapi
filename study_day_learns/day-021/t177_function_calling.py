# study_day_learns/day-021/t177_function_calling.py
# t-177 Function Calling 初识：模型只输出「调用意图」，执行在你手里
# 目标：跑完能看到 ① tool_calls 列表 ② content 是 None ③ 最终自然语言答案

import sys
import json
import asyncio
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from openai import AsyncOpenAI
from config import settings

client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)

# ================= 机械部分（已写好，读懂即可）=================
# 工具说明书：告诉模型「有这么个工具、叫什么、要什么参数」
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 重庆"},
                },
                "required": ["city"],
            },
        },
    }
]


def get_weather(city: str) -> dict:
    """真实的函数实现（这里是假的，真项目里会去调天气 API）"""
    fake_db = {
        "重庆": {"temp": 28, "desc": "晴"},
        "北京": {"temp": 19, "desc": "多云"},
    }
    return fake_db.get(city, {"temp": 25, "desc": "未知"})


async def ask(messages: list):
    """发一次请求，返回整个 message 对象（注意：不是 content，因为要拿 tool_calls）"""
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        tools=TOOLS,
        temperature=0,
    )
    return resp.choices[0].message


# ================= 你的部分（4 个 TODO）=================
async def run():
    messages = [{"role": "user", "content": "重庆今天天气怎么样？"}]

    # ---------- 第一次请求：看模型给不给 tool_calls ----------
    msg1 = await ask(messages)
    print("① tool_calls =", msg1.tool_calls)
    print("① content    =", msg1.content)  # 预期是 None —— 模型没打算自己回答

    # ⬜ TODO 1：把第一个调用拆出来
    # 词典：
    #   msg1.tool_calls          → 列表，取第一个用 [0]
    #   call.id                  → 这次调用的唯一编号（回传结果时要对上）
    #   call.function.name       → "get_weather"（字符串）
    #   call.function.arguments  → ⚠️ 是 JSON 字符串，不是字典！要 json.loads() 转
    call = msg1.tool_calls[0]                    # 列表取第一个
    name = call.function.name                    # "get_weather"
    args = json.loads(call.function.arguments)   # ⚠️ JSON 字符串 → 字典

    print("② 函数名 =", name, "参数 =", args)

    # ---------- TODO 2：按函数名分发到真函数 ----------
    if name == "get_weather":
        result = get_weather(args["city"])
    else:
        result = {"error": f"未知工具：{name}"}

    print("③ 本地执行结果 =", result)

    # ---------- TODO 3：把这一轮追加进 messages（顺序不能反）----------
    messages.append(msg1)                        # 3a. 模型那条 assistant 消息原样塞回
    messages.append({                            # 3b. tool 结果消息
        "role": "tool",
        "tool_call_id": call.id,                 # ⚠️ 必须对上编号，不是函数名
        "content": json.dumps(result, ensure_ascii=False),
    })

    # ---------- TODO 4：第二次请求 ----------
    msg2 = await ask(messages)
    print("④ 最终回答 =", msg2.content)


if __name__ == "__main__":
    asyncio.run(run())
