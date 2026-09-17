# FastAPI 进阶费曼讲解：认证 / 限流 / SSE

> 用自己的话讲清楚三大块。每块的「防坑」是面试最常追问的点，也是我（叶梓皓）讲错过、被纠正后焊死的点。

## 一、认证（JWT + Depends + RBAC）

### 1. JWT 三段
- **header**：JWT 自身的头部，声明 `alg` 算法（如 HS256）、`typ` 类型。
- **payload**：**服务端签发 JWT 时写进去的声明**（`user_id`、`role`、`exp` 过期时间）。是服务端生成的，不是客户端调用时传的；客户端只传整个 JWT，服务端验签后信任它。
- **signature**：前两段 base64 拼接后用**密钥**算出的哈希（HMAC）。作用是**防篡改**。
- 🚫 防坑：payload 是**明文 base64**，谁都能解码看到，**绝不能放密码**。它不是"加密"。我一开始把 signature 说成"加密"，错。

### 2. Depends 鉴权
- `Depends(get_current_user)` 是"声明"依赖，不是"调用"。
- `get_current_user` 从 `Authorization: Bearer xxx` 请求头拿 token、验签、返回当前用户对象。
- 🚫 防坑：删了 `Depends` = 接口**裸奔**，**任何人都能访问**（不需要 token）。我一开始说反成"任何人不能访问"，错。

### 3. RBAC
- 基于角色的访问控制：不同角色能访问不同**接口/操作**（资源级权限），不只是"看到不同字段"。
- 例：`role` 从 payload 拿出来，admin 能调 `/admin/delete`，普通用户只能登录/查看。

## 二、限流（slowapi）

### 1. 为什么限流
- 限制**同 IP 单位时间**请求频率（如 3 次/分钟），防刷、防滥用、保护上游（如 LLM API）。不是"禁止多次访问"，是限制频率。

### 2. 怎么挂
- `@limiter.limit("3/minute")` 必须写在 `@router.get(...)` **下面**、def 上面。
- 函数**必须接收 `request: Request`**——slowapi 要从 request 拿客户端 IP 来计数，不注入就拿不到 IP、做不了限流。

### 3. 计数维度
- `key_func=get_remote_address` → 返回 `request.client.host`（客户端 IP），同 IP 累积计数 = "同一个人刷"。

### 4. 超限制
- 返回 **429**（不是 430）。

### 5. 测试注意
- conftest 里 `limiter.enabled=False` 关掉限流，否则 pytest 反复调接口累积触发 429 让测试**假挂**（功能没问题，被限流挡了）。

## 三、SSE 流式

### 1. 为什么 SSE
- 打字机/流式输出，不用等全部生成完（对比 `return` 一次性返回）。

### 2. 帧格式
- `data: xxx\n\n`：**两个 `\n` 是帧分隔符**。少一个，前端 `EventSource` 不认为帧完整，不触发 `onmessage`（表现像收不到，不是"后端返回不了"）。
- 🚫 防坑：字段名 `data`/`event`/`id` 必须**顶格**，不能有前导空格（` data:` 整帧被忽略）；但 `data:` 冒号后要有空格。

### 3. event: end
- 自定义事件名，前端 `addEventListener('end', ...)` 监听，明确标记"流结束"做收尾（比靠连接断开判断明确）。

### 4. StreamingResponse 与生成器
- 生成器 `yield` **产**数据；`StreamingResponse(generator)` 把生成器包起来，让 FastAPI **边 yield 边推**给客户端（默认等 return 才发，是一次性）。

### 5. 断连检测（重点坑）
- `request.is_disconnected()` **必须配 `async def` 路由**。
- `sync def` → 扔进**线程池** → 同步代码调 `is_disconnected`（内部 await receive），receive 流被另一协程占 → **跨线程死锁 → 0 字节**。
- `async def` → 同事件循环 `await` 协作，不抢。
- 🚫 防坑：`TestClient` 测不出，必须真实 uvicorn + curl（t-086 纪律）。

### 6. id + Last-Event-ID 续传
- 每帧带 `id: n`；断连重连时浏览器自动带 `Last-Event-ID` 请求头，后端从断点继续发（断了不丢数据）。

### 7. wait_for 超时兜底
- `asyncio.wait_for(client.create(...), timeout=10)` 给上游 API 调用加超时，超 10 秒抛 `TimeoutError`；generator `except` 后 `yield "上游响应超时"` 再 `return`，避免接口永久卡死。

### 实战代码（routers/llm.py 核心片段）
```python
@router.get("/llm/chat")
@limiter.limit("10/minute")
async def llm_chat(request: Request, prompt: str = Query(..., min_length=1),
                   user=Depends(get_current_user)):
    return sse_response(llm_stream_generator(prompt, request))

async def llm_stream_generator(prompt, request):
    try:
        stream = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.agnes_model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            ),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        yield "上游接口响应超时,请稍后重试"
        return
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta.strip():
            yield delta
        if await request.is_disconnected():
            break
```
