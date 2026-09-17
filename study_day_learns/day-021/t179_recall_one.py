# t179_recall_one.py —— 闭卷默写 LLMClient.one()
#
# 【规则】不许打开 llm_service/client.py、也不许翻任何旧脚本
# 【目标】凭记忆写出 one() 的完整实现（约 5 行）
#
# 【过关标准 · 5 个点】
#   ① retry 装饰器贴在函数上方，三参数：
#        wait  = 指数退避
#        stop  = 最多 3 次
#        reraise = True
#   ② 函数签名：async def one(self, prompt: str) -> str
#   ③ messages 是「字典列表」，role 用哪个自己判断
#   ④ await 发起请求，三个参数：model / messages / temperature
#   ⑤ 返回时要把内容取出来，并去掉首尾空白
#
# 卡住了就在注释里写「卡在第 X 步 + 你的疑问」，直接问我，别硬猜。

import sys, asyncio
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from tenacity import retry, wait_exponential, stop_after_attempt,retry_if_exception_type
from llm_service.factory import get_client, get_model
from openai import APIConnectionError,APITimeoutError,RateLimitError


class MyClient:
    """简化版的 LLMClient，只为默写 one()。"""

    def __init__(self, provider: str = "deepseek", temperature: float = 0.0):
        self.provider = provider
        self.temperature = temperature
        self._client = get_client(provider)   # 从工厂拿，复用连接池
        self._model = get_model(provider)     # 模型名跟厂商走

    # ⬇⬇⬇ 你的部分：在下面写 one() ⬇⬇⬇
    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((APITimeoutError,APIConnectionError,RateLimitError)),
        reraise=True,
    )
    async def one(self, prompt: str) -> str:
        messages = [{"role":"user","content": prompt}]
        #    ① 构造 messages
        #    ② await 发起请求
        resp = await self._client.chat.completions.create(
            messages=messages,
            model=self._model,
            temperature=self.temperature

        )


        #    ③ return 取出内容 + 去空白
        return (resp.choices[0].message.content or "").strip()


    # ⬆⬆⬆ 你的部分结束 ⬆⬆⬆


async def main():
    c = MyClient("deepseek")
    print("回复 1:", await c.one("用一句话介绍你自己"))
    print("回复 2:", await c.one("1+1 等于几？只回数字"))


if __name__ == "__main__":
    asyncio.run(main())
