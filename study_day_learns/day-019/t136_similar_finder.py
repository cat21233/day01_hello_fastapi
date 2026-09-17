# day-019/t136_similar_finder.py —— 相似句查找小工具（mini RAG 雏形，t-136）
# 数据流：读库 -> 加载模型 -> 查询编码 -> 逐一算余弦 -> 排序 top-3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))   # day-XXX 子目录里必须手动加项目根，才能找到 models/

import numpy as np
from sentence_transformers import SentenceTransformer

# ===== 阶段一：库（day-017 已做好，只读取）=====
STORE = Path(__file__).resolve().parent.parent / "day-017" / "embeddings_store.json"
with open(STORE, encoding="utf-8") as f:
    records = json.load(f)

# ⬜ TODO 1：从 records 里取出所有 text，放进 texts 列表（一行列表推导）
texts = [r["text"] for r in records]

# 向量矩阵：(3, 512)，第 i 行就是 texts[i] 的向量
vectors = np.array([r["embedding"] for r in records])
print(f"库里有 {len(texts)} 条向量, 形状 {vectors.shape}")

# ===== 阶段二：查询 =====
MODEL_DIR = str(ROOT / "models" / "bge-small-zh-v1.5")
print("加载模型中...")
model = SentenceTransformer(MODEL_DIR)

query = input("\n输入一句话: ")

# ⬜ TODO 2：把 [query] 编码成向量
#    提示：model.encode(列表, normalize_embeddings=True) 返回 shape (1, 512)
#    记得用 [0] 取出那一条，变成 (512,)
q_vec = model.encode([query],normalize_embeddings=True)[0]



# ⬜ TODO 3：默写 cosine 函数（t-133 你闭卷写过的，就 2~3 行：np.dot / np.linalg.norm）
def cosine(a, b):
    cosine_reason = np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b))
    return cosine_reason

# ⬜ TODO 4：算 query 和库内每条向量的相似度
#    提示：列表推导 + enumerate，得到 [(text, 分数), ...]，如
scores = [(t, cosine(q_vec, vectors[i])) for i, t in enumerate(texts)]

# ⬜ TODO 5：按分数从高到低排序
#    词典：sorted(列表, key=lambda x: x[1], reverse=True)
scores_sorted = sorted(scores, key=lambda x: x[1], reverse=True)
# ⬜ TODO 6：打印 top-3（序号 + 分数 + 句子），格式随意但要能看出排名
print(f"\n「{query}」的 top-3 相似句:")
for rank, (text, score) in enumerate(scores_sorted[:3], start=1):
    print(f"  {rank}. [{score:.4f}] {text}")

