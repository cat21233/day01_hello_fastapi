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

# routers/auth.py 切出的块数。这是**语料快照**：改了 auth.py 的任何一行
# （含模块 docstring），chunk_size=200 会整体重排，这个数必须重新量。
# 量法：python -c "from llm_service import rag_store; ..." 或看 _probe_split 输出。
# 2026-10-18：补 docstring 后 30 → 37。
AUTH_BLOCKS = 37
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

    原来是钉死一个精确值（0.1422），但那是**语料快照**：
    补一次 docstring 检索结果就整体重排，精确值立刻失效 → 测试变噪音。
    现改成用「相关问句 vs 无关问句」的**符号关系**来判方向，
    对语料改动免疫，同时对两种写反都致命：

      score = d      → 无关问句变成正数（实测 +1.368），far < 0 挂
      score = -d     → 相关问句变成负数（实测 -0.510），near > 0 挂
      score = 1 - d  → near=0.4897, far=-0.3680，全过 ✅（当前实现）
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
    assert hit["source"].endswith(".py")     # 来源必须是语料文件，不能是空串/路径串错

    # 范围 [-1, 1]
    assert -1.0 <= hit["score"] <= 1.0

    scores = [h["score"] for h in body["hits"]]

    # 方向判据：相关问句为正、无关问句为负（不依赖语料，只依赖语义）
    near = scores[0]
    far = client.post(
        "/rag/query", json={"query": "今天重庆天气怎么样", "n": 1}
    ).json()["hits"][0]["score"]
    assert near > 0, f"相关问句得分应为正，实测 {near}"
    assert far < 0, f"无关问句得分应为负，实测 {far}"
    assert near - far > 0.3, f"相关性差距过小：near={near} far={far}"

    # 排名必须严格按 score 从高到低（放在方向判据之后，
    # 否则 score=d 时会在这一行先挂，掩盖掉真正的方向错误信息）
    assert scores == sorted(scores, reverse=True)


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


def test_query_without_source_searches_whole_library():
    """不传 source = 全库检索（对照上一条：传了 source 就只剩那一个文件）。

    原来的判据是「同一问句的 3 条来源跨 ≥2 个文件」，但那是**检索质量差**的
    副作用：auth.py 一治理（37 块），"令牌校验" 的前 3 名全落在 auth.py 里，
    这个断言就失效了。用「问商品的事却要能在 items.py 找到」来判，
    才真正证明「没有加过滤条件」——如果路由层偷偷默认只查 auth.py，必挂。
    """
    resp = client.post("/rag/query", json={"query": "删除商品需要管理员吗", "n": 3})
    assert resp.status_code == 200

    hits = resp.json()["hits"]
    assert len(hits) == 3
    assert hits[0]["source"] == r"routers\items.py"   # 实测首条 0.1095
    assert {h["source"] for h in hits} != {AUTH_SRC}  # 没有被限制在 auth.py


def test_query_n_param_and_validation():
    """n 生效；n=0 和空 query 交给 pydantic 拦成 422"""
    assert len(client.post("/rag/query", json={"query": "令牌", "n": 1}).json()["hits"]) == 1

    assert client.post("/rag/query", json={"query": "令牌", "n": 0}).status_code == 422
    assert client.post("/rag/query", json={"query": ""}).status_code == 422

