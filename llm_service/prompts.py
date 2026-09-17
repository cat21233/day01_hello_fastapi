"""
llm_service/prompts.py —— system prompt 注册表

为什么需要它？
  之前 system prompt 是散落在各处的字符串，改一句要翻遍代码。
  集中成一个「名字 → 文本」的注册表后：
    · 动态选择：运行时按名字挑 prompt（A/B 测试、按场景切换角色）
    · 预览：/prompts 接口直接看当前有哪些、长什么样，不用查源码

这是 t-235「Prompt 管理路由：动态选择/预览 system prompt」的数据层。
路由层（routers/prompts.py）只负责把这里的东西暴露成 HTTP 接口。
"""


# 名字 → system prompt 文本。加一个角色 = 在这里加一行，其余代码零改动。
_PROMPTS: dict[str, str] = {
    "default": "你是一个乐于助人的中文助手。",
    "concise": "你是一个简洁的助手，回答不超过三句话。",
    "code_reviewer": "你是一位严谨的代码审查者，只指出问题并给出修改建议，不要重写整段代码。",
}


def list_prompts() -> list[str]:
    """返回所有已注册的 prompt 名字。"""
    return list(_PROMPTS.keys())


def get_prompt(name: str) -> str:
    """按名字取 prompt 文本。名字不存在时抛 KeyError 并列出可用的。"""
    if name not in _PROMPTS:
        raise KeyError(f"未知 prompt：{name!r}，可用：{list(_PROMPTS.keys())}")
    return _PROMPTS[name]


def register_prompt(name: str, text: str) -> None:
    """运行时新增/覆盖一个 prompt（测试或热更新用）。"""
    _PROMPTS[name] = text
