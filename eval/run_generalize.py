"""泛化集评测：用「题库里没有的新问法」检验 docstring 是否真的建立了语义层。

为什么需要它：如果 docstring 直接抄了 retrieval_eval.jsonl 的措辞，
recall 会涨，但涨的是"背答案"。只有从未出现过的问法也能命中，
才说明向量空间里真的连上了意思。

用法：
    python eval/run_generalize.py              # 跑全部
    python eval/run_generalize.py --round 2    # 只跑第 2 轮新增的

维护约定（很重要）：
    每次给新文件补 docstring 后，**追加**几条新问法并标新 round，不要修改老条目。
    老条目一旦被用来调 docstring 就失去"held-out"意义，只能当回归测试用。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_service.rag_store import get_collection, get_model  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTION = os.environ.get("RAG_COLLECTION", "day020")


def norm(s: str) -> str:
    """metadata 里是 routers\\llm.py，题库写 routers/llm.py，统一成分隔符无关的形式。"""
    return (s or "").replace("\\", "/")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=None, help="只跑指定轮次")
    ap.add_argument("--n", type=int, default=5, help="取前 n 名判断命中")
    args = ap.parse_args()

    rows = [
        json.loads(line)
        for line in open(os.path.join(HERE, "generalize_set.jsonl"), encoding="utf-8")
        if line.strip()
    ]
    if args.round is not None:
        rows = [r for r in rows if r.get("round") == args.round]

    col = get_collection(COLLECTION)
    model = get_model()

    hit1 = hit_n = 0
    for r in rows:
        vec = model.encode(r["query"], normalize_embeddings=True).tolist()
        res = col.query(query_embeddings=[vec], n_results=args.n)
        metas = res["metadatas"][0]
        dists = res["distances"][0]
        expect = {norm(s) for s in r["expected_sources"]}
        rank = next(
            (i for i, m in enumerate(metas, start=1) if norm(m.get("source")) in expect),
            None,
        )
        top1_src = norm(metas[0].get("source")) if metas else "-"
        ok1 = rank == 1
        hit1 += ok1
        hit_n += rank is not None
        flag = "OK  " if ok1 else ("top%d" % args.n if rank else "MISS")
        print(f"{flag} r{r.get('round')} {r['id']} {r['query']}")
        print(f"       期望={sorted(expect)} 名次={rank or '>%d' % args.n} 首位={top1_src}")

    n = len(rows)
    print()
    print(f"泛化集（{COLLECTION}，n={n}）: top1 命中 {hit1}/{n} = {hit1 / n:.2f}"
          f"    top{args.n} 命中 {hit_n}/{n} = {hit_n / n:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
