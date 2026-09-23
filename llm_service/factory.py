# llm_service/factory.py —— 厂商工厂：一个名字换一个 client
#
# 为什么需要工厂？
#   上层业务（路由 / Agent / 实验脚本）不应该 import openai，也不该知道
#   base_url / model 这些细节。它只需要说「我要 deepseek」，拿到一个能干活的 client。
#
# 为什么带缓存？
#   AsyncOpenAI 内部持有 httpx 连接池（keep-alive）。每次调用都 new 一个 →
#   每个请求各开一个池，并发时连接数暴涨。同 (provider, key) 只应建一次。
from openai import AsyncOpenAI

from config import settings

# 厂商名 → (api_key, base_url) 的映射表。
# 加一家新厂商 = 在这里加一行，其余代码零改动。
def _providers() -> dict[str,tuple[str,str]] :
    table:dict[str,tuple[str,str]] = {
        "agnes": (settings.agnes_api_key,settings.agnes_base_url),
        "deepseek": (settings.deepseek_api_key, settings.deepseek_base_url),
        "zhipu":(settings.zhipu_api_key,settings.zhipu_base_url)
    }
    return {k: v for k,v in table.items() if v[0].strip()}
# 客户端缓存：{(provider, api_key): client}
_cache: dict[tuple[str, str], AsyncOpenAI] = {}


def get_client(provider: str = "deepseek") -> AsyncOpenAI:
    """按厂商名拿一个（复用的）异步 client。

    provider 不认识时抛 ValueError 并列出可用项 —— 快速失败优于静默用错厂商。
    """
    providers = _providers()
    if provider not in providers:
        raise ValueError(
            f"未知厂商：{provider!r}，可用：{list(providers.keys())}"
        )

    api_key, base_url = providers[provider]
    cache_key = (provider, api_key)

    if cache_key not in _cache:
        _cache[cache_key] = AsyncOpenAI(api_key=api_key, base_url=base_url)

    return _cache[cache_key]


def get_model(provider: str = "deepseek") -> str:
    """模型名也跟着厂商走，避免上层写死 'deepseek-chat'。"""
    models = {
        "agnes": settings.agnes_model,
        "deepseek": settings.deepseek_model,
        "zhipu":settings.zhipu_model
    }
    if provider not in models:
        raise ValueError(f"未知厂商：{provider!r}")
    return models[provider]
