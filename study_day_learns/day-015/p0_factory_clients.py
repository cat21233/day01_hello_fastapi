# p0_factory_clients.py
# 任务 2 目标：工厂模式切换多个 OpenAI 兼容厂商
# 用同步 OpenAI 即可（任务 1 已经演示过 async 流式，这里只验切换）
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from config import settings
from openai import OpenAI

# 厂商注册表：新增厂商只改这里，加一行即可（工厂模式核心收益）
CLIENTS = {
    "agnes": {
        "api_key": settings.agnes_api_key,
        "base_url": settings.agnes_base_url,
    },
    "deepseek": {
        "api_key": settings.deepseek_api_key,
        "base_url": settings.deepseek_base_url,
    },
}


def get_client(name: str) -> OpenAI:
    """按名字返回对应厂商的 OpenAI 兼容客户端（未注册的名字直接 KeyError）"""
    return OpenAI(**CLIENTS[name])


def chat_once(name: str, prompt: str) -> str:
    """对指定厂商发一次非流式请求，返回模型回复"""
    cfg = CLIENTS[name]
    client = OpenAI(**cfg)
    resp = client.chat.completions.create(
        model=settings.agnes_model if name == "agnes" else settings.deepseek_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    print("=== 工厂结构验证（每个厂商打印 client 类型）===")
    for name in CLIENTS:
        c = get_client(name)
        print(f"  {name:>8s} -> {type(c).__name__}  base_url={CLIENTS[name]['base_url']}")

    print("\n=== 真实调通（每个厂商各发一次）===")
    for name in CLIENTS:
        try:
            reply = chat_once(name, "用一句话介绍你自己")
            print(f"  {name:>8s} -> {reply}")
        except Exception as e:
            print(f"  {name:>8s} -> ❌ {type(e).__name__}: {str(e)[:120]}")
