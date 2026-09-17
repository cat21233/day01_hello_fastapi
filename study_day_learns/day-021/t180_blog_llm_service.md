# 我把 3 处散落的 LLM 调用收成了一个模块

学了十几天 FastAPI 调 LLM，每写一个新脚本都要抄同一段调用代码。换厂商时改了 3 处参数才反应过来：**参数必须传，和参数必须由我每次手写，是两件事**。于是把散落的调用收成了一个模块。

---

## 起因：同一个东西，我抄了三遍

我在学 FastAPI 调 LLM 的这十几天里，**几乎每写一个脚本，开头都要抄同一段代码**——不管是做流式输出、做 CoT 对比实验，还是做 Function Calling：

```python
client = AsyncOpenAI(api_key=settings.deepseek_api_key, base_url=..., )
resp = await client.chat.completions.create(model="deepseek-chat", messages=[...], temperature=0)
return resp.choices[0].message.content.strip()
```

抄的次数我自己都数不清了，**基本上每一次要做 LLM 流式输出，都要重新写一遍**。

真正让我意识到不对劲的是**换厂商**的时候。那次要把 agnes 换成 deepseek，需要改 **3 处**：模型名、base_url、API key。我一处没漏，全改对了——但改完之后我盯着屏幕想了一下：

> **这 3 个参数当然不能省，它们是调用的必需品。但它们凭什么每次都要我手写？**

参数必须传，和参数必须由我每次手写，**是两件事**。

后来 grep 了一下项目，证据摆出来更难看：

```bash
common/llm_client.py:17    client = AsyncOpenAI(api_key=settings.agnes_api_key, ...)
routers/llm.py:13          client = AsyncOpenAI(api_key=settings.agnes_api_key, ...)   # 重复第二份！
study_day_learns/...       client = AsyncOpenAI(api_key=settings.deepseek_api_key, ...)
```

**问题不在"代码丑"，也不在"参数多"——在于这 3 个参数散落在每个脚本里。** 每多一处散落，就多一个将来要改的地方、多一个改漏的机会。

封装要做的不是省掉参数，而是**把参数换个地方放着**：只定义一次，其他地方从那里取。

---

## 设计：两层分工

改造的思路是把"调模型"这件事拆成两层：

| | factory.py | client.py |
|---|---|---|
| 管什么 | **连哪儿** | **怎么发** |
| 具体内容 | api_key / base_url / model 名 | temperature / messages 拼装 / 重试 / 并发 |
| 变化频率 | 几乎不变（配一次用很久） | 经常变（每个任务可能不同） |

一句话公式：**factory 管"连哪儿"，client 管"怎么发"。**

分开的理由不是"看起来整洁"，而是**这两类东西的变化频率不一样**——厂商连接信息是配置，调用行为是业务逻辑。混在一起，改一个就得动另一个。

改造前后的对比：

```python
# 改造前（每个脚本都这么写）
client = AsyncOpenAI(api_key=..., base_url=...)
resp = await client.chat.completions.create(model=..., messages=[...], temperature=0)
return resp.choices[0].message.content.strip()

# 改造后
from llm_service import LLMClient
llm = LLMClient("deepseek")
await llm.one("问题")        # 一行
```

### 决策 2：为什么要缓存 client？

一开始我以为"每次 `LLMClient("deepseek")` 新建一个 `AsyncOpenAI`"没什么大不了，反正只是构造对象。但实际上 **`AsyncOpenAI` 内部持有一个 httpx 连接池**——TCP 连接是复用的，不是每次请求重新握手。

所以每次都新建的后果是：

- **资源层面**：每个实例一个连接池，连接数随实例数线性膨胀
- **性能层面**：连接无法复用，每次都要重新建连，延迟变高

工厂里用字典缓存解决，key 用 `(provider, api_key)` 而不是只有 provider——因为同一个厂商可能配不同的 key（免费号/付费号），不同 key 必须分开缓存，不能混用。

---

## 三个设计决策

### 决策 1：流式为什么不加重试？

单次调用失败重试是安全的——失败了没有副作用，重来一次即可。但流式不一样：**一旦已经开始往外吐 token，重试就意味着"从头再来"，前端会收到重复内容**。

可重试的前提是「失败时无副作用」。流式不满足这个前提，所以 `stream()` 不加 `@retry`，把决定权交给调用方。

```python
@retry(...)                          # ✅ one() 有重试
async def one(self, prompt): ...

async def stream(self, prompt):      # ✅ stream() 没有重试
    ...
```

