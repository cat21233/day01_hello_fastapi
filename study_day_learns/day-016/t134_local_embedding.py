# t134_local_embedding.py
# 本地离线 Embedding（t-134）+ 余弦相似度（t-135）
# 用 sentence-transformers + BGE 中文小模型，完全本地、免费、离线
# 注意：模型已手动下载到项目 models/ 下（WorkBuddy 沙箱会拦截 huggingface 的
#       临时文件清理导致自动下载失败，详见 9-03 笔记）
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # 项目根（脚本在 study_day_learns/day-016/ 下，向上 3 级）
MODEL_DIR = str(ROOT / "models" / "bge-small-zh-v1.5")

import numpy as np
from sentence_transformers import SentenceTransformer

# ============ t-134: 文本 -> 向量 ============
print(f"[1/3] 加载本地 BGE 中文模型: {MODEL_DIR}")
model = SentenceTransformer(MODEL_DIR)

texts = ["我喜欢吃苹果", "我喜欢吃水果", "汽车在公路上行驶"]
# normalize_embeddings=True 会把向量归一化成单位长度
# 归一化后：余弦相似度 = 向量点积（省一次除法，是 RAG 里的标准操作）
embs = model.encode(texts, normalize_embeddings=True)

print(f"向量维度: {embs.shape}")   # (3, 512) → 3 句话，每句 512 维
for i, t in enumerate(texts):
    print(f"  句子[{i}] {t}")
    print(f"    前5个数字: {embs[i][:5]}")
    print(f"    向量长度(|v|): {np.linalg.norm(embs[i]):.4f}")  # 归一化后≈1

# ============ t-135: 余弦相似度 ============
print("\n[2/3] 余弦相似度（归一化后 = 点积）...")

def cos_sim(a, b):
    """余弦相似度：a·b / (|a|*|b|)。已归一化，|a|=|b|=1，所以直接点积"""
    return float(np.dot(a, b))

print(f"  苹果 vs 水果: {cos_sim(embs[0], embs[1]):.4f}  ← 语义相近，应该接近 1")
print(f"  苹果 vs 汽车: {cos_sim(embs[0], embs[2]):.4f}  ← 语义无关，应该明显更低")

# ============ 加分：找最相似的一对 ============
print("\n[3/3] 验证：三句话里谁和'我喜欢吃苹果'最像？")
scores = [(t, cos_sim(embs[0], embs[j])) for j, t in enumerate(texts) if j != 0]
best = max(scores, key=lambda x: x[1])
print(f"  最相似的: {best[0]} (相似度 {best[1]:.4f})  ← 应该是'我喜欢吃水果'")
