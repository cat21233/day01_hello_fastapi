# t-110 费曼输出：LLM API 调用与流式核心

> 用自己的话讲清 OpenAI SDK（Agnes 兼容端点）的四块核心：单次调用 / 流式调用 / 多轮上下文 / 封装函数。
> 兼作 t-117 技术博客素材。

---

## ① 单次调用（sync）

**是什么**：模型一次性生成完整回复，存在响应对象里，直接取全文。

**关键写法**：
```python
from openai import OpenAI
client = OpenAI(api_key=..., base_url=...)          # 只传 密钥 + 端点
resp = client.chat.completions.create(
    model=settings.agnes_model,                      # ① 用哪个模型（请求参数，不是 client 参数）
    messages=[{"role": "user", "content": prompt}],  # ② 对话内容
)
text = resp.choices[0].message.content               # 完整回复路径
```

**踩坑（讲错被纠正）**：
- ❌ 把 `model` 当 client 初始化参数 → 错，`model` 是发请求时才传的。
- ❌ 把 `create(...)` 方法名当成"请求参数" → 实际核心字段是 `model` + `messages`。
- ⚠️ `.env` 加载顺序：子目录脚本必须 `load_dotenv(ROOT/".env")` 写在 `from config import settings` **之前**，否则 `settings` 在 import 那一刻已把空值固化，运行时报 missing credentials（题1、题3 都栽过）。

---

## ② 流式调用（async）

**是什么**：模型边生成边推，打字机效果。

**关键写法**：
```python
from openai import AsyncOpenAI                       # ← 异步客户端
client = AsyncOpenAI(api_key=..., base_url=...)

stream = await client.chat.completions.create(model=..., messages=..., stream=True)
async with stream:
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""  # ← 增量，不是 message
        print(delta, end="")
```

**对比单次（讲清差异）**：
| | 单次 | 流式 |
|---|---|---|
| 客户端 | `OpenAI` | `AsyncOpenAI` |
| 返回 | `ChatCompletion` 完整对象 | `AsyncStream` 流对象（异步迭代器） |
| 取文本 | `resp.choices[0].message.content` | `chunk.choices[0].delta.content` |
| 迭代 | 直接取 | `async for` |

- **为什么 AsyncOpenAI**：流式要长时间保持连接、持续收数据；同步客户端等数据时会把线程卡死。
- **为什么 `async for`**：数据分批到、非一次性，每次迭代让出控制权回事件循环，不卡别人。
- **`delta` vs `message`**：`message`=整条；`delta`=增量（Δ），每个 chunk 只带一小段新文本，完整回复=所有 `delta` 拼起来。末尾 chunk 的 `delta` 常为 `None`，故写 `or ""`。
- ⚠️ **`RuntimeError: generator didn't stop after athrow()`**：httpx 0.28 + OpenAI SDK 异步流收尾的**已知兼容噪音**，**不是业务代码错误**（发生在 `asyncio.run()` 清理连接池时，不在你的调用栈，try/except 抓不到）。模型回复已正常打印、`exit code 0` 即功能正常，忽略即可。D12 的 `llm.py` 因被 `StreamingResponse` 包着吞了异常才没暴露。

---

## ③ 多轮上下文（messages 数组）

**角色**：
- `system` = 设定人设/指令（"你是一个简洁的中文助手"）
- `user` = **用户/提问方**（你）
- `assistant` = **模型/AI 回复方**（它）

⚠️ 讲错被纠正：user 是提问者、assistant 是模型回复，别记反。

**为什么能"记住"**：LLM 是**无状态**的，服务端不保留记忆，每轮请求独立。必须靠**客户端把历史拼进 messages 传过去**：
```python
messages = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "我叫叶梓皓，记住了"},
    {"role": "assistant", "content": "好的我记住了"},   # 第一轮模型回复追加进来
    {"role": "user", "content": "我叫什么名字？"},        # 第二轮才能答出"叶梓皓"
]
```
去掉历史 `assistant`，模型就没历史可看，记不住。

---

## ④ 封装最简 chat 函数

**三件事**：①准备 messages（含 system 人设 + user prompt）②调 API 取回复 ③异常兜底返回兜底文字。
```python
def chat(prompt: str) -> str:
    messages = [
        {"role": "system", "content": "你是一个简洁的中文助手，回答不能超过30个字"},
        {"role": "user", "content": prompt},
    ]
    try:
        resp = client.chat.completions.create(model=settings.agnes_model, messages=messages)
        return resp.choices[0].message.content
    except Exception as e:                  # ← 至少 Exception，别裸 except
        print(f"API 调用失败: {e}")
        return "网络错误，请稍后重试"
```

**踩坑（讲错被纠正）**：
- ❌ 裸 `except:` 最糟——会连自己代码的 bug（NameError/TypeError）一起吞掉，还捕获 Ctrl+C 退出信号，调试时找不到错。至少写 `except Exception as e:`，更好精确捕获 `openai.OpenAIError`。
- ❌ 把交互式 `while True` + `input()` 塞进 chat 函数 → chat 应是纯函数（传 prompt 返字符串），REPL 循环单独写（t-111 终端对话程序）。
- ⚠️ `messages` 列表元素间**缺逗号**、`role` 字段写成 `"user"`（应为 `"role":"user"`）是今天高频粗心点，写时先脑子里过结构。

---

## 防坑清单（今日复发）
1. `load_dotenv` 必须在 `from config import settings` 之前（子目录脚本读根 `.env`）。
2. `user`=提问者，`assistant`=模型回复，别反。
3. `model` 是请求参数，非 client 初始化参数。
4. 流式：`AsyncOpenAI` + `stream=True` + `await create` + `async for` + `delta.content` + `or ""`。
5. 末尾 `RuntimeError(athrow)` 是环境噪音，非代码错，忽略。
6. `messages` 元素间逗号别漏，`role` 字段名写全。
7. 别裸 `except:`，用 `except Exception as e:`。
