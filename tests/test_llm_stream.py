import pytest
import routers.llm as rl

async def _empty_gen():
    """
    假的上游:一个字叶不吐
    """
    if False:

        yield ""

class _FakeClient():
    def __init__(self,factory):
        self._factory = factory
    def stream(self,prompt):
        return self._factory()
# tests/test_llm_stream.py
# t-260 为 SSE 生产函数 _produce 写单元测试



# ============ 零件区 ============


async def _normal_gen():
    """正常流：吐两块。"""
    yield "你好"
    yield "，世界"


async def _timeout_gen():
    """假装首块超时。"""
    raise TimeoutError("上游首块超时")
    yield ""          # 这行不可达，只为让本函数成为「生成器」


async def _boom_gen():
    """假装上游报 429（额度打满）。"""
    raise RuntimeError("429 rate limit exceeded")
    yield ""




def _setup(monkeypatch, factory):
    """摆现场：换掉真客户端 + 关掉 120s 定时器。"""
    monkeypatch.setattr(rl, "llm", _FakeClient(factory))

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(rl, "_expire", _noop)


async def _run_produce(sid):
    """执行：跑一遍 _produce，返回最终的 _Stream。"""
    rl._STREAMS[sid] = rl._Stream()
    try:
        await rl._produce(sid, "hi")
        return rl._STREAMS[sid]
    finally:
        rl._STREAMS.pop(sid, None)


# ============ 测试区 ============

@pytest.mark.asyncio
async def test_empty_stream_appends_nothing(monkeypatch):
    """空流：上游一个字都没吐 → 不应产生任何 chunk，更不能有假报错。"""
    _setup(monkeypatch, _empty_gen)
    st = await _run_produce("t-empty")
    assert st.done is True
    assert st.chunks == []


@pytest.mark.asyncio
async def test_normal_stream_collects_all_chunks(monkeypatch):
    """正常流：chunk 按序收齐，一块不少。"""
    _setup(monkeypatch, _normal_gen)
    st = await _run_produce("t-normal")
    assert st.chunks == ["你好", "，世界"]


@pytest.mark.asyncio
async def test_first_chunk_timeout_appends_hint(monkeypatch):
    """首块超时：追加超时提示，而不是断流。"""
    _setup(monkeypatch, _timeout_gen)
    st = await _run_produce("t-timeout")
    assert st.chunks == ["上游接口响应超时,请稍后重试"]


@pytest.mark.asyncio
async def test_upstream_error_is_wrapped_as_chunk(monkeypatch):
    """上游抛异常（如 429）：被包装成一条 chunk，前端不断流。"""
    _setup(monkeypatch, _boom_gen)
    st = await _run_produce("t-boom")
    assert len(st.chunks) == 1
    assert st.chunks[0].startswith("[上游异常]")
    assert "429 rate limit" in st.chunks[0]

