# llm_service — LLM 统一调用中间层

一个薄封装层，让上层业务（FastAPI 路由 / Agent / RAG / 实验脚本）不必直接接触 openai SDK。

## 解决什么问题

改造前，项目里散落着多处独立的 client 实例化：

```python
# common/llm_client.py:17
client = AsyncOpenAI(api_key=settings.agnes_api_key, base_url=settings.agnes_base_url)

# routers/llm.py:13
client = AsyncOpenAI(api_key=settings.agnes_api_key, base_url=settings.agnes_base_url)  # 重复第二份
```

代价：

1. **换厂商要改 N 处** —— 测试用 deepseek、线上用 agnes 时，配置漂移
2. **连接池浪费** —— 每个 client 各持一套 httpx keep-alive 连接池
3. **能力无法组合** —— 「流式 + 重试」「并发 + 重试」要重复手写

## 用法

```python
from llm_service import LLMClient

llm = LLMClient("deepseek")                    # 换厂商只改这一个字符串

text = await llm.one("用一句话解释什么是向量")   # 单次（带重试）

async for piece in llm.stream("介绍一下异步"):   # 流式
    print(piece, end="")

results = await llm.many(["问题1", "问题2", "问题3"])  # 并发（信号量封顶）
```

## 模块结构

```
llm_service/
├── __init__.py     收窄公开接口，只暴露 LLMClient / get_client / get_model
├── factory.py      厂商工厂：名字 → client（带缓存）
└── client.py       核心类 LLMClient：one / stream / many
```

## 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| client 复用 | 模块级字典缓存，key = `(provider, api_key)` | 同配置只建一次，连接池复用；实测并发性能依赖此 |
| 厂商切换 | 工厂接 `provider: str`，未知值抛 `ValueError` | 上层只传字符串，不 import SDK；快速失败优于静默用错厂商 |
| **重试位置** | 只装饰 `one()`，**`stream()` 不重试** | 流式一旦已吐出 token，重试会造成重复输出；可重试的前提是「失败时无副作用」 |
| 并发上限 | `many()` 内 `Semaphore(max_concurrency)` | 无脑全并发会打爆网关触发限流，**实测 0.24x（比串行还慢）** |

## 实测数据（2026-09-10，deepseek-chat）

| 场景 | 结果 |
|---|---|
| 换厂商 | `LLMClient("deepseek")` → `LLMClient("agnes")`，其余代码零改动 |
| 流式 | 86 块渐进输出，首 token 延迟 0.71s，总耗时 1.32s |
| 并发 `many(3)` | 串行 2.58s → 并发 1.16s，**提速 2.22x**，结果顺序与输入一致 |

## 测试

```bash
pytest tests/test_llm_service.py -v
```

8 个用例，**全部 mock 掉 SDK、不打真实网络**（1.3s 跑完）：

- 工厂：同厂商返回同一实例 / 未知厂商抛错 / model 跟随 provider
- `one()`：剥首尾空白 / `content=None` 兜底不崩
- `many()`：并发结果顺序保持输入序 / `return_exceptions` 隔离单个失败
- `stream()`：过滤纯空白块（避免 SSE 出现空 `data:` 帧）

> 为什么 mock 而不打真实 API：真实的网络测试只能证明「网通不通」，
> 单元测试要证明的是「代码逻辑对不对」，且必须能离线在 CI 里秒级跑完。

## 依赖

- `openai`（AsyncOpenAI）
- `tenacity`（指数退避重试）
- `pytest` + `pytest-asyncio`（测试）
