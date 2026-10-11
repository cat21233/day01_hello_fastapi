"""RAG 存储层：Chroma 建库 / 写入 / 检索。

从 _probe_chroma.py 提炼而来。探针只跑一次、跑完就退，服务要长期驻留
—— 两个关键差别：
  1. 路径从 config 读，不写死（容器里挂载点不同）
  2. client 和 model 都模块级缓存，不每次新建（构造要 13 秒 / 持有连接）
"""
import json
import pathlib

from config import settings

ROOT = pathlib.Path(__file__).resolve().parent.parent

_MODEL = None
_CLIENT = None
_DATA = None


def get_model():
    """惰性加载 + 缓存：模型构造要 13 秒，全局只做一次"""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(str(ROOT / "models" / "bge-small-zh-v1.5"))
    return _MODEL


def get_client():
    """惰性加载 + 缓存：PersistentClient 持有 SQLite 连接，不能每次新建"""
    global _CLIENT
    if _CLIENT is None:
        import chromadb

        db_dir = ROOT / settings.chroma_dir
        db_dir.mkdir(parents=True, exist_ok=True)
        _CLIENT = chromadb.PersistentClient(path=str(db_dir))
    return _CLIENT


def get_collection(name: str | None = None):
    """拿到集合（不存在则创建，空集合）。集合名默认走配置。"""
    col_name = name or settings.rag_collection
    return get_client().get_or_create_collection(col_name)


def load_docs() -> list:
    """读 day-020 产出的向量文件。惰性加载 + 缓存，1.24MB 只读一次。"""
    global _DATA
    if _DATA is None:
        vec_file = ROOT / settings.rag_vec_file
        _DATA = json.loads(vec_file.read_text(encoding="utf-8"))
    return _DATA


def ingest(paths: list[str] | None = None, collection: str | None = None) -> dict:
    """把向量写进库。

    paths 为空 = 全量写入；非空 = 只写 metadata["source"] 在里面的那些。
    幂等：库非空时直接返回，不重复 add。

    返回 {"ingested": 本次写入条数, "total": 库内总条数}
    """
    col = get_collection(collection)
    if col.count() > 0:
        return {"ingested": 0, "total": col.count()}

    data = load_docs()
    if paths:
        # 库里存的是 Windows 反斜杠（routers\auth.py），调用方习惯传正斜杠
        # （routers/auth.py）—— 两边都归一成 / 再比，两种写法都能匹配。
        def _norm(p: str) -> str:
            return p.replace("\\", "/")

        wanted = {_norm(p) for p in paths}
        picked = [d for d in data if _norm(d["source"]) in wanted]
    else:
        picked = data


    if not picked:
        return {"ingested": 0, "total": col.count()}

    col.add(
        ids=[str(i) for i in range(len(picked))],
        embeddings=[d["embedding"] for d in picked],
        documents=[d["text"] for d in picked],
        metadatas=[{"source": d["source"], "idx": i} for i, d in enumerate(picked)],
    )
    return {"ingested": len(picked), "total": col.count()}


def search(query: str, n: int = 3, collection: str | None = None, where: dict | None = None):
    """语义检索。必须用 query_embeddings —— query_texts 会拉 384 维默认模型，与 512 维库错配。"""
    qe = get_model().encode([query], normalize_embeddings=True).tolist()
    return get_collection(collection).query(
        query_embeddings=qe, n_results=n, where=where
    )
