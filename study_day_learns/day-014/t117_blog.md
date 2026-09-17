# 从零踩坑：用 OpenAI SDK 调通 LLM 单次 / 流式 / 多轮对话

> 作者：叶梓皓 · 学习记录（2026-08-30）
> 适用：Python 初学者，想把大模型 API 真正跑通的人
> 环境：OpenAI 官方 SDK（兼容 Agnes AI 端点），FastAPI 项目

---

## 0. 为什么写这篇

学 LLM 应用开发，第一步不是背概念，是把 API **真跑通**。这篇记录我从「单次调用」→「流式输出」→「多轮上下文」→「封装成终端对话程序」的完整踩坑过程。所有代码都能直接跑。

核心教训一句话：**API key 绝不硬编码，子目录脚本加载 `.env` 有顺序讲究，流式用 `AsyncOpenAI` + `async for`，多轮靠客户端维护历史。**

---

## 1. 环境准备：key 不进代码

API key 一旦硬编码进 `.py` 推到 GitHub，就会被机器人扫走盗刷。正确做法：放 `.env`，加进 `.gitignore`，代码里读环境变量。

```python
# study_day_learns/t109_q1_sync_chat.py
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent   # 项目根目录
load_dotenv(ROOT / ".env")                       # ← 必须先加载

from config import settings                       # ← 再 import settings
from openai import OpenAI

client = OpenAI(
    api_key=settings.agnes_api_key,
    base_url=settings.agnes_base_url,
)
```

⚠️ **致命顺序坑**：`config.py` 里 `settings = Settings()` 在 **import 那一刻就读取环境变量**。如果 `from config import settings` 写在 `load_dotenv` 前面，`settings` 已经把空值固化，后面再加载 `.env` 也来不及 → 运行时报 `Missing credentials`。

---

## 2. 单次调用：拿到完整回复

```python
def once_request(prompt: str) -> str:
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model=settings.agnes_model,   # model 是请求参数，不是 client 参数
        messages=messages,
    )
    return response.choices[0].message.content
```

- `model` 在**发请求时**传，不在 client 初始化时；
- 回复在 `response.choices[0].message.content`，一次性取全文。

---

## 3. 流式调用：打字机效果

流式要长时间保持连接、持续收数据。同步客户端等数据时会把线程卡死，所以用 `AsyncOpenAI`：

```python
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=settings.agnes_api_key, base_url=settings.agnes_base_url)

async def stream_request(prompt: str):
    messages = [{"role": "user", "content": prompt}]
    stream = await client.chat.completions.create(
        model=settings.agnes_model,
        messages=messages,
        stream=True,                 # ← 关键：返回流对象，不是完整响应
    )
    async with stream:
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""   # ← delta 是增量
            print(delta, end="", flush=True)
```

**单次 vs 流式对比：**

| | 单次 | 流式 |
|---|---|---|
| 客户端 | `OpenAI` | `AsyncOpenAI` |
| 返回 | `ChatCompletion` 完整对象 | `AsyncStream` 流对象 |
| 取文本 | `resp.choices[0].message.content` | `chunk.choices[0].delta.content` |
| 迭代 | 直接取 | `async for` |

- `delta` = 增量（Δ），每个 chunk 只带一小段新文本，完整回复 = 所有 `delta` 拼起来；
- 末尾 chunk 的 `delta` 常为 `None`，故写 `or ""` 兜底。

⚠️ **一个无害的报错**：独立脚本跑流式时，结尾可能出现
`RuntimeError: generator didn't stop after athrow()`。这是 httpx 0.28 + OpenAI SDK 异步流收尾的已知兼容噪音，**不在你的业务代码里**（发生在 `asyncio.run()` 清理连接池时），模型回复已正常打印、`exit code 0` 即功能正常。忽略即可。

---

## 4. 多轮上下文：LLM 是无状态的

三种角色：
- `system` = 人设/指令（"你是一个友好的中文助手"）
- `user` = 提问者（你）
- `assistant` = 模型回复（它）

**关键认知**：LLM 服务端不记得上一轮，每轮请求独立。必须靠**客户端把历史拼进 messages 传过去**：

```python
messages = [
    {"role": "system", "content": "你是一个友好的中文助手"},
    {"role": "user", "content": "我叫叶梓皓，记住了"},
    {"role": "assistant", "content": "好的我记住了"},   # 第一轮模型回复追加进来
    {"role": "user", "content": "我叫什么名字？"},        # 第二轮才能答出"叶梓皓"
]
```

去掉历史 `assistant`，模型就"失忆"。

---

## 5. 封装 + 终端对话程序

把"调 API"封装成纯函数，REPL 循环单独写：

```python
def chat(messages: list) -> str:
    try:
        resp = client.chat.completions.create(
            model=settings.agnes_model,
            messages=messages,        # ← 用传入的，别在函数内自建列表
        )
        return resp.choices[0].message.content
    except Exception as e:           # ← 至少 Exception，别裸 except:
        print(f"API 调用失败: {e}")
        return "网络错误，请稍后重试"

def main():
    messages = [{"role": "system", "content": "你是一个友好的中文助手"}]
    while True:
        user_text = input("你> ")
        if user_text in ("exit", "quit"):
            break
        messages.append({"role": "user", "content": user_text})
        reply = chat(messages)
        print("AI>", reply)
        messages.append({"role": "assistant", "content": reply})

if __name__ == "__main__":
    main()
```

⚠️ **高频坑**：`chat` 函数别自己新建 `message` 列表——那样会忽略传入的历史，多轮直接失效。`messages.append` 元素间逗号别漏，`role` 字段写 `"role":"user"` 不是 `"user"`。

---

## 6. 踩坑清单（背下来）

1. `load_dotenv` 必须在 `from config import settings` 之前（子目录脚本读根 `.env`）
2. `user`=提问者，`assistant`=模型回复，别反
3. `model` 是请求参数，非 client 初始化参数
4. 流式：`AsyncOpenAI` + `stream=True` + `await create` + `async for` + `delta.content` + `or ""`
5. 末尾 `RuntimeError(athrow)` 是环境噪音，非代码错，忽略
6. `messages` 元素间逗号别漏，`role` 字段名写全
7. 别裸 `except:`，用 `except Exception as e:`

---

## 7. 下一步

这套跑通后，可进阶：把终端程序改成 Web 接口（FastAPI + SSE 流式，加 JWT 鉴权 + slowapi 限流），就是面试能讲的完整项目。
