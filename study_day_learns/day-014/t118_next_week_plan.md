# 下周学习计划（2026-08-31 ~ 2026-09-06）

> 阶段：stage-1 基础筑基（LLM API 应用开发方向）
> 制定时间：2026-08-30（本周日收工前）
> 本周已完成的铺垫：t-109~t-111（单次/流式/多轮/封装/终端对话程序全跑通）

---

## 一、下周主题地图

| 日期 | 主题 | 核心产出 |
|---|---|---|
| 8-31 周一 | **流式输出专题** | SSE 包装 LLM 流式、前端 EventSource 联调、429 错误处理、接入 W2 骨架 |
| 9-01 周二 | **国产模型接入** | 通义/DeepSeek 兼容 OpenAI、base_url 切换、temperature/top_p/max_tokens 调优、工厂函数 |
| 9-02 周三 | **Embedding 入门** | 文本向量化、余弦相似度(numpy)、本地 json/np 存储 |
| 9-03 周四 | **异步调用进阶** | AsyncOpenAI、asyncio.gather 并发、tenacity 指数退避重试 |
| 9-04 周五 | **整合 + 输出** | 调用层改 async+重试、费曼草稿、本周博客成文 |
| 9-05 周六 | **周项目 + 测试** | LLM 服务模块(sync+async+流式+embedding)、pytest、ollama 本地模型弹性 |
| 9-06 周日 | **Prompt 工程** | 角色设定/清晰指令/输出格式约束、CoT/Few-shot/Structured Output/Function Calling |

---

## 二、每日要点（来自 plan.json）

### 8-31 流式专题（6 项）
- t-121 流式输出：`stream=True` 逐 token 接收（**今天 t-110 已讲透原理，明天动手练**）
- t-122 FastAPI SSE 包装：`/chat/stream`（**你项目已有 `routers/llm.py` 的 SSE 封装，复用 `common/sse.py`**）
- t-123 前端联调：EventSource 接收流式渲染（**你 t-087 写过 `static/sse_counter.html`，可借鉴**）
- t-124 流式错误处理：捕获 API 异常 + 限流 429（**你 t-100 已在 llm.py 集成 `wait_for` 超时兜底，t-091 有 SSE 封装**）
- t-125 艾宾浩斯复现（D1/D3/D7 节点）
- t-126 整合：流式 chat 接入 W2 FastAPI 骨架（**W2 骨架=你 t-101 做的认证+限流+流式三件套**）

### 9-01 国产模型（6 项）
- t-127 通义/DeepSeek 兼容 OpenAI 格式接入
- t-128 统一客户端：`base_url` 切换厂商
- t-129 模型对比：价格/速度/质量
- t-130 参数调优：temperature/top_p/max_tokens 实测
- t-131 艾宾浩斯复现
- t-132 工厂函数：按名字返回不同厂商客户端

### 9-02 Embedding（6 项）
- t-133 向量化与语义相似度理解
- t-134 调 embedding 接口文本转向量
- t-135 numpy 余弦相似度
- t-136 专项加练（动手题）
- t-137 艾宾浩斯复现
- t-138 本地 json/np 存 embedding

### 9-03 异步进阶（6 项）
- t-139 AsyncOpenAI 客户端（**你题2 已跑通**）
- t-140 asyncio.gather 批量并发（**你 t-088 已练过**）
- t-141 tenacity 指数退避重试（**新库，重点**）
- t-142 专项加练
- t-143 艾宾浩斯复现
- t-144 概念笔记整理

### 9-04 整合 + 输出（6 项）
- t-145 调用层改 async + 重试
- t-146 专项加练
- t-147 艾宾浩斯复现
- t-148 费曼输出草稿
- t-149 本周技术博客成文（**可基于今天 `t117_blog.md` 扩写**）
- t-150 概念笔记

### 9-05 周项目 + 测试（11 项，重头戏）
- t-151/t-153/t-161 费曼输出（讲给小白）
- t-152/t-157 pytest 补用例（≥60% 覆盖）
- t-154 专项加练
- t-155 **周项目：LLM 服务模块（sync+async+流式+embedding）**
- t-156 艾宾浩斯复现
- t-158 README 记录支持的模型与示例
- t-159 弹性：olama 本地开源模型跑通
- t-160 概念笔记
- t-162 **下周规划（9-07 起）**

### 9-06 Prompt 工程（8 项）
- t-163/t-166 艾宾浩斯复现 + 概念笔记（Prompt 工程/CoT/Few-shot/Structured Output/Function Calling）
- t-164/t-167/t-168/t-169/t-170/t-171 角色设定/系统提示词/输出约束/对比实验

---

## 三、基于本周薄弱点的特别提醒

你本周（8-29~8-30）反复踩的坑，下周这些任务里**还会遇到**，提前焊死：

1. **`user`=提问者、`assistant`=模型回复** —— 9-02 Embedding、9-06 Prompt 构造 messages 时别再反。
2. **`load_dotenv` 必须在 `from config import settings` 之前** —— 写 9-01 工厂函数、9-03 异步客户端时，子目录脚本必踩。
3. **`messages` 元素间逗号别漏、`role` 字段写全** —— 任何构造 messages 的地方。
4. **流式：`AsyncOpenAI`+`stream=True`+`async for`+`delta.content`+`or ""`** —— 8-31 流式专题直接复用。
5. **`async def` 路由配 `is_disconnected`**（t-086 死锁原理）—— 8-31 写 SSE 接口时别退化成 sync def。
6. **别裸 `except:`** —— 9-03 tenacity 重试、9-04 整合时都用具体异常。

---

## 四、弹性建议

- 下周任务量偏大（尤其 9-05 有 11 项），**优先保住 high 优先级**（流式、异步、周项目、Prompt 基础）。
- 8-31 的 SSE/EventSource 你已有现成代码（t-087/t-091/t-100/t-101），**复用 > 重写**，省时间。
- 9-04 博客可直接基于今天 `t117_blog.md` 扩写，不必从零。
- 每天结束按约定自动打卡（streak 连续维护）。