### 决策 2：为什么要缓存 client？

`AsyncOpenAI` 内部持有一个 httpx 连接池，TCP 连接是复用的。如果每次 `LLMClient(...)` 都新建一个实例，就等于每次新建一个连接池——连接无法复用，既浪费资源，又让每个请求都要重新建连，直接影响并发效率。

所以工厂里用字典缓存，同配置只建一次。缓存 key 用 `(provider, api_key)` 而不是只有 provider：同一家厂商可能配不同 key，不同 key 必须分开缓存，不能混用。

### 决策 3：为什么要用 Semaphore 封顶并发？

`many()` 是"一次问一堆问题"的接口。第一直觉是用 `asyncio.gather` 把所有请求一起甩出去——但我实测发现**这样比串行还慢**：几十个请求一起冲，被网关限流逐个拒绝重试，最后只跑出 **0.24x** 的速度（比老老实实排队还慢）。

所以加了 `asyncio.Semaphore(max_concurrency)` 限制同时在飞的请求数：前 3 个先发，谁回来谁腾位，第 4 个立刻补上——流水线式滚动，而不是一批批等。

## 实测数据

| 项目 | 结果 |
|---|---|
| 换厂商 | `LLMClient("deepseek")` ↔ `LLMClient("agnes")`，只改一个字符串 |
| 流式 | 86 块逐 token，首 token **0.71s**，总耗时 1.32s |
| 并发 | 串行 2.58s → 并发 **1.16s（2.22x）**，结果顺序与输入一致 |
| 单元测试 | **8 个用例 1.27s 全过**（全 mock，不打网络） |
| 回归测试 | 全项目 **26 passed**，零破坏 |

**关于 2.22x 而不是 3x**：并发耗时约等于"最慢的那个请求"，但实际达不到理想值——有协程调度开销，服务端也有限流。所以 2.22x 已经是合理结果，它证明的是"并发确实生效了"，而不是追求理论峰值。

---

## 加一家厂商，只要 8 行

这段是我自己动手做的验证——为了确认真的理解了工厂模式，我往里加了一家新厂商（智谱 GLM）。

改了**三个文件**：

| 文件 | 改了什么 |
|---|---|
| `.env` | 加 3 行（API key / base_url / model 名） |
| `config.py` | 加 3 个字段（**key 写 `= ""` 占位，真实值只住在 `.env` 里**） |
| `factory.py` | 注册一行 + 过滤一行 |

上层代码——也就是 `LLMClient` 类本身、路由、以及**测试文件**——**一个字都没改**。

```python
# 只保留「配了 key」的厂商：空 key 的厂商当作不存在，
# 避免带着空 key 去撞 401 —— 错误信息更准（"未知厂商" vs "认证失败"）
_PROVIDERS = {k: v for k, v in _PROVIDERS.items() if v[0].strip()}
```

这行过滤一开始我漏写了。漏掉的后果是：**注册 ≠ 可用**。如果某家厂商的 key 没配，`get_client()` 不会报"未知厂商"，而是带着空 key 去撞 401——错误信息从"配置缺失"变成了"认证失败"，排查方向完全跑偏。快速失败比晚失败好。

改完真调了一次 `glm-4.7-flash` 成功。**8 行改动，换来一家新厂商支持。**

---

## 踩坑记录

### 坑 1：pytest 不认异步测试

写完模块后我补了 8 个单元测试，一跑全挂：

```
5 failed: async def functions are not natively supported
```

**原因**：pytest 原生不认识 `async def` 测试函数，它需要一个插件来接管事件循环。

**修法**：`pip install pytest-asyncio`，装完即绿。

这个小坑值得单独记一笔——**只要项目里有异步代码，就一定会再遇到它**。

### 坑 2：`stream=True` 混进了 `one()`

默写 `one()` 实现时，我顺手写了 `stream=True`，结果：

```
AttributeError: 'AsyncStream' object has no attribute 'choices'
```

**原因**：`stream=True` 时 `create()` 返回的是**异步流对象**（`AsyncStream`），不是完整响应对象。所以它当然没有 `.choices` —— 那是完整响应的属性。

| 方法 | 参数 | 返回什么 | 怎么消费 |
|---|---|---|---|
| `one()` | 不带 stream | 完整 `resp` | `resp.choices[0].message.content` |
| `stream()` | `stream=True` | `AsyncStream` | `async for chunk in resp` |

**这就是为什么要拆成两个方法**——它们的返回类型完全不同，一个是一次性拿全文，一个是逐块拿增量。

