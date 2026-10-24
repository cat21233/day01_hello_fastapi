"""hybrid 评测：向量检索 + BM25 的 RRF 融合，一把跑出三组数。

RRF（Reciprocal Rank Fusion）：只看名次，不看分数——
    融合分(doc) = Σ 1/(K + 名次)     名次从 1 起，K=60（论文经验值）
两路各取前 10，分数相加后重排。好处：不用管两路分数量纲（余弦和 BM25 分不可比）。

跑法：
    python eval/run_eval_hybrid.py                 # v2 难题集
    python eval/run_eval_hybrid.py --set generalize  # 泛化集
    python eval/run_eval_hybrid.py -k h03          # 只看某题
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.bm25_lite import build, rank as bm25_rank  # noqa: E402
from llm_service.rag_store import get_collection, get_model  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTION = os.environ.get("RAG_COLLECTION", "day020")
DEPTH = 10   # 每路取前多少名参与融合
K = 60       # RRF 常数


def norm(s: str) -> str:
    return (s or "").replace("\\", "/")


def rrf_fuse(order_a: list, order_b: list, k: int = K) -> list:
    """两路名次融合。order_x 是文档下标列表，已按各自分数降序。"""
    scores: dict = {}
    for r, i in enumerate(order_a, start=1):
        scores[i] = scores.get(i, 0.0) + 1.0 / (k + r)
    for r, i in enumerate(order_b, start=1):
        scores[i] = scores.get(i, 0.0) + 1.0 / (k + r)
    return [i for i, _ in sorted(scores.items(), key=lambda x: -x[1])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", default=None, help="只跑指定 id")
    ap.add_argument("--set", default="v2", choices=["v2", "generalize"], help="用哪把尺子")
    args = ap.parse_args()

    eval_file = "retrieval_eval_v2.jsonl" if args.set == "v2" else "generalize_set.jsonl"
    rows = [
        json.loads(line)
        for line in open(os.path.join(HERE, eval_file), encoding="utf-8")
        if line.strip()
    ]
    if args.k:
        rows = [r for r in rows if r["id"] == args.k]

    col = get_collection(COLLECTION)
    model = get_model()

    got = col.get(include=["documents", "metadatas"])
    docs, metas = got["documents"], got["metadatas"]
    id2pos = {doc_id: p for p, doc_id in enumerate(got["ids"])}
    index = build(docs)
    sources = [norm(m.get("source")) for m in metas]

    tally = {"vec": [0, 0], "bm25": [0, 0], "hyb": [0, 0]}  # [top1, top3]

    for r in rows:
        expect = {norm(s) for s in r["expected_sources"]}

        # 路 1：向量
        vec = model.encode(r["query"], normalize_embeddings=True).tolist()
        res = col.query(query_embeddings=[vec], n_results=DEPTH)
        vec_order = [id2pos[i] for i in res["ids"][0]]

        # 路 2：BM25（只留 score>0，天然没命中就没名次）
        bm25_order = [i for i, _ in bm25_rank(index, r["query"])[:DEPTH]]

        hyb_order = rrf_fuse(vec_order, bm25_order)

        def rank_of(order):
            for pos, i in enumerate(order, start=1):
                if sources[i] in expect:
                    return pos
            return None

        rv, rb, rh = rank_of(vec_order), rank_of(bm25_order), rank_of(hyb_order)
        for key, rk in (("vec", rv), ("bm25", rb), ("hyb", rh)):
            tally[key][0] += rk == 1
            tally[key][1] += rk is not None and rk <= 3

        mark = lambda rk: "OK  " if rk == 1 else (f"top{rk}" if rk else "MISS")
        print(f"{mark(rv)} | {mark(rb)} | {mark(rh)}  [{r.get('difficulty', '-')}] {r['id']} {r['query']}")
        if args.k:
            print(f"       向量前3: {[sources[i] for i in vec_order[:3]]}")
            print(f"       BM25 前3: {[sources[i] for i in bm25_order[:3]]}")

    n = len(rows)
    print()
    print(f"{args.set}（{COLLECTION}，n={n}，融合深度 {DEPTH}，K={K}）")
    for key, name in (("vec", "纯向量"), ("bm25", "纯 BM25"), ("hyb", "hybrid 融合")):
        h1, h3 = tally[key]
        print(f"  {name:8} top1 {h1}/{n} = {h1 / n:.2f}    top3 {h3}/{n} = {h3 / n:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
