"""
Day 1-6 学习档案：D1-D5 功能合并 + D6 模块化重构
运行：cd 项目目录后 → uvicorn main:app --port 8000
文档：http://127.0.0.1:8000/docs

结构：
- main.py      骨架：app 实例 + 全局中间件 + 顶层杂项(/ 和 /health) + 挂载路由
- routers/     业务模块：items / users / stream / external
"""

import time
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from routers.limits import limiter
from fastapi import FastAPI, Request
from config import settings, validate_settings
from fastapi.middleware.cors import CORSMiddleware
from routers.items import router as items_router
from routers.users import router as users_router
from routers.stream import router as stream_router
from routers.external import router as external_router
from routers.auth import router as auth_router
from routers.llm import router as llm_router
from routers.prompts import router as prompts_router
from common.logger import log_request

# 应用启动时刻，用来算 uptime（/health 用）
START_TIME = time.time()


# ============ t-236：启动钩子 — 校验配置 ============
# lifespan 在 app 启动/关闭时各跑一次。把 validate_settings() 放在这里，
# 配置有缺失时服务根本起不来（fail-fast），而不是跑起来第一次调 LLM 才 401。
@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_settings()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
   # 顶部 import

# ============ D11：CORS 跨域支持 ============
# 允许前端页面跨域调用本服务（生产环境要收紧成具体域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 允许的来源：* = 任何人（学习阶段够用）
    allow_credentials=False,    # 不允许携带 Cookie（和 * 互斥，不能同时 True）
    allow_methods=["*"],        # 所有 HTTP 方法
    allow_headers=["*"],        # 所有请求头
)



app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============ D6 重构：挂载各业务模块 ============
app.include_router(items_router)
app.include_router(users_router)
app.include_router(stream_router)
app.include_router(external_router)
app.include_router(auth_router)
app.include_router(llm_router)
app.include_router(prompts_router)

# ============ D4：全局中间件 — 记录请求处理耗时 ============
# 中间件对所有请求生效：进站记时 → 放行路由 → 出站把耗时贴到响应头 + 写结构化日志
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    cost_seconds = time.time() - start
    response.headers["X-Process-Time"] = str(cost_seconds)
    # 一次请求一条结构化日志（耗时转毫秒）
    log_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=cost_seconds * 1000,
    )
    return response


# ============ 顶层杂项：留在主文件 ============
@app.get("/")
def read_root():
    return {"message": "Hello World"}


# ============ t-238：健康检查 + 基础指标 ============
# 之前只返回 {"status":"ok"}。生产里健康检查要能反映「服务活着 + 依赖可用」，
# 这里补上 uptime / 当前厂商 / 版本，方便监控和排障。
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "llm_provider": settings.llm_provider,
        "version": "0.1.0",
    }
