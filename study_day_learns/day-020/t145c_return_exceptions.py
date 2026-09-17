# t145c：gather 的部分失败容错（return_exceptions 参数）
# 衔接 t-145 复盘第 1 题：你当时答「只丢第三个」是错的——默认是整批崩。
# 本脚本用纯本地 coroutine 演示（不依赖网络），看清两种行为的差异。
import sys
from pathlib import Path

# 把项目根加进 sys.path，才能 import common.*（记忆库坑#12：必须在 import 前）
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import asyncio

from common.llm_client import chat_many  # 仅验证封装可被导入 + 真实用法示例


async def ok(i: int) -> str:
    """模拟一个成功的 LLM 调用。"""
    await asyncio.sleep(0.1)
    return f"结果{i}"


async def bad() -> str:
    """模拟一个永久失败的 LLM 调用（重试 5 次也救不回）。"""
    await asyncio.sleep(0.1)
    raise ValueError("这个 prompt 永久失败（如触发网关永久错误）")


async def demo_default() -> None:
    print("=== 默认 return_exceptions=False：任一失败 → 整批崩 ===")
    try:
        # 默认行为：有一个协程抛异常，gather 立即取消其余并抛出
        await asyncio.gather(ok(1), bad(), ok(2))
    except Exception as e:
        print(f"  捕获: {type(e).__name__}: {e}")
        print("  → ok(1) / ok(2) 明明成功了，结果也拿不到（全废）")


async def demo_tolerant() -> None:
    print("\n=== return_exceptions=True：失败降级为结果元素，其余照常 ===")
    # 加 return_exceptions=True：失败的协程不再抛异常，而是把 Exception 对象放进结果列表
    results = await asyncio.gather(ok(1), bad(), ok(2), return_exceptions=True)
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"  位置{i}: 失败 → {type(r).__name__}: {r}")
        else:
            print(f"  位置{i}: 成功 → {r}")


async def main() -> None:
    await demo_default()
    await demo_tolerant()

    print("\n=== 真实封装 chat_many 怎么用 ===")
    print("  # 部分失败也不拖垮整批：")
    print("  results = await chat_many(prompts, return_exceptions=True)")
    print("  for i, r in enumerate(results):")
    print("      if isinstance(r, Exception):  # 失败项单独告警/重试")
    print("          log_error(prompts[i], r)")
    print("      else:                         # 成功项正常消费")
    print("          consume(r)")


if __name__ == "__main__":
    asyncio.run(main())
