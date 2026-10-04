import time
from llm_service import registry
from llm_service.tool_calling import TOOLS, REGISTRY, run_tool_loop
import asyncio
from types import SimpleNamespace
def test_get_weather_contains_city_and_temp():
    result = registry.get_weather("北京")
    assert "北京" in result
    assert "28" in result

def test_get_time_contains_city_and_today():
    result = registry.get_time("上海")
    today = time.strftime("%Y-%m-%d")
    assert "上海" in result
    assert today in result          # 判据 2：今天的日期要出现（用 today，别写死）
def test_tool_names_all_registered():
    declared = {t["function"]["name"] for t in TOOLS}
    assert declared == set(REGISTRY)

# 测试3 ：打桩client,测完整闭环
def test_run_tool_returns_final_answer():
    calls = []
    async def fake_create(**kwarg):
        calls.append(1)
        messages = kwarg["messages"]
        if len(calls) == 1:
            fn = SimpleNamespace(
                name="get_weather",
                arguments='{"city": "北京"}'
            )
            tc = SimpleNamespace(id="call_1", function=fn)
            msg = SimpleNamespace(tool_calls=[tc], content="")
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        outs = [
            m["content"] for m in messages
            if isinstance(m,dict) and m.get("role") == "tool"
        ]
        msg = SimpleNamespace(
            tool_calls=None,
            content="已查到：" + " / ".join(outs)  # ← 回答由真实工具结果拼出来
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=fake_create)
        )
    )

    result = asyncio.run(run_tool_loop("北京天气",client=client))
    assert result.startswith("已查到：")
    assert "北京" in result
    assert "28" in result
    assert len(calls) == 2