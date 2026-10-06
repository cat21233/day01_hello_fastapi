# RAG 分块 · 速查卡（三种分块器对照 + 缓存真相）

> day-020（2026-10-06）· stage-2 RAG 地基 · 明天装 Chroma 前扫一眼
> 背景：10-05 计划的 11 项 RAG 分块任务全未做（10-05 无学习日志）。今天补完「加载 → 分块 → 嵌入」三步闭环。
> 产出：`llm_service/_probe_split.py`（探针，不进版本库）+ `day-020/split_embeddings.json`（110 条向量）

---

## 一张总图：三块在 RAG 链路上的位置

```
routers/*.py （9 个文件 · 25626 字符）
        ↓
【A 造语料】9 个 Document（metadata 记 source）
        ↓
【B 分块】110 块，每块 ≤200 字符
        ↓
【C 嵌入】110 条 × 512 维 float32 → JSON 落盘
        ↓
   （明天）向量库建索引 → similarity_search → 喂给模型
```

**一句话**：A 把文件变成"可被切的单位"，B 把单位切成"能塞进模型的小片"，C 把小片换成"计算机能比的东西"。

---

## 词 1 · `chunk_size` 不是「切多小」

这是今天最反直觉的一点，**90% 的教程没讲清**。

| 栏 | 内容 |
|---|---|
| 误解 | `chunk_size=200` = 每块 200 字符 |
| 实测 | `chunk_size` = **合并后别超过多大**。切不动就整块留着，可以远超 200 |
| 为什么 | 分块器有**两刀**：先按 `separator` 切，再把切好的小块**合并**到 `chunk_size` 以内。第 1 刀切不动，第 2 刀无事可做 |
| 判别信号 | 平均块长 **> chunk_size**，或刷出 `Created a chunk of size N, which is longer than the specified 200` |
| 真话 | **`chunk_size` 是上限，不是目标。程序不报错，只安静地给你一个烂结果。** |

---

## 词 2 · 两种分块器的真实区别 = 有没有备选链

实测打印内部结构（今天所有结论的根）：

```python
CharacterTextSplitter    _separator  = '\n\n'                      # 只有 1 把刀
RecursiveTextSplitter    _separators = ['\n\n', '\n', ' ', '']    # 4 级备选
```

**`Recursive` 的含义**：先用 `\n\n` 切 → 块还太大就换 `\n` → 还太大换 `' '` → 再不行换 `''`（等于每字符一刀，保底）。

**判别力实验（434 字符 · 0 个空行 · chunk_size=200）**：

| 分块器 | 块数 | 每块长度 | 超过 200 的块 |
|---|---|---|---|
| `CharacterTextSplitter` | **1** | 433 | **1**（超 2 倍）|
| `RecursiveCharacterTextSplitter` | **3** | 199 / 181 / 43 | **0** |

**同样 0 个空行，一个整块没切，一个切 3 块全达标。** 差别不在参数，全在备选链。

---

## 词 3 · 真语料实测（本项目 9 个 .py）

```
Character ->  62 块 | 长度 20~952  | 越界 29 个（47%）| 警告 43 条
Recursive -> 110 块 | 长度 20~198  | 越界  0 个（ 0%）| 无警告
```

**为什么这个差距这么大**：`routers/*.py` 是**代码**，空行少。`Character` 那唯一的一把刀（`\n\n`）经常砍空，砍空就整块留着 —— 于是 47% 的块超标，最大 952 字符（近 5 倍）。

**工程结论**：**默认就用 `RecursiveCharacterTextSplitter`。** `Character` 只在"你确信语料空行极多"时才用。

**别拿平均值下结论** —— 平均 241（Character）vs 133（Recursive）看着只差一倍，但真正说明问题的是**越界块数 29 vs 0** 和 **max 952 vs 198**。

---

## 词 4 · `Document`：RAG 为什么不只用字符串

```python
from langchain_core.documents import Document
d = Document(page_content="正文", metadata={"source": "routers/llm.py"})
```

| 栏 | 内容 |
|---|---|
| 为什么需要 | 检索回来要能回答"**这段话出自哪个文件**"，否则模型无法引用、易编造 |
| `metadata` 存什么 | `source`（相对路径）/ 页码 / 章节 / 任何过滤维度 |
| ⚠️ 陷阱 | `str(p)` 打出 `C:\Users\yizihao\projects\...` 一长串；要用 `str(p.relative_to(ROOT))` |
| 三个切法 | `split_text(str)` 传字符串→返回 list[str]；`create_documents(strs, metadatas)` 从字符串建 Document；`split_documents(docs)` 切已有 Document（**metadata 自动跟着走**）|

---

## 🔴 1.x 坑 #2：分块器**没有 `split` 方法**

网上教程（含很多中文博客）写 `splitter.split(text)` —— **这个方法在 1.1.3 里不存在**。

```
实际可用：split_text / create_documents / split_documents
```

今天是第二个 1.x 变更（第一个：`langgraph.prebuilt.create_react_agent` 已移走，改 `langchain.agents.create_agent`）。**装 1.x 之后，别信任何没标版本的教程。**

---

## 词 5 · 归一化：为什么 `normalize_embeddings=True`

实测三句的相似度矩阵（**用的是点积，不是余弦**）：

```
                鉴权逻辑  JWT校验  天气
鉴权逻辑           1.0    0.382   0.326
JWT校验          0.382    1.0     0.232
天气             0.326   0.232    1.0
```

