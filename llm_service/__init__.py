# llm_service/__init__.py
# 对外只暴露必要的东西：上层写 `from llm_service import LLMClient`，
# 不需要知道 factory / client 这些内部文件名。这叫「收窄公开接口」——
# 以后重构内部结构，只要 __init__ 这几个名字不变，上层代码零改动。
from llm_service.client import LLMClient
from llm_service.factory import get_client, get_model
from llm_service.prompts import get_prompt, list_prompts, register_prompt

__all__ = ["LLMClient", "get_client", "get_model", "get_prompt", "list_prompts", "register_prompt"]
