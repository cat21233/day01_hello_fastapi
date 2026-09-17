"""
common/logger.py —— 结构化日志

为什么需要结构化日志？
  平时 print 是给人临时看的，机器没法解析。结构化日志把每条日志变成
  「固定字段 + 值」（这里用 JSON 单行），方便以后接 Loki / ELK 做检索和告警。

本模块统一两件事：
  1. 配置一个 JSON 格式的 logger（生产友好，一行一条）
  2. 提供两个 helper：
       log_request() —— 记「一次 HTTP 请求」（中间件调用）
       log_llm()     —— 记「一次 LLM 调用」的 token 消耗（client 调用）
"""
import json
import logging
from typing import Optional

# 模块级单例：避免每次 import 都 addHandler，导致同一条日志被打两遍。
_logger = logging.getLogger("fastapi_app")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    # 只输出 message 本身，格式由我们自己在 log_request/log_llm 里拼成 JSON。
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def get_logger(name: str = "fastapi_app") -> logging.Logger:
    """拿 logger。默认返回应用统一那个；传别的名字就新建一个。"""
    return _logger if name == "fastapi_app" else logging.getLogger(name)


def log_request(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """记一次 HTTP 请求。

    duration_ms 由 main.py 的 add_process_time 中间件算好传进来；
    prompt/completion_tokens 由 LLMClient 调用后回填（见 client.py）。
    """
    record = {
        "event": "http_request",
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    _logger.info(json.dumps(record, ensure_ascii=False))


def log_llm(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> None:
    """记一次 LLM 调用的 token 消耗（不依赖 HTTP 上下文，所以单独一个 helper）。"""
    record = {
        "event": "llm_call",
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    _logger.info(json.dumps(record, ensure_ascii=False))