| 栏 | 内容 |
|---|---|
| 归一化做了什么 | 把每个向量缩放到**模长 = 1**（实测三条全是 1.0） |
| 于是 | `cos(a,b) = (a·b)/(|a||b|) = (a·b)/1 = a·b` —— **余弦 = 点积，省一次除法** |
| 为什么标准化 | 向量库（FAISS/Chroma）内部都按内积算，**归一化后直接用点积，结果就是余弦** |
| 判别 | 打印 `np.linalg.norm(v)`，全 ≈ 1.0 才算生效 |
| 怎么查 | 语义近的那对分数应明显更高（这里 0.382 vs 0.232，差 1.6 倍）|

---

## ⭐ 词 6 · 缓存：真相不是"省时间"，是"不重复算"

**今天实测打翻了我自己的判据。**

| 项 | 我说的 | 实测 |
|---|---|---|
| 首次运行命中次数 | 0 次 | **1 次** |

**根因**：`routers/stream.py` 里有**两处字面完全相同**的代码：

```python
yield "event: end\ndata: done\n\n"      # 出现 2 次
```

分块后成为两块内容一样的文本 → 第 2 块查缓存命中 → **省掉 6 ms 模型计算**。

**110 块 / 109 唯一 / 1 重复。**

| 栏 | 内容 |
|---|---|
| 缓存键用什么 | **文本本身**（`cache[d.page_content]`）。文本是天然身份证，不需额外编号也不会撞 |
| 为什么能复用 | 嵌入是**确定性**的：同文本 + 同模型 = 同向量。存下来复用不会算错 |
| 真实价值 | 真实项目里 `import` 块 / `__init__` / 配置样板 / 注释头 重复率常 **5~10%**，规模越大命中率越高 |
| `.tolist()` 细节 | `model.encode()` 返回 numpy `float32` 数组，`json.dumps` 直接抛 `TypeError`，**必须 `.tolist()`** |
| **当前缺陷** | `cache` 是**内存字典，进程退出即消失**。`split_embeddings.json` 是**产物**，不是缓存（虽然长得像）|

**要让缓存活过进程**（明天做，2 行）：

```python
loaded = json.loads((out / "split_embeddings.json").read_text(encoding="utf-8"))
cache = {x["text"]: x["embedding"] for x in loaded}   # ← 列表不能按文本查，必须转字典
```

**这一步叫「索引重建」** —— 列表是**按位置**取值（`cache[0]`），字典是**按键**取值（`cache["import jwt"]`），位置和文本之间没有对应关系。

> 顺带发现：`day-017/embeddings_store.json` 存的是 **list 不是 dict** → **能存不能查**。当时（可能无意识地）存成了错结构。

---

## 🔴 零宽空格 U+200B（第二次踩）

```python
if __name__ == "__&#8203;main__":     # ← 藏了一个 U+200B，屏幕完全看不见
```

条件永远 `False` → **整个文件定义完函数就退出 → 零输出、退出码 0**。9-24 撞过一次，今天第二次。

**成因**：从带渲染的源（MD/网页）复制，`&#8203;` 被解码成真的零宽字符。**手打 `__main__` 就没这问题。**

**当场可查**（判据：必须是 0）：

```powershell
.\.venv\Scripts\python.exe -c "print(open('llm_service/_probe_split.py',encoding='utf-8').read().count(chr(0x200b)))"
```

**通病根因：改完不 Ctrl+S → 磁盘上还是旧版本。** 今天又犯（10-04 已犯两次）。

---

## 三条判别力铁律（今天全部用上）

| # | 铁律 | 今天的证据 |
|---|---|---|
| 1 | **测试通过不算数，改坏了还能通过才是假测试** | 沿用 10-04 立的 |
| 2 | **我给判据前必须自己先跑一次** | 今天第三次翻车：猜 parser 返回 `str`（实为 `TextAccessor`）、猜 400 根因、**猜"110 块无重复"** |
| 3 | **数据类判据必须先 `Counter` 数一遍** | 「110 块都是不同内容」是我凭直觉说的，`Counter` 一跑就出 1 个重复 |

**第 2、3 条是配套的**：API 类判据靠实测（跑一次），数据类判据靠实测（数一遍）。**都不能靠直觉。**

---

## 性能基线（本机实测，下次可对照）

| 操作 | 耗时 | 备注 |
|---|---|---|
| 载入 BGE-small-zh | **0.1 s** | 71 层权重 / 95.8 MB safetensors |
| 嵌入 3 条 | 0.11 s | 单条调用 |
| **嵌入 110 块（batch_size=32）** | **0.64 s** | 每块 6 ms |
| 向量维度 | 512 | float32，模长全 1.0 |
| 模型位置 | `models/bge-small-zh-v1.5/` | **不是 `.model_cache`**（记忆里那条记错了）|

**110 块 0.64 s 意味着：本地嵌入完全够用，不需要为 RAG 申请云端 embedding key。** （`chromadb` / `faiss-cpu` 仍未装，明天装）

---

## 明天接着做（已排好序）

| 序 | 内容 | 依赖 |
|---|---|---|
| 1 | **磁盘缓存**：2 行，让第二次跑命中 109 | 今天剩的 |
| 2 | 装 `chromadb` → 建库 → `similarity_search` + 打印命中分数 | — |
| 3 | 换 `k` 值 / 换 embedding 模型看命中变化 | 2 |
| 4 | metadata filter 按 source 限定检索范围 | 2 |
| 5 | 纯 Python 手算 cosine，复现向量库打分 | 2 |

**欠账提醒**：`bind_tools` 对照实验（框架 1 行 vs 你手写 40 行）、async 深层（`wait_for` / `TaskGroup`）。

---

## 一句话总结

> **分块器不是"按长度切"，是"先用分隔符切、再合并到上限"；两种分块器的差距全在有没有备选链；缓存不是省时间，是不重复算。**

三个都是"直觉会错、实测才对"的地方 —— 这就是为什么凡给判据都得先跑一遍。
