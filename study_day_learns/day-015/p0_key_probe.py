# p0_key_probe.py
# 用途：验证同一个 key 在 agnes / deepseek 两个 base_url 上是否都有效
# 用法：python study_day_learns/p0_key_probe.py
# 输出自动给出诊断结论（401 来源：key 无效 vs 不能跨模型）
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from config import settings
from openai import OpenAI


def probe(name: str, api_key: str, base_url: str, model: str) -> bool:
    print(f"--- 探针: {name} ---")
    print(f"  base_url: {base_url}")
    print(f"  model   : {model}")
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        print(f"  ✅ 成功: {resp.choices[0].message.content!r}")
        return True
    except Exception as e:
        print(f"  ❌ 失败: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    key = settings.deepseek_api_key  # 拿 .env 里 DEEPSEEK_API_KEY 的值
    print(f"使用 key（长度 {len(key)}）分别探测两条路径:\n")
    ok_agnes = probe("agnes 路径", key, settings.agnes_base_url, settings.agnes_model)
    ok_ds = probe("deepseek 路径", key, settings.deepseek_base_url, settings.deepseek_model)

    print("\n===== 结论 =====")
    if ok_agnes and ok_ds:
        print("两个路径都通 → key 通用，之前 401 是别的 bug，回来复查脚本")
    elif ok_agnes and not ok_ds:
        print("agnes 通、deepseek 401 → key 不能跨模型访问 deepseek；")
        print("  去 Agnes 控制台给 deepseek 模型生成专用 key，或换一个真正有 deepseek 权限的 key")
    elif not ok_agnes and ok_ds:
        print("deepseek 通、agnes 401 → 意外情况，检查 config.py 的 agnes base_url 拼写")
    else:
        print("两条都不通 → key 本身无效或 .env 复制漏了字符，重新核对 key")
