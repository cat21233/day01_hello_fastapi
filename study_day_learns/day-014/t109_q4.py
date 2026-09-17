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
def chat(prompt:str)-> str:
    messages = [{"role":"system", "content":"你是一个简洁的中文助手,回答不能超过30个字"},
                {"role":"user","content": prompt}],
    try:
        response = client.chat.completions.create(
            model=settings.agnes_model,
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"API 调用失败:{e}")
        return "网络错误,请稍后重试"

if __name__ == '__main__':
    print(chat("你好"))
    print(chat("今天的天气怎么样"))
    print(chat("认识孙景晨吗"))