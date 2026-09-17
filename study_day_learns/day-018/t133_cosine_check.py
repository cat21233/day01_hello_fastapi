# study_day_learns/day-018/t133_cosine_check.py
import json
from pathlib import Path
import numpy as np

# ---- 数据读取（已写好，读懂每行注释即可）----
STORE = Path(__file__).resolve().parent.parent / "day-017" / "embeddings_store.json"
with open(STORE, encoding="utf-8") as f:
    data = json.load(f)          # data = [{"text": "...", "embedding": [512个float]}, x3]

texts = [item["text"] for item in data]                # 取每条的文本 → ["我喜欢吃苹果", ...]
vectors = np.array([item["embedding"] for item in data])  # 取每条向量 → shape (3, 512)
# vectors 是矩阵：3 行 = 3 条文本；vectors[0] 是第一行 = "我喜欢吃苹果" 的 512 维向量

# ---- ⬜ 你的任务 1：写 cosine 函数（就 2~3 行）----
def cosine(a, b):
    """
    参数：a、b 是一维 ndarray（各是一条文本的 512 维向量）
    返回：余弦相似度 = (a·b) / (|a|·|b|)
    numpy 词典：
      点积   -> np.dot(a, b)
      模长   -> np.linalg.norm(a)
    """
    cos_sin = np.dot(a, b)/(np.linalg.norm(a)*np.linalg.norm(b))
    return cos_sin
    # 你的代码：把上面公式翻译成 return 语句


# ---- ⬜ 你的任务 2：打印三对相似度（示范第 1 对，其余自己写）----

# ⬜ 补：水果 vs 汽车（第 1 行 vs 第 2 行）


# ---- ⬜ 你的任务 3：验证相对关系 ----
# 要求：苹果vs水果 必须大于 苹果vs汽车。
# 用 if + 打印 PASS/FAIL（不许抄上面对比输出，要写成判断）
# 先用变量接住三对返回值（名字自己起，语义要能看懂）
sim_apple_fruit = cosine(vectors[0], vectors[1])
# ⬜ 照这两行的样子，补 苹果vs汽车 和 水果vs汽车
sim_apple_car = cosine(vectors[0], vectors[2])

# 打印改用变量（代替任务2原来的三行 print）
print("苹果vs水果:", sim_apple_fruit)
print("苹果vs汽车:", sim_apple_car)
print("水果vs汽车:", cosine(vectors[1], vectors[2]))

# # 判断
if sim_apple_fruit > sim_apple_car:
    print("PASS")
else:
    print("FAIL")   # ⬜ 顺手写行注释：如果 FAIL，你猜最可能的原因是什么？

# ---- ⬜ 你的任务 4（加分）：归一化后点积 == 余弦 ----
# 归一化：unit = v / np.linalg.norm(v)   （把向量缩到模长=1）
# 验证：np.allclose(np.dot(unit_a, unit_b), cosine(a, b))  → 打印结果
# 想通它：模长=1 时 |a|·|b| = 1，cos 就退化成点积
unit_a = vectors[0]/np.linalg.norm(vectors[0])
unit_b = vectors[1]/np.linalg.norm(vectors[1])
print(np.allclose(np.dot(unit_a, unit_b), cosine(vectors[0], vectors[1])))