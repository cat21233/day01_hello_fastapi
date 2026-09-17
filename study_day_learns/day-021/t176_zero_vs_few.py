import sys
from dotenv import load_dotenv
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/".env")
from openai import AsyncOpenAI
from config import settings
import asyncio
client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url
)
async def ai_chat(prompt:str):

    messages = [{"role": "user","content": prompt}]
    resp = await client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=0
    )
    return resp.choices[0].message.content.strip()
async def run():
    TASK = """你是客服消息分类器。把用户消息分到以下三类之一：
- 技术咨询：用户在问技术问题、怎么配置、怎么使用
- 闲聊：打招呼、无关话题
- 投诉：表达不满、追责、要求解决问题

只输出标签本身（技术咨询/闲聊/投诉之一），不要任何解释。
"""
    EXAMPLES = """用户消息：FastAPI 里 Depends 和 Query 有啥区别
分类：技术咨询

用户消息：你是谁
分类：闲聊

用户消息：你们接口又 500 了到底什么时候修好
分类：投诉

"""
    TEST_MSG = "你们接口文档里那个超时参数到底怎么配啊，配了三次都报错"
    TEST_MSGS = [
        "你们接口文档里那个超时参数到底怎么配啊，配了三次都报错",  # 原：情绪+技术
        "又报错了，我真的会谢，这破库文档也看不懂，浪费一下午",  # 加：情绪更浓
        "气死我了，付了钱功能用不了，再不解决就退款",  # 加：纯投诉（对照组）
    ]
    for msg in  TEST_MSGS:
        zero = await ai_chat(TASK + "用户消息：" + msg)
        few = await ai_chat(TASK + EXAMPLES + "用户消息：" + msg)
        print("Zero-shot 分类:", zero)
        print("Few-shot  分类:", few)



if __name__ == '__main__':
   asyncio.run(run())
