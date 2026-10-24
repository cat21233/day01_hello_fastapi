"""字符 bigram + BM25 最小实现（零依赖：re / math / collections）。

用途：给 day020 补一路「字面匹配」，之后与向量检索融合成 hybrid。
    python eval/bm25_lite.py --selftest   # toy 三篇，验公式
    python eval/bm25_lite.py --corpus     # 真实语料统计
    python eval/bm25_lite.py --check      # 相关 / 无关判别
"""
import collections
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CJK = re.compile(r"[\u4e00-\u9fff]+")          # 连续汉字段
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")   # 英文 / 标识符

TOY = ["db pool timeout", "db pool pool pool", "cache expire"]


def tokenize(text: str) -> list[str]:
    """英文按单词转小写；中文按「段内 2 字滑窗」。返回列表保留重复。"""
    out = []
    # ===== BLANK 1：往 out 里塞 token，约 5 行 =====
    for w in WORD.findall(text):
        out.append(w.lower())
    for seg in CJK.findall(text):
        for i in range(len(seg)-1):
            out.append(seg[i:i+2])
    return out


def build(docs: list[str]) -> dict:
    """建索引，返回：
        {"n": 文档数, "avgdl": 平均长度,
         "dfs": {token: 含该 token 的文档数},
         "tfs": [{token: 次数}, ...],   # 下标 = 文档下标
         "dls": [每篇 token 总数, ...]}

    dfs 数「有几篇含它」，不是「总次数」—— 最常见错点。
    """
    tfs, dls = [], []
    dfs = collections.Counter()
    for d in docs:
        # ===== BLANK 2：算这篇的 toks / c / dls / tfs / dfs，约 6 行 =====
        toks = tokenize(d)
        c = collections.Counter(toks)
        dls.append(len(toks))
        tfs.append(dict(c))
        for t in c:
            dfs[t] += 1

    n = len(docs)
    return {
        "n": n,
        "avgdl": (sum(dls) / n if n else 0.0),
        "dfs": dict(dfs),
        "tfs": tfs,
        "dls": dls,
    }


def rank(index: dict, query: str, k1: float = 1.2, b: float = 0.75):
    """返回 [(文档下标, 分数)]，按分数降序，只留 score > 0。"""
    qt = tokenize(query)
    if not qt or index["n"] == 0:
        return []
    n, avgdl = index["n"], index["avgdl"]
    out = []
    for i, tf_map in enumerate(index["tfs"]):
        norm = 1 - b + b * index["dls"][i] / avgdl
        s = 0.0
        # ===== BLANK 3：对 qt 里每个 token 累加分数，约 8 行 =====
        for t in qt:
            tf = tf_map.get(t,0)
            if tf == 0:
                continue
            df = index["dfs"][t]
            idf = math.log((n-df+0.5)/(df+0.5)+1,math.e)
            s += idf*tf*(k1+1)/(tf+k1*norm)
        if s > 0:

            out.append((i, s))
    out.sort(key=lambda x: -x[1])
    return out


def main() -> int:
    args = set(sys.argv[1:])

    if "--selftest" in args:
        idx = build(TOY)
        print(f"N = {idx['n']}   avgdl = {idx['avgdl']}   df(pool) = {idx['dfs'].get('pool')}")
        for i, s in rank(idx, "pool"):
            print(f"D{i + 1} score = {s:.4f}")
        return 0

    if "--corpus" in args:
        from llm_service.rag_store import get_collection
        docs = get_collection("day020").get(include=["documents"])["documents"]
        idx = build(docs)
        print(f"N = {idx['n']}   词表 = {len(idx['dfs'])}   avgdl = {idx['avgdl']:.2f}")
        print(f"df(def) = {idx['dfs'].get('def')}   df(限流) = {idx['dfs'].get('限流')}")
        return 0

    if "--check" in args:
        from llm_service.rag_store import get_collection
        got = get_collection("day020").get(include=["documents", "metadatas"])
        docs, metas = got["documents"], got["metadatas"]
        idx = build(docs)
        for q in ["苹果手机的电池续航", "梅西退役了吗", "限流怎么配的"]:
            r = rank(idx, q)
            top = f"{metas[r[0][0]]['source']:26} score={r[0][1]:.4f}" if r else "空"
            print(f"{q:14} -> 命中 {len(r):3} 条   top1 = {top}")
        return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
