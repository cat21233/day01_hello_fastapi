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


def main() -> None:
    cases = [
        json.loads(line)
        for line in EVAL_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print(f"共 {len(cases)} 题\n")

    top1_hit = top3_hit = 0
    for c in cases:
        raw = search(c["query"], n=3)
        got = [norm(m["source"]) for m in raw["metadatas"][0]]
        scores = [round(1 - d, 4) for d in raw["distances"][0]]

        want = set(c["expected_sources"])
        hit1 = got[0] in want
        hit3 = any(g in want for g in got)
        top1_hit += hit1
        top3_hit += hit3

        mark = "PASS" if hit3 else "FAIL"
        print(f"[{mark}] {c['id']} ({c['difficulty']}) {c['query']}")
        print(f"      期望: {sorted(want)}")
        for g, s in zip(got, scores):
            flag = "  <-- 命中" if g in want else ""
            print(f"      实得: {g}  score={s}{flag}")
        print()

    n = len(cases)
    print("=" * 50)
    print(f"recall@1 = {top1_hit}/{n} = {top1_hit / n:.2f}")
    print(f"recall@3 = {top3_hit}/{n} = {top3_hit / n:.2f}")


if __name__ == "__main__":
    main()
