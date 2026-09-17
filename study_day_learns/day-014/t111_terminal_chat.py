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
def chat(messages:list)->str:
    try:

        resp = client.chat.completions.create(
                model=settings.agnes_model,
                messages=messages)
        return resp.choices[0].message.content

    except Exception as e:
        print(f"API 调用失败:{e}")
        return "网络错误,请稍后重试"
def main():
    messages=[{"role":"system","content":"你是一个友好的中文助手"}]
    while True:
        user_text = input("你> ")
        if user_text in ("exit","quit"):
            break
        messages.append({"role": "user", "content":user_text})
        reply = chat(messages)
        print("AI>",reply)
        messages.append({"role":"assistant","content":reply})
if __name__ == '__main__':
    main()