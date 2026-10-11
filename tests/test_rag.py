"""tests/test_rag.py —— /rag 端点的判别力测试（t-1262 + t-1263）

ingest 覆盖四件事：
  1. 空库真的能写入（不是走幂等那条路）
  2. 正斜杠 / 反斜杠两种路径写法都能匹配（10-10 修的那个坑）
  3. 不存在的路径返回 0 而不是抛异常
  4. HTTP 端点 /rag/ingest 返回结构正确

query 覆盖四件事：
  5. 返回结构正确，score = 1 - 余弦距离（越大越像）
  6. source 过滤传正斜杠也能命中（路由层做了分隔符转换）
  7. n 参数生效，非法入参返回 422

用临时集合，跑完就删 —— 不碰 day020 那 110 条的正式库。
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from llm_service import rag_store

client = TestClient(app)

AUTH_BLOCKS = 30        # routers/auth.py 切出 30 块（day-020 分块对照的实测值）
TMP = "pytest_rag_tmp"


def _drop(name: str) -> None:
    """删集合；名字不存在时忽略（delete_collection 对不存在的会抛 NotFoundError）。"""
    try:
        rag_store.get_client().delete_collection(name)
    except Exception:
        pass


@pytest.fixture
def tmp_col():
    """给一个干净的空集合，用完删掉。"""
    _drop(TMP)          # 先清：上次跑崩可能留下残留
    yield TMP
    _drop(TMP)          # 后清


def test_ingest_forward_slash(tmp_col):
    """正斜杠路径能命中 —— 10-07 的坑，10-10 修好"""
    res = rag_store.ingest(["routers/auth.py"], collection=tmp_col)
    assert res["ingested"] == AUTH_BLOCKS
    assert res["total"] == AUTH_BLOCKS


def test_ingest_backslash(tmp_col):
    """反斜杠是老写法，不能被修坏"""
    res = rag_store.ingest([r"routers\auth.py"], collection=tmp_col)
    assert res["ingested"] == AUTH_BLOCKS


def test_ingest_unknown_path(tmp_col):
    """不存在的路径 → 0 条，而不是抛异常"""
    res = rag_store.ingest(["routers/nope.py"], collection=tmp_col)
    assert res == {"ingested": 0, "total": 0}


def test_ingest_idempotent(tmp_col):
    """同一集合写两次，第二次不重复写"""
    first = rag_store.ingest(["routers/auth.py"], collection=tmp_col)
    second = rag_store.ingest(["routers/auth.py"], collection=tmp_col)
    assert first["ingested"] == AUTH_BLOCKS
    assert second["ingested"] == 0            # 幂等
    assert second["total"] == AUTH_BLOCKS     # 总数没翻倍


def test_ingest_endpoint():
    """HTTP 层返回结构正确（默认集合已满 110 条，所以 ingested=0）"""
    resp = client.post("/rag/ingest", json={"paths": []})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"ingested", "total"}
    assert body["total"] >= 110


# ── t-1263 /rag/query ──────────────────────────────────────────────

AUTH_SRC = r"routers\auth.py"    # 库里 metadata 的真实格式（反斜杠）


def test_query_shape_and_score():
    """返回结构正确，且 score = 1 - 距离（越大越像）。

    这里卡「精确值」而不是「区间」—— 区间判据抓不住方向写反的错：
    score=d 时会得到 0.8578，照样落在 [-1,1] 且 >0.1 里，测试假通过。
    基线来自实测：正确实现首条恰好 0.1422。
    """
    resp = client.post("/rag/query", json={"query": "怎么校验 JWT 令牌", "n": 3})
    assert resp.status_code == 200

    body = resp.json()
    assert set(body) == {"query", "hits"}
    assert body["query"] == "怎么校验 JWT 令牌"
    assert len(body["hits"]) == 3

    hit = body["hits"][0]
    assert set(hit) == {"source", "score", "text"}
    assert isinstance(hit["score"], float)
    assert hit["text"]                       # 原文非空，拼 prompt 要用

    # score = 1 - 距离，范围 [-1, 1]。
    assert -1.0 <= hit["score"] <= 1.0
    # 钉死实测值：写成 score=d 会变成 1-0.1422=0.8578，这里必挂。
    assert hit["score"] == pytest.approx(0.1422, abs=1e-3)
    assert hit["source"] == r"routers\users.py"    # 实测第一名是这个文件（检索质量差，见 t-426）


def test_query_source_filter_forward_slash():
    """传正斜杠要能命中 —— 路由层负责转成库里的反斜杠（10-11 修的）"""
    resp = client.post(
        "/rag/query",
        json={"query": "令牌校验", "n": 3, "source": "routers/auth.py"},
    )
    assert resp.status_code == 200

    hits = resp.json()["hits"]
    assert len(hits) == 3
    assert {h["source"] for h in hits} == {AUTH_SRC}


def test_query_without_source_spans_files():
    """不传 source = 全库检索，结果可以跨文件（对照上一条）"""
    resp = client.post("/rag/query", json={"query": "令牌校验", "n": 3})
    hits = resp.json()["hits"]
    assert len(hits) == 3
    assert len({h["source"] for h in hits}) > 1     # 实测 2 个来源


def test_query_n_param_and_validation():
    """n 生效；n=0 和空 query 交给 pydantic 拦成 422"""
    assert len(client.post("/rag/query", json={"query": "令牌", "n": 1}).json()["hits"]) == 1

    assert client.post("/rag/query", json={"query": "令牌", "n": 0}).status_code == 422
    assert client.post("/rag/query", json={"query": ""}).status_code == 422

