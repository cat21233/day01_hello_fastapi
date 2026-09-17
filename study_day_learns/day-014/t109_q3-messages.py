from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
from config import settings
from openai import OpenAI
client = OpenAI(
    api_key=settings.agnes_api_key,
    base_url=settings.agnes_base_url
)
def multi_turn_chat():
    messages = [{"role": "system", "content": "你是一个中文助手"},
                {"role": "user", "content": "我叫叶梓皓,记住了"},


                ]
    response1 = client.chat.completions.create(
        model=settings.agnes_model,
        messages=messages
    )
    reply1 = response1.choices[0].message.content
    print("第一轮回复",reply1)
    messages.append({"role": "assistant", "content": "好的,我记住了"})
    messages.append({"role": "user", "content": "我叫什么名字?"})
    response2 = client.chat.completions.create(
        model=settings.agnes_model,
        messages=messages
    )
    reply2 = response2.choices[0].message.content
    print("第二轮回复:", reply2)
if __name__ == '__main__':
    multi_turn_chat()