"""检索基线测量：拿 eval/retrieval_eval.jsonl 当考卷，跑一遍现在的检索，算出命中率。

这就是评测集的用途 —— 把「感觉准了点」变成数字。
M1 做完混合检索 / rerank 之后，同一个文件再跑一次，两个数字一比就是提升证据。

用法（项目根目录）：
    .venv\\Scripts\\python.exe eval\\run_baseline.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from llm_service.rag_store import search  # noqa: E402

EVAL_FILE = pathlib.Path(__file__).with_name("retrieval_eval.jsonl")


def norm(p: str) -> str:
    """库里存的是反斜杠（routers\\auth.py），评测集写正斜杠，比较前统一。"""
    return p.replace("\\", "/")


# ⚠️ 口径：这个 collection 建库时没传 metadata → Chroma 用默认 l2 空间，
#    而向量都做了归一化 → d = 2 - 2·cos，所以 cos = 1 - d/2。
#    直接写 `1 - d` 得到的不是相似度，是 2·cos - 1（会出现负数，看着像乱码）。
#    若以后把库改成 cosine 空间（建库时 metadata={"hnsw:space": "cosine"}），
#    这里必须同步改成 cos = 1 - d，否则数字又会说谎。
L2_SPACE = True


def to_cos(d: float) -> float:
    """把 Chroma 的 distance 换算成真正的余弦相似度。"""
    return 1 - d / 2 if L2_SPACE else 1 - d


def main() -> None:
    cases = [
        json.loads(line)
        for line in EVAL_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(f"共 {len(cases)} 题\n")

    # 取 5 条候选：多留 2 条是给 M1 的 rerank 看的（重排是在候选池里重排）。
    # 但每个「指标」必须自己切片 —— recall@3 只看 got[:3]，切片跟着指标名走，
    # 这样即使以后把 TOP_N 调大，recall@3 也不会偷偷变成「Top-N 命中率」。
    TOP_N = 5
    hits = {k: 0 for k in (1, 3, 5)}
    for c in cases:
        raw = search(c["query"], n=TOP_N)
        got = [norm(m["source"]) for m in raw["metadatas"][0]]
        scores = [round(to_cos(d), 4) for d in raw["distances"][0]]

        want = set(c["expected_sources"])
        for k in hits:
            if any(g in want for g in got[:k]):
                hits[k] += 1

        mark = "PASS" if any(g in want for g in got[:3]) else "FAIL"
        print(f"[{mark}] {c['id']} ({c['difficulty']}) {c['query']}")
        print(f"      期望: {sorted(want)}")
        for g, s in zip(got, scores):
            flag = "  <-- 命中" if g in want else ""
            print(f"      实得: {g}  cos={s}{flag}")
        print()

    n = len(cases)
    print("=" * 50)
    for k in (1, 3, 5):
        print(f"recall@{k} = {hits[k]}/{n} = {hits[k] / n:.2f}")


if __name__ == "__main__":
    main()
