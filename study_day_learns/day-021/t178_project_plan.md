# study_day_learns/day-021/t178_project_plan.md
# t-178 周项目 I：LLM 服务模块（llm_service/）

## 一、为什么做（问题陈述）

项目里当前散落着 3 处独立的 client 实例化：

| 位置 | 厂商配置 |
|---|---|
| `common/llm_client.py:17` | agnes |
| `routers/llm.py:13` | agnes（重复第二份） |
| `study_day_learns/day-021/*.py` | deepseek |

代价：
1. **换厂商要改 N 处**——测试用 deepseek、上线用 agnes，配置漂移
2. **连接池浪费**——每个 client 各持一套 keep-alive 连接池
3. **能力无法组合**——想「流式 + 重试」要手写，想「并发 + 重试」再手写一遍

## 二、目标（简历视角的一句话）

> 一个 LLM 中间层：厂商可切换、sync/async 双模、流式与重试正交组合，
> 上层业务（路由 / Agent / RAG）只依赖接口，不碰 SDK。

## 三、模块结构

```
llm_service/
├── __init__.py        对外只暴露 4 个名字，隐藏内部实现
├── factory.py         厂商工厂：名字 → client（带缓存，同样配置只建一次）
├── client.py          核心类 LLMClient：one / stream / many 三个方法
└── exceptions.py      统一异常（可选，本日先略）
```

## 四、设计决策（要能讲出来的 4 条）

| 决策 | 选择 | 理由 |
|---|---|---|
| client 复用 | 模块级字典缓存 `_cache[(provider, key)]` | 同配置只建一次，连接池复用 |
| 厂商切换 | 工厂函数接 `provider: str` | 上层只传字符串，不 import SDK |
| 重试位置 | 装饰在 `one()` 上，`stream()` 不重试 | **流式一旦吐了字节就无法回退**——重试会重复输出 |
| 并发上限 | `many()` 内 `Semaphore` | 已实测无脑全并发 0.24x（比串行还慢） |

## 五、验收标准（能跑 + 能测）

- [ ] `LLMClient("deepseek").one("1+1=?")` 返回字符串
- [ ] `LLMClient("agnes").one("1+1=?")` 返回字符串（换厂商一行参数）
- [ ] `stream()` 逐 token yield，可用 `async for` 消费
- [ ] `many([...])` 3 个 prompt 并发，耗时 ≈ 最慢单个（非求和）
- [ ] pytest 至少 3 个用例，不依赖外网（mock 掉 SDK）

## 六、时间盒

- 骨架 + factory + client 三方法：40 分钟
- 跑通验证：10 分钟
- pytest：30 分钟（9-11 做）
- 博客第 2 篇：9-11 做
