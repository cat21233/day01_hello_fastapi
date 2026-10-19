"""v2 难题集评测：歧义题 / 反向题 / 改写题，量「当前检索的真实短板」。

v1（retrieval_eval.jsonl）已饱和 1.00，失去区分度；v2 的题故意避开语料原词。
跑法：
    python eval/run_eval_v2.py            # 全部
    python eval/run_eval_v2.py -k h01     # 只看某题
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_service.rag_store import get_collection, get_model  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTION = os.environ.get("RAG_COLLECTION", "day020")
N = 5


def norm(s: str) -> str:
    return (s or "").replace("\\", "/")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", default=None, help="只跑指定 id")
    args = ap.parse_args()

    rows = [
        json.loads(line)
        for line in open(os.path.join(HERE, "retrieval_eval_v2.jsonl"), encoding="utf-8")
        if line.strip()
    ]
    if args.k:
        rows = [r for r in rows if r["id"] == args.k]

    col = get_collection(COLLECTION)
    model = get_model()

    hit1 = hit3 = 0
    for r in rows:
        vec = model.encode(r["query"], normalize_embeddings=True).tolist()
        res = col.query(query_embeddings=[vec], n_results=N)
        metas = [norm(m.get("source")) for m in res["metadatas"][0]]
        dists = res["distances"][0]
        expect = {norm(s) for s in r["expected_sources"]}
        rank = next((i for i, m in enumerate(metas, start=1) if m in expect), None)
        ok1, ok3 = rank == 1, rank is not None and rank <= 3
        hit1 += ok1
        hit3 += ok3
        flag = "OK  " if ok1 else (f"top{rank}" if rank else "MISS")
        print(f"{flag} [{r['difficulty']}] {r['id']} {r['query']}")
        if not ok1:
            print(f"       期望={sorted(expect)}")
            for i, (m, d) in enumerate(zip(metas, dists), start=1):
                mark = " <== 期望" if m in expect else ""
                print(f"       {i}. {m:26} cos={1 - d / 2:.4f}{mark}")

    n = len(rows)
    print()
    print(f"v2 难题集（{COLLECTION}，n={n}）: top1 {hit1}/{n} = {hit1 / n:.2f}    top3 {hit3}/{n} = {hit3 / n:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
