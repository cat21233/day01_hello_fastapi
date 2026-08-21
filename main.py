"""
Day 1-6 学习档案：D1-D5 功能合并 + D6 模块化重构
运行：cd 项目目录后 → uvicorn main:app --port 8000
文档：http://127.0.0.1:8000/docs

结构：
- main.py      骨架：app 实例 + 全局中间件 + 顶层杂项(/ 和 /health) + 挂载路由
- routers/     业务模块：items / users / stream / external
"""

import time

from fastapi import FastAPI, Request
from config import settings

from routers.items import router as items_router
from routers.users import router as users_router
from routers.stream import router as stream_router
from routers.external import router as external_router

app = FastAPI(title=settings.app_name)

# ============ D6 重构：挂载各业务模块 ============
app.include_router(items_router)
app.include_router(users_router)
app.include_router(stream_router)
app.include_router(external_router)


# ============ D4：全局中间件 — 记录请求处理耗时 ============
# 中间件对所有请求生效：进站记时 → 放行路由 → 出站把耗时贴到响应头
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    cost = time.time() - start
    response.headers["X-Process-Time"] = str(cost)
    return response


# ============ 顶层杂项：留在主文件 ============
@app.get("/")
def read_root():
    return {"message": "Hello World"}


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "async"}
