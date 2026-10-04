import json
from collections.abc import Callable

from llm_service import registry
from llm_service.factory import get_client, get_model
TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定城市的实时天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"},
            },
            "required": ["city"],
        },
    },
},
{
    "type":"function",
    "function": {
        "name": "get_time",
        "description": "查询指定城市的当前时间。参数 city 是城市名",
        "parameters":{
            "type": "object",
            "properties":{
                "city": {
                    "type": "string",
                    "description": "城市名，例如北京"
                }
            },
            "required": ["city"]
        }
    }

}
]
REGISTRY: dict[str, Callable] = {
    "get_weather": registry.get_weather,
    "get_time": registry.get_time
}
async def call_one_tool(client, model, messages) -> bool:
    """跑一轮。True = 模型要调工具（已执行+回传）；False = 模型给最终答案了"""
    resp = await client.chat.completions.create(
        model=model, messages=messages, tools=TOOLS
    )
    msg = resp.choices[0].message
    messages.append(msg)
    if not msg.tool_calls:                 # 情况1：模型没要工具 → 告诉外层"停"
        return False

    for tc in msg.tool_calls:              # 情况2：逐个执行
        try:
            args = json.loads(tc.function.arguments)
            fn = REGISTRY[tc.function.name]
            result = fn(**args)
        except Exception as e:
            result = f"工具执行失败:{e}"
        messages.append({
            "role": "tool",
            "content": result,
            "tool_call_id": tc.id
        })
    return True                           # 告诉外层"再来一圈"


async def run_tool_loop(user_input: str, max_turns: int = 5, client=None, model: str | None = None) -> str:
    """完整 while 循环，返回模型的最终回答

    client / model 不传就用真 client（生产）；测试传假 client 打桩。
    """
    if client is None:
        client = get_client()
    if model is None:
        model = get_model()
    messages = [{"role": "user", "content": user_input}]
    for turn in range(max_turns):
        has_tool = await call_one_tool(client=client, model=model, messages=messages)
        if not has_tool:
            return messages[-1].content
    return "(已达到最大轮数，仍未得出结论)"
