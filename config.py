from pathlib import Path

import openai
from pydantic_settings import BaseSettings, SettingsConfigDict
class ConfigError(Exception):
    """配置不完整/不合法时抛出。启动即失败（fail-fast），别等跑起来才炸。"""


class Settings(BaseSettings):
    app_name: str = "我的FastAPI项目"
    port: int = 8000
    debug: bool = False
    agnes_api_key: str = ""
    agnes_base_url: str = "https://apihub.agnes-ai.com/v1"
    agnes_model: str = "agnes-2.0-flash"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = "glm-4.7-flash"
    # 当前默认厂商：LLMClient 用哪家由这里决定，换厂商只改 .env，不动代码。
    # （agnes 免费额度容易打满，429 时切 deepseek 即可）
    llm_provider: str = "deepseek"



    # .env 路径固定为 config.py 同级（项目根），不再依赖 cwd。
    # 修前：env_file=".env"（cwd 相对，PyCharm 跑脚本 cwd=脚本目录→找不到）
    # 修后：env_file=<config.py 同级的 .env>（任何 cwd 下都能找到）
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent / ".env")
    )
settings = Settings()


# ============ t-236：启动配置校验（fail-fast） ============
# 这些函数不依赖任何 LLM 调用，纯读 settings，启动阶段就能跑。
# 目的：.env 漏配 api_key 时，服务一起动就报错退出，而不是在第一次调 LLM 时才 401。
def configured_providers() -> list[str]:
    """返回所有在 .env 里填了 api_key 的厂商名。"""
    providers = {
        "agnes": settings.agnes_api_key,
        "deepseek": settings.deepseek_api_key,
        "zhipu": settings.zhipu_api_key,
    }
    return [name for name, key in providers.items() if key.strip()]


def validate_settings() -> None:
    """启动时校验必需配置，缺一项就 raise ConfigError。

    校验规则（✍️ 闭卷题，你来补全 TODO）：
      1. 当前选中的 llm_provider 必须真的配了 key（否则一起步就会 401）
      2. 至少得有一个厂商配了 key（否则整个 LLM 功能等于废了）
    失败时抛出的 ConfigError 信息要写清楚「缺了什么、怎么补」。
    """
    providers = configured_providers()
    if not providers:
        raise ConfigError("一个厂商都没有配去.env里面补")

    if settings.llm_provider not in providers:
        raise ConfigError(f"当前厂商 {settings.llm_provider} 没有配置 API key，请在 .env 里补上")


