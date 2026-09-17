# tests/test_llm_service.py
# t-178 为 LLM 服务模块写单元测试
#
# 关键策略：mock 掉 SDK，不打真实网络。
#   为什么？① 测试要能离线跑、秒级返回 ② 断了 API 也要能跑 CI
#   ③ 真实调用花钱且不稳定，测不出「代码逻辑对不对」，只测出「网通不通」
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_service import LLMClient
from llm_service.factory import get_client, get_model


# ============ ① 工厂层测试 ============

def test_get_client_returns_same_instance():
    """同厂商重复取应拿到同一个 client（连接池复用）。"""
    c1 = get_client("deepseek")
    c2 = get_client("deepseek")
    assert c1 is c2


def test_get_client_unknown_provider():
    """未知厂商应快速失败（抛 ValueError），而不是静默用错厂商。"""
    with pytest.raises(ValueError):
        get_client("openai")


def test_get_model_follows_provider():
    assert get_model("deepseek") == "deepseek-chat"
    assert get_model("agnes") == "agnes-2.0-flash"


# ============ ② one() 测试（mock 掉网络）============

def _fake_response(text: str, usage=None):
    """造一个假的 API 响应对象，结构模仿 SDK 真实返回。

    注意 usage 必须显式给出：真实 SDK 的 resp.usage 要么是 CompletionUsage，
    要么是 None（部分代理网关不返回）。不写的话 MagicMock 会自动编一个假对象，
    下游 token 日志一旦拿去 json.dumps 就会炸成
    「TypeError: Object of type MagicMock is not JSON serializable」。
    —— 教训：mock 只造「用到的字段」是不够的，残缺的 mock 会误伤下游代码。
    """
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


@pytest.mark.asyncio
async def test_one_strips_whitespace():
    """one() 应剥掉首尾空白——调用方拿到的是干净文本。"""
    client = LLMClient("deepseek")
    with patch.object(
        client._client.chat.completions, "create",
        new=AsyncMock(return_value=_fake_response("  hello  \n")),
    ):
        result = await client.one("say hi")
    assert result == "hello"


@pytest.mark.asyncio
async def test_one_handles_none_content():
    """content 为 None 时不能崩（用 `or ""` 兜底）。"""
    client = LLMClient("deepseek")
    with patch.object(
        client._client.chat.completions, "create",
        new=AsyncMock(return_value=_fake_response(None)),
    ):
        result = await client.one("say hi")
    assert result == ""


# ============ ③ many() 并发测试 ============

@pytest.mark.asyncio
async def test_many_preserves_order():
    """并发结果顺序必须与输入一致——这是 many() 的硬契约。"""
    client = LLMClient("deepseek")

    async def fake_one(prompt: str) -> str:
        # 故意让先发的慢，检验 gather 是否按输入序而非完成序返回
        await asyncio.sleep(0.05 if prompt == "A" else 0.01)
        return f"reply-{prompt}"

    client.one = fake_one  # type: ignore[method-assign]
    results = await client.many(["A", "B", "C"], max_concurrency=3)
    assert results == ["reply-A", "reply-B", "reply-C"]


@pytest.mark.asyncio
async def test_many_return_exceptions_isolates_failure():
    """return_exceptions=True 时，单个失败不能拖垮整批。"""
    client = LLMClient("deepseek")

    async def flaky_one(prompt: str) -> str:
        if prompt == "B":
            raise RuntimeError("网关抖动")
        return f"reply-{prompt}"

    client.one = flaky_one  # type: ignore[method-assign]
    results = await client.many(["A", "B", "C"], return_exceptions=True)

    assert results[0] == "reply-A"
    assert isinstance(results[1], RuntimeError)
    assert results[2] == "reply-C"


# ============ ④ stream() 测试 ============

@pytest.mark.asyncio
async def test_stream_filters_blank_chunks():
    """流式应过滤纯空白块（否则 SSE 会出现空 data: 帧）。"""

    async def fake_stream():
        for piece in ["你", "好", "   ", "呀"]:
            delta = MagicMock()
            delta.content = piece
            choice = MagicMock()
            choice.delta = delta
            chunk = MagicMock()
            chunk.choices = [choice]
            chunk.usage = None      # 真实流式里 usage 只在最后一个 chunk 出现
            yield chunk

    client = LLMClient("deepseek")
    with patch.object(
        client._client.chat.completions, "create",
        new=AsyncMock(return_value=fake_stream()),
    ):
        collected = [p async for p in client.stream("hi")]

    assert collected == ["你", "好", "呀"]   # 空白块被滤掉


# ============ ⑤ token 日志测试（t-237）============

@pytest.mark.asyncio
async def test_one_logs_token_usage():
    """有 usage 时，one() 应把 token 用量记进结构化日志。"""
    from types import SimpleNamespace

    fake_usage = SimpleNamespace(prompt_tokens=12, completion_tokens=7)
    client = LLMClient("deepseek")
    with patch.object(
        client._client.chat.completions, "create",
        new=AsyncMock(return_value=_fake_response("hi", usage=fake_usage)),
    ), patch("llm_service.client.log_llm") as log:
        await client.one("say hi")

    log.assert_called_once_with(
        provider="deepseek",
        model="deepseek-chat",
        prompt_tokens=12,
        completion_tokens=7,
    )


@pytest.mark.asyncio
async def test_one_skips_log_when_no_usage():
    """usage 为 None（网关不返回）时，不能记日志、更不能崩。"""
    client = LLMClient("deepseek")
    with patch.object(
        client._client.chat.completions, "create",
        new=AsyncMock(return_value=_fake_response("hi", usage=None)),
    ), patch("llm_service.client.log_llm") as log:
        result = await client.one("say hi")

    assert result == "hi"
    log.assert_not_called()
