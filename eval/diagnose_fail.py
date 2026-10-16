"""FAIL 诊断：把全库排一遍，看目标文件最好的一块排第几。

为什么要单独一个脚本 —— 它和 run_baseline.py 是两个工种：
    run_baseline.py   全卷打分（20 题），要反复跑做回归，得快
    diagnose_fail.py  单题深挖（4 题 × 全库 110 块），一次性诊断，慢无所谓

诊断要回答的问题：「目标文件排第几名？」不同名次对应不同的药：
    排进前 5         → 差一口气，rerank 就能捞回来
    排到 50 / 110    → 被淹了，得靠关键词检索（BM25）补
    None（全库都没） → 不是排序问题，是分块 / 语料的问题

用法（项目根目录）：
    .venv\\Scripts\\python.exe eval\\diagnose_fail.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from llm_service.rag_store import get_collection, search  # noqa: E402

EVAL_FILE = pathlib.Path(__file__).with_name("retrieval_eval.jsonl")

# 上一轮基线（n=3 口径）挂掉的 4 道
FAIL_IDS = ["q05", "q07", "q11", "q20"]


def norm(p: str) -> str:
    """库里存反斜杠，评测集写正斜杠，比较前统一。"""
    return p.replace("\\", "/")


def diagnose(case: dict) -> int | None:
    """把全库排一遍，返回目标文件第一次出现的名次（从 1 数）；没出现返回 None。"""
    total = get_collection().count()
    # 提示：Chroma 的 n_results 不能超过库里总数，所以别写死 110，用上面算出来的。

    raw = search(case["query"], n=total)          # ← ① 填什么？
    got = [norm(m["source"]) for m in raw["metadatas"][0]]
    want = set(case["expected_sources"])

    for rank, src in enumerate(iterable=got, start=1):                      # ← ② 填什么？
        if src in want:                          #    要同时拿到「名次」和「文件名」，
            return rank                          #    而且名次要真从 1 数起
    return None


def main() -> None:
    cases = {}
    for line in EVAL_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            cases[obj["id"]] = obj

    for qid in FAIL_IDS:
        case = cases[qid]
        print(f"{qid}  期望 = {case['expected_sources']}")
        print(f"      目标文件最高名次 = {diagnose(case)}")
        print()


if __name__ == "__main__":
    main()
