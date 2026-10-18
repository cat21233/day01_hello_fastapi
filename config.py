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
    # ── RAG 存储 ──────────────────────────────
    # 路径都是「相对项目根目录」，rag_store.py 里拼 ROOT 后使用。
    # 放在 config 里是为了容器部署时能换（t-032 的 Dockerfile 里挂载点不同）。
    chroma_dir: str = ".chroma_probe"
    rag_collection: str = "day020"
    rag_vec_file: str = "study_day_learns/day-020/split_embeddings.json"

    # ── 关系数据库（业务数据）──────────────────────
    # 换库只改 .env 的 DATABASE_URL，代码一个字不动。
    # 本地开发：SQLite 文件（零配置，文件就落在项目根）
    # 真实数据库（本机 phpstudy MySQL）：
    #   DATABASE_URL=mysql+pymysql://root:密码@127.0.0.1:3306/day01?charset=utf8mb4
    # 注意 charset=utf8mb4：utf8 在 MySQL 里只有 3 字节，存 emoji 会直接报错
    database_url: str = "sqlite:///./app.db"
    # 调试用：把每条 SQL 打到控制台（.env 里 DATABASE_ECHO=true 打开）
    database_echo: bool = False
    # 启动时是否自动插入演示账号（生产环境务必 false）
    db_auto_seed: bool = True
    # 改后
    llm_provider: str = "deepseek"

    # ── JWT 签名密钥（秘密！只能来自 .env）────────────
    # 这个值是 token 的「印章」：拿到它就能自签任意用户名的 token。
    # 所以它属于秘密，不属于可调参数 —— 代码里故意不给可用默认值。
    # 生成方式：python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret_key: str = ""

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
    # 改后（新增这一段，原有两段检查保持不动）
    # ① 先查「印章」：它比 API key 更基础，缺了等于谁都能冒充谁。
    #    阈值 32 不是玄学：太短（如 "123456"）可以被离线暴力枚举出签名。
    if len(settings.jwt_secret_key.strip()) < 32:
        raise ConfigError(
            "JWT_SECRET_KEY 缺失或太短（要求 ≥32 字符）。"
            '生成一个：python -c "import secrets; print(secrets.token_urlsafe(48))"'
            "，然后写进项目根的 .env：JWT_SECRET_KEY=<生成的值>"
        )

    providers = configured_providers()

    if not providers:
        raise ConfigError("一个厂商都没有配去.env里面补")

    if settings.llm_provider not in providers:
        raise ConfigError(f"当前厂商 {settings.llm_provider} 没有配置 API key，请在 .env 里补上")


