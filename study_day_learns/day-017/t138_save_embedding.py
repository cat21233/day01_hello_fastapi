# t138_save_embedding.py
# 本地 Embedding 的持久化：把向量存文件、再读回验证（t-138）
# 流程: 编码 → 存 JSON → 读回验证 → 存 NPY → 读回验证
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # 项目根（脚本在 study_day_learns/day-017/ 下，向上 3 级）
HERE = Path(__file__).resolve().parent       # 本脚本所在目录 day-017/，数据存这里
MODEL_DIR = str(ROOT / "models" / "bge-small-zh-v1.5")

import json
import numpy as np
from sentence_transformers import SentenceTransformer

# ---------- ① 加载模型（与 t134 相同，本地路径） ----------
print("[1] 加载本地 BGE 模型...")
model = SentenceTransformer(MODEL_DIR)

texts = ["我喜欢吃苹果", "我喜欢吃水果", "汽车在公路上行驶"]
embs = model.encode(texts, normalize_embeddings=True)   # (3, 512) ndarray
print(f"    编码完成: {embs.shape}, dtype={embs.dtype}")

# ---------- ② 存 JSON：把 句子+向量 配对 ----------
# ndarray 不能直接 json.dump → 每行 .tolist() 转成 Python list
records = []
for i, text in enumerate(texts):
    records.append({"text": text, "embedding": embs[i].tolist()})

json_path = HERE / "embeddings_store.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)   # ensure_ascii=False 中文可读
print(f"[2] JSON 已存: {json_path}")

# ---------- ③ 读回 JSON 并验证 ----------
with open(json_path, encoding="utf-8") as f:
    loaded = json.load(f)

print("[3] JSON 读回验证:")
for i, rec in enumerate(loaded):
    restored = np.array(rec["embedding"])               # list → ndarray
    same = np.allclose(restored, embs[i])               # 浮点比较用 allclose
    print(f"    [{i}] {rec['text']} -> 一致? {same}")

# ---------- ④ 加分: NPY 二进制 ----------
npy_path = HERE / "embeddings_store.npy"
np.save(npy_path, embs)                                  # 整个矩阵一次存
arr = np.load(npy_path)                                  # 读回
print(f"[4] NPY 存/读: {npy_path}")
print(f"    形状一致? {arr.shape == embs.shape}, 数值一致? {np.allclose(arr, embs)}")

print("\n完成：向量已持久化到 JSON（可读）+ NPY（紧凑二进制）")
