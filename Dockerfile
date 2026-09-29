# ============================================================
# Dockerfile —— 多阶段构建
#
# 三个阶段：
#   base    → 装生产依赖（只有 requirements.txt 这一份，见该文件头部说明）
#   test    → 在 base 上加测试依赖 + 测试代码，跑 pytest（对应 t-308「容器内 pytest 全绿」）
#   runtime → 最终镜像：只带生产依赖 + 生产代码，非 root 运行
#
# 为什么要多阶段：测试依赖（pytest 三件套）和学习归档不该进最终镜像 ——
# 体积更小、攻击面更少。`docker build` 默认产出最后一个阶段 = runtime。
# ============================================================

# ---------- stage 1：base（依赖层，test 和 runtime 共用） ----------
FROM python:3.12-slim AS base

# PYTHONDONTWRITEBYTECODE：不生成 __pycache__（容器里没人会复用）
# PYTHONUNBUFFERED      ：日志立刻刷出来，否则 `docker logs` 看不到实时输出
# PIP_NO_CACHE_DIR      ：pip 下载缓存不留在层里（白占体积）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pip 源：默认走官方 PyPI（保证镜像可移植，别人 clone 就能构建）。
# 国内网络慢时可覆盖，例如：
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t day01-fastapi:v0.1 .
ARG PIP_INDEX_URL=https://pypi.org/simple

WORKDIR /app

# ⚠️ 关键顺序：先 COPY requirements.txt，再 RUN pip install。
#    只要 requirements.txt 没变，这一层就走缓存 —— 改代码时不必重装依赖。
#    若写成 `COPY . .` 再装依赖，改任何一行代码都会让缓存全废、重装一遍。
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt --index-url "$PIP_INDEX_URL"


# ---------- stage 2：test（测试镜像，不参与部署） ----------
FROM base AS test

# ARG 不跨阶段继承，test 阶段要重新声明才能用
ARG PIP_INDEX_URL=https://pypi.org/simple

COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt --index-url "$PIP_INDEX_URL"

# 测试需要三样东西：pytest 配置 + 测试代码 + 被测的生产代码
COPY pyproject.toml ./
COPY tests/ ./tests/
COPY main.py config.py ./
COPY common/ ./common/
COPY routers/ ./routers/
COPY llm_service/ ./llm_service/

# 哑环境变量：只为让启动期的 validate_settings() 不因缺 key 直接退出。
# 测试全部 mock、不会真发请求 —— 值是不是真的无所谓，但必须【非空】。
# ⚠️ 造它不是当密码用；真部署时用 `docker run -e DEEPSEEK_API_KEY=<真值>` 覆盖。
ENV DEEPSEEK_API_KEY=dummy-key-for-container \
    DEEPSEEK_BASE_URL=https://api.deepseek.com \
    DEEPSEEK_MODEL=deepseek-chat

# 收集范围由 pyproject.toml 的 testpaths 决定 —— 与本地、CI 三处行为一致
CMD ["pytest", "--cov", "--cov-report=term-missing"]


# ---------- stage 3：runtime（最终镜像） ----------
FROM base AS runtime

# 非 root 运行：万一应用被攻破，攻击者拿到的是普通用户，不是 root
RUN useradd --create-home --uid 1000 appuser

# 只 COPY 生产代码。测试代码、学习归档（study_day_learns/）、
# 本地模型权重（models/，92MB）统统不进最终镜像。
COPY --chown=appuser:appuser main.py config.py ./
COPY --chown=appuser:appuser common/ ./common/
COPY --chown=appuser:appuser routers/ ./routers/
COPY --chown=appuser:appuser llm_service/ ./llm_service/

USER appuser

EXPOSE 8000

# ⚠️ --host 0.0.0.0 不能省：默认 127.0.0.1 只在容器内部监听，
#    宿主机的 `-p 8000:8000` 映射不进来，表现为「容器活着但浏览器连不上」。
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