**更有意思的是重试行为**：这个 `AttributeError` 被 `@retry` **重试了 3 次，白等了 3 秒**。

这里暴露了一个认知：`@retry` 默认对**所有异常**都重试。但重试只对"等一会儿可能就好了"的错误有意义——网络超时、连接断开、429 限流，这些属于环境问题；而 `AttributeError` 这种**代码 bug，重试一万次也是同一个错**，纯浪费时间和 API 配额。

**判断标准**：问自己"等一会儿再来，有可能好吗？"——可能好才重试。

正确的做法是给 `retry` 加白名单：

```python
from tenacity import retry_if_exception_type
from openai import APIConnectionError, APITimeoutError, RateLimitError

@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((APITimeoutError, APIConnectionError, RateLimitError)),  # 只重试这三种
    reraise=True,
)
```

### 坑 3：`reraise` 不是能 import 的名字

我原本在文件头写了：

```python
from tenacity import retry, wait_exponential, stop_after_attempt, reraise   # ❌ ImportError
```

**原因**：`reraise` 只是 `@retry()` 的一个**关键字参数**，不是 tenacity 里可以导入的对象。IDE 报的红线是对的。

**判断口诀**：

> **要用它"造东西"才 import；只是填个 `True` 就不需要。**

- `wait=wait_exponential(...)` —— 你在**调用它造一个等待策略对象** → 要 import
- `stop=stop_after_attempt(3)` —— 同样在造对象 → 要 import
- `retry=retry_if_exception_type(...)` —— 造对象 → 要 import
- `reraise=True` —— 只是填个布尔值，库内部自己读 → **不用 import**

顺便说一下 `reraise` 是干什么的：

| 值 | 3 次都失败后抛什么 |
|---|---|
| `False`（默认） | `tenacity.RetryError`，原始异常被包在里面，要挖 `__cause__` 才看得到 |
| `True` | **原始异常本身**（401 / 超时），上层能直接 `except`，报错信息清楚 |

### 坑 4：我把真实 API key 硬编码进了 `config.py`

加智谱那家厂商时，我在 `config.py` 里直接写了：

```python
zhipu_api_key: str = "真实key直接写在代码里"      # ❌ 危险
```

**这个文件会被 git 提交**——`.gitignore` 只忽略了 `.env`，没忽略 `config.py`。一旦推到 GitHub，key 就公开了，而且通常在**几分钟内**就会被爬虫扫到并盗用；更麻烦的是即使事后删除，git 历史里还留着。

项目里其他两家（agnes / deepseek）都规规矩矩写 `= ""` 走 `.env`，只有新加的这家破例了。

**规则定死**：**所有密钥只住 `.env`，代码里永远只写 `= ""` 占位。**

```
.env        ZHIPU_API_KEY=xxx        ← 被 .gitignore 保护，不进仓库
config.py   zhipu_api_key: str = ""  ← 只是字段声明，真实值运行时从 .env 注入
```

改完之后跑了一次验证：`config.py` 里写的是空串，但运行时 `settings.zhipu_api_key` 拿到了真实值——**这就是 `.env` 生效的证据**。

---

## 下一步

这套模块接下来会直接服务于两个场景：

1. **Agent 循环**：模型输出工具调用意图 → 本地执行 → 结果回传 → 再调模型。这个循环里"怎么调模型"是重复的，`llm.one()` 直接复用
2. **RAG 批量处理**：一次给 20 段文档做摘要/抽取，用 `llm.many()` 并发，Semaphore 自动控流

也就是说，`llm_service` 不是终点，是后面所有功能的**地基**。

---

## 复盘：这个模块到底解决了什么

回到最开始那句话——**参数必须传，和参数必须由我每次手写，是两件事**。

| 维度 | 改造前 | 改造后 |
|---|---|---|
| 写新脚本 | 抄 5 行调用代码 | `llm.one("问题")` |
| 换厂商 | 改 N 个脚本 × 3 处参数 | 改一个字符串 |
| 加重试 | 每个脚本各写一遍 tenacity | `one()` 自带 |
| 单元测试 | 无 | 8 个用例 1.3 秒跑完，全离线 |

封装不是"省掉参数"，是**把参数收敛到一处**——每减少一处散落，就少一个将来要改的地方、少一个改漏的机会。

**验证这个抽象是否划对了，有一个很硬的标准**：加一家新厂商时，上层代码和测试**一个字都不用改**。我加智谱时测试全绿，这一步通过了。
