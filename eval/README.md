# eval/ 检索评测集

`retrieval_eval.jsonl` —— 每行一个 JSON，用来**量化** RAG 检索质量。M1 的「混合检索 + rerank」到底有没有变好，全靠这份数据说话。

## 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str | `q01` 起，唯一 |
| `query` | str | **用户口吻**的问句（模拟真人提问，不是代码符号） |
| `expected_sources` | list[str] | 期望命中的文件，**正斜杠**写法 |
| `difficulty` | str | `easy` / `medium` / `hard` |
| `why` | str | 为什么这么出题（给自己看，评测脚本可跳过） |

## 三条约定

1. **路径一律正斜杠**（`routers/auth.py`）。库里存的是反斜杠，比较时统一归一化 —— 别在 JSON 里写 `\\` 转义。
2. **`expected_sources` 是列表**：一个问题合理指向多个文件时全写上，命中任一个都算对。
3. 库里只有 **9 个 router 文件**（`rag.py` 建库时还不存在），别出这 9 个之外的题 —— 那测的是「库没覆盖」，不是「检索差」。

## 怎么用（M1 再写脚本）

```
query → 检索 Top-K → 看 expected_sources 里的文件是否出现在 Top-K 的 source 里 → 算 recall@K
```
