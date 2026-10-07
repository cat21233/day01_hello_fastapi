# Chroma 向量库 · 速查卡（建库 + 检索 + metadata 过滤）

> day-020（2026-10-07）· stage-2 RAG 地基 · 明天做 rerank / bind_tools 前扫一眼
> 背景：接 10-06 分块三块（D 块）。今天把 110 条向量真正放进库并查出来。
> 产出：`llm_service/_probe_chroma.py`（探针，不进版本库）+ `.chroma_probe/`（本地库，不进版本库）
> 判据实测：D1=110 条 / D2两组各 3 条 / **D3=3 条全 `routers\auth.py`** / **D4=0 条**

---

## Chroma 是什么

**是一个向量数据库。** 只干两件事：存向量+ 算「谁离我最近」，附带一层 SQL 风格的 `where` 过滤。

| | MySQL | Chroma |
|---|---|---|
| 查什么 | `WHERE id = 3` 精确匹配 | 「谁最像这个向量」 |
| 命中与否 | 命中 / 不命中 | **永远返回 top-k**，每条带距离分 |
| 存什么 | 行 | 向量 + 原文 + metadata |

**一句话**：Chroma = 只干「存向量 + 算谁最近」的数据库。

---

## 链路上的位置

```
离线入库（探针 D1/D2 跑的就是这段）
routers/*.py → 分块 110 块 → BGE 512 维 → 【向量库 Chroma 存+查】

在线检索
用户提问 → 同一嵌入模型 → 问题变向量 → 【向量库找最像的 k 块】 → 拼回原文块送 LLM
```

**关键：两段必须用同一个嵌入模型。** 换了模型向量空间就对不上，检索结果全是垃圾。

---

## 词 1 · `query()` 的返回是三层嵌套

```python
r["metadatas"]              # list，长度 = query 个数
r["metadatas"][0]           # list，长度 = top-k 条
r["metadatas"][0][0]# dict ← 键在这一层！
# {'source': 'routers\\auth.py', 'idx': 0}
```

| 栏 | 内容 |
|---|---|
| 写法错误 | `r["metadatas"][0]["source"]` |
| 症状 | `TypeError: list indices must be integers or slices, not str` |
| 正确 | `[m["source"] for m in r["metadatas"][0]]` |
| 根因 | 你少了一层括号。`[0]` 之后是 list 不是 dict |

`ids` / `distances` / `documents` 结构完全一致：`r["ids"][0]`、`r["distances"][0]`。

---

## 词 2 · `where` 语法，`$eq` 不能省

```python
where={"source": {"$eq": "routers\\auth.py"}}   # ✅
where={"source": {"routers\\auth.py"}}          # ❌
```

| 栏 | 内容 |
|---|---|
| 症状 | 写错**不报错，静默返回 0 条** |
| 根因 | `{"routers\\auth.py"}` 少冒号 → Python 当成 **set（集合）**，不是 dict |
| 修法 | 补`$eq:` |
| 其他操作符 | `$ne`（不等于）、`$gt` / `$lt`、`$in`（在列表里）、`$and` / `$or` 组合 |

**`$eq` 必须写。** 别指望 `where={"source": "xxx"}` 能work。

---

## 词 3 · `distances` 是余弦距离，范围 0~2

```
distances = 1 - cos_sim     越小越像
```

| | 含义 | 越像的值 | 取值范围 |
|---|---|---|---|
| `distances` | 余弦距离 | **越小** | **[0, 2]**（归一化后） |
| 相似度 / dot product | 你在分块 C 手算的那个 | **越大** | [0, 1] |

- `dist = 0` → 方向完全相同
- `dist = 1` → 垂直，正交，毫无关系
- `dist = 2` → 完全相反

**看到 1.02 不是算错。** 别看到 >1 就以为爆了。

---

## 词 4 · 必须用 `query_embeddings`，不能用 `query_texts`

```python
qe = MODEL.encode([query], normalize_embeddings=True).tolist()
col.query(query_embeddings=qe, n_results=n, where=where)   # ✅
col.query(query_texts=query, n_results=n)                  # ❌
```

| 栏 | 内容 |
|---|---|
| 症状 | `InvalidArgumentError`（维度对不上） |
| 根因 | `query_texts` 会触发 Chroma **自带默认模型**（384 维 all-MiniLM-L6）下载，而本库是 BGE 512 维 |
| 本质 | **向量库只认维度**。512 维的库塞进 384 维查询 → 拒绝服务 |

---

## 词 5 · Windows 路径的反斜杠（第 3 次撞这个）

