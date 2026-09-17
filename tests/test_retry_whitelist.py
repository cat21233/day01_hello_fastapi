"""验证 one() 的重试白名单「真的」生效。

为什么需要这个文件：
    26 passed 只能证明「没改坏」，证明不了「改对了」——
    之前没有任何测试断言过重试次数，白名单写错（比如写成不存在的类型、
    或者 retry= 参数名敲错）测试照样全绿。

两个断言（都用假 client，不发真实网络请求）：
    1. 白名单内错误 APITimeoutError → create() 被调 3 次才抛出（重试生效）
    2. 白名单外错误 ValueError      → create() 只被调 1 次就抛出（不重试）
"""
from types import SimpleNamespace

import httpx
import pytest
from openai import APITimeoutError

from llm_service.client import LLMClient

_FAKE_REQUEST = httpx.Request("POST", "http://fake.local/v1/chat/completions")


def _fake_openai_raising(exc: BaseException, counter: list[int]):
    """造一个假 client：每次 create() 都记一笔账，然后抛指定异常。"""

    async def _create(**_kwargs):
        counter.append(1)
        raise exc

    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_create))
    )


def _patch_client(monkeypatch, fake):
    """把 LLMClient 拿 client / model 的两个入口换成假的，彻底断网。"""
    monkeypatch.setattr("llm_service.client.get_client", lambda provider: fake)
    monkeypatch.setattr("llm_service.client.get_model", lambda provider: "fake-model")


@pytest.mark.asyncio
async def test_whitelisted_error_retries_3_times(monkeypatch):
    counter: list[int] = []
    _patch_client(
        monkeypatch, _fake_openai_raising(APITimeoutError(_FAKE_REQUEST), counter)
    )

    llm = LLMClient("agnes")
    with pytest.raises(APITimeoutError):
        await llm.one("hi")

    assert len(counter) == 3, f"应重试到 3 次，实际 {len(counter)} 次"


@pytest.mark.asyncio
async def test_non_whitelisted_error_no_retry(monkeypatch):
    counter: list[int] = []
    _patch_client(monkeypatch, _fake_openai_raising(ValueError("boom"), counter))

    llm = LLMClient("agnes")
    with pytest.raises(ValueError):
        await llm.one("hi")

    assert len(counter) == 1, f"应只调 1 次，实际 {len(counter)} 次（说明白名单没拦住）"
