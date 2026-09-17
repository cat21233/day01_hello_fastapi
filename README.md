# FastAPI 认证 + 限流 + 流式 骨架应用

一个把「JWT 认证」「接口限流」「SSE 流式响应」三件套合体的 FastAPI 骨架，
可直接作为 Agent / LLM 后端实习项目的底座。

## 运行

```bash
.\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
# 文档：http://127.0.0.1:8000/docs
```

## 三件套说明

### 1. 认证（JWT）
- `routers/auth.py`：`/token` 登录签发 access + refresh；`/refresh` 仅换 access。
- `get_current_user`（Depends 依赖）：从 `Authorization: Bearer <token>` 抽 token、验签、认 `type=="access"`。
- `get_current_admin`：在认证(401)之后做鉴权(403)，实现 RBAC。
- **关键认知**：`Depends(get_current_user)` 是“声明”不是“调用”；删掉它 = 接口裸奔，任何人可访问。
- payload 只是 base64 编码（非加密），**绝不能放密码**。

### 2. 限流（slowapi）
- `routers/limits.py`：`Limiter(key_func=get_remote_address)` 按 IP 计数。
- 用法：装饰器 `@limiter.limit("10/minute")` 必须写在 `@router.get` **下方**、且路由函数要接收 `request: Request`。
- 超限返回 `429`；全局异常处理器 `_rate_limit_exceeded_handler` 在 `main.py` 注册。
- 测试中 `conftest.py` 默认 `limiter.enabled=False`，避免老测试互相撞 429。

### 3. 流式（SSE）
- `common/sse.py`：`sse_response()` 通用包装，把异步生成器包成 `StreamingResponse(media_type="text/event-stream")`，自动补 `event:end` 结束帧。
- 帧格式：`data: xxx\n\n`（**两个换行**才是帧分隔符，少一个前端收不到）；`id:N` 用于断线续传（`Last-Event-ID` 头）。
- 流式路由**必须是 `async def`**：`request.is_disconnected()` 要和 `StreamingResponse` 内置的断连监听抢同一条 `receive` 流，sync def 路由跑线程池会跨线程争用 → 死锁 → 0 字节（TestClient 测不出，必须真实 uvicorn + curl 验证）。
- `routers/llm.py`：`/llm/chat` 用 `asyncio.wait_for(..., timeout=10)` 给上游 LLM 接口加超时兜底，超时 yield 错误帧后 `return`。

## 三件套合体的接口

| 接口 | 认证 | 限流 | 流式 |
|---|---|---|---|
| `/token` | - | ✅ 3/min | - |
| `/llm/chat` | ✅ | ✅ 10/min | ✅ |
| `/stream/protected` | ✅ | ✅ 20/min | ✅ |
| `/stream/greet`、`/stream/counter` | 公开 demo | - | ✅ |

## 测试

```bash
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

## 面试可讲的几个坑（真实踩过）
1. async 路由 + `is_disconnected` 死锁（见上）。
2. `wait_for` 超时后 `except` 里必须 `return`，否则引用未赋值的 `stream` 抛 `UnboundLocalError`。
3. SSE 帧分隔符是 `\n\n`，字段名顶格无空格前缀。
4. `Depends` 删了 = 接口裸奔。