```
"routers\auth.py"     ❌ \a = BEL 响铃符 → repr 显示 routers\x07uth.py，len 14
"routers\\auth.py"    ✅ 一个真反斜杠      → repr 显示 routers\\auth.py，  len 15
r"routers\auth.py"    ✅ raw string，推荐
```

**metadata 里存的是 Windows 反斜杠**（因为 `str(Path)` 在 Windows 上就是反斜杠），所以：

```python
where={"source": {"$eq": "routers\\auth.py"}}   # ✅ 3 条
where={"source": {"$eq": "routers/auth.py"}}   # ❌ 0 条
```

`\a` `\t` `\n` `\r` 都是Python 认识的转义序列，Windows 路径撞上就完蛋。
**验字符串的招**：`print(repr(s), len(s))` —— repr 出现 `\\` 是对的，出现 `\x07` 就是被吃了。

---

## 词 6 · `where` 只缩小候选池，**不改分数**（实测）

直觉误区：以为「加了过滤 → 结果更差 → 过滤把向量算坏了」。实测证明不是：

```
全局 110 条排名：(0, 1.1829, auth.py) (1, 1.1861, auth.py) (2, 1.1963, llm.py)
                (3, 1.1980, llm.py)   (4, 1.2002, auth.py)
D3 过滤后      ：[1.1829, 1.1861, 1.2002]   ← 正好是全局第 0、1、4 名
```

**分毫不差。** `where` = 「先划候选范围，再在里面排序」，不是「排完再筛」。

---

## 词 7 · 假阳性：过滤 ≠ 正确

| 查询 | 最佳距离 | 换算相似度 |
|---|---|---|
| `怎么校验 JWT 令牌` | 0.8578 | 0.14 |
| `令牌校验`（D3/D4 用的短词） | 1.1829 | **−0.18（负数 = 不相关）** |

`令牌校验` 在 30 条 `auth.py` 块里**没有一条真正相关**，相似度全是负的，
它却仍排第 1 —— 只因为「其他文件更不相关」。

**这叫假阳性**：metadata 过滤只保证你**只能看到某个文件**，不保证**看到的是对的**。
生产上要多召回（`n_results` 取大）再让 LLM 自己筛，或者加 rerank —— 这就是 stage-2 下一块。

---

## 词 8 · `zip()` 只有 1 个参数会炸

```python
for src, dist in zip([m["source"] for m in r["metadatas"][0]]):          # ❌
# ValueError: not enough values to unpack (expected 2, got 1)

for src, dist in zip([m["source"] for m in r["metadatas"][0]], r["distances"][0]):   # ✅
```

`zip()` 1 个参数 → 每轮只吐 1 个元素 → 要拆2 个变量就报错。
症状可能伪装成 `ValueError: Unknown format code 'f' for str`（`dist` 拿到的是字符串）。

---

## 建库四行（幂等写法）

```python
client = chromadb.PersistentClient(path=str(DB_DIR))
col = client.get_or_create_collection("day020")     # 已存在就拿到，不存在才建
if col.count() == 0:                # 空才写，重复跑不会重复add
    col.add(
        ids=[str(i) for i in range(len(DATA))],
        embeddings=[d["embedding"] for d in DATA],
        documents=[d["text"] for d in DATA],
        metadatas=[{"source": d["source"], "idx": i} for i, d in enumerate(DATA)],
    )
```

`col.count() == 0` 这个判断是**幂等的关键** —— 10-06 在JSON 缓存里踩过一次：
不判空重复 `add` 会写重，Chroma 同 id 会报错或覆盖。

---

## 复现命令

```powershell
# PyCharm 内置 PowerShell
.\.venv\Scripts\python.exe -m llm_service._probe_chroma
```

**判据（实测数字，非推测）**：

| | 预期 | 改坏预期怎么挂 |
|---|---|---|
| D1 | `库内 110 条` | 改成 200 → 数量对不上 |
| D2 | 两组各 3 条 | — |
| D3 | **3 条全 `routers\auth.py`** | 删掉 `$eq` → 变 3 条混合，「全 auth.py」这条挂 ✅ 有判别力 |
| D4 | **0 条** | metadata 键改 `src` → D3 也变 0，两条一起挂 ✅ 咬合住 |

**为什么 D3 和 D4 必须一起看**：只判 D3「>0」可能假通过（`where` 整体被忽略时会照样返回 top-3）。
两个配对才证明 `$eq` 真在过滤。

---

## 一句话收口

**Chroma = 存向量 + 算谁最近。** 三件事记牢：
返回结构**三层嵌套**、`where` **必须 `$eq`**、`distances` 是**余弦距离（0~2，越小越像）**。