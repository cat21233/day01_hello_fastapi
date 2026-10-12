"""routers/rag.py —— RAG 路由（t-1262）

把 llm_service/rag_store.py 的存储层暴露成 HTTP：
  POST /rag/ingest   按路径把已有向量写进库（幂等）

路由层只干 HTTP 的活（收参数、校验、返回 JSON），Chroma 的活全在
rag_store.py —— 将来换向量库，这个文件一行不用改。
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from common.sse import sse_response
from config import settings
from llm_service import LLMClient
from llm_service.rag_store import build_context, ingest, search

router = APIRouter(prefix="/rag", tags=["rag"])

# 模块级建一次 —— 和 routers/llm.py 第 16 行同一个做法
llm = LLMClient(settings.llm_provider)

class IngestIn(BaseModel):
    paths: list[str] = Field(
        default_factory=list,
        description="要入库的源文件相对路径；空列表 = 全量入库",
    )


class IngestOut(BaseModel):
    ingested: int   # 本次写入条数
    total: int      # 库内总条数


class QueryIn(BaseModel):
    query: str = Field(..., min_length=1, description="检索问句")
    n: int = Field(3, ge=1, le=50, description="返回条数")
    source: str | None = Field(
        None, description="只在某个源文件里检索，如 routers/auth.py；不传 = 全库"
    )


class Hit(BaseModel):
    source: str    # 这块来自哪个文件
    score: float   # 余弦相似度 = 1 - 距离，越大越像
    text: str      # 命中块原文 —— 下一步拼 prompt 就靠它


class QueryOut(BaseModel):
    query: str
    hits: list[Hit]


# 注意：这两个都是 def，不是 async def —— 理由见文件顶部注释
@router.post("/ingest")
def rag_ingest(body: IngestIn) -> IngestOut:
    return ingest(body.paths)

@router.post("/query")
def rag_query(body: QueryIn) -> QueryOut:
    where = None
    if body.source:
        # Chroma 拿这个字符串跟 metadata 逐字符比：库里存的是反斜杠
        # （routers\auth.py），调用方习惯传正斜杠 —— 必须转成库里的格式。
        # 方向跟 ingest 里「两边都归一成正斜杠」相反，因为那边是内存比、
        # 这边是跟已存字符串比。
        where = {"source": {"$eq": body.source.replace("/", "\\")}}

    raw = search(body.query, n=body.n, where=where)

    hits = [
        Hit(source=m["source"], score=round(1 - d, 4), text=t)
        for m, d, t in zip(
            raw["metadatas"][0], raw["distances"][0], raw["documents"][0]
        )
    ]
    return QueryOut(query=body.query, hits=hits)

# ⚠️ 故意用 def —— 里面的 search() 是 CPU 阻塞调用（首次 9.7 秒）。
#    写成 async def 会焊住事件循环，同期所有请求都进不来。
#    那怎么还能流式？用 stream_response 里那层「同步转异步」的包装（见下）。
@router.post("/query/stream")
def rag_query_stream(body: QueryIn):
    where = None
    if body.source:
        where = {"source": {"$eq": body.source.replace("/", "\\")}}

    raw = search(body.query, n=body.n, where=where)
    hits = [
        Hit(source=m["source"], score=round(1 - d, 4), text=t).model_dump()
        for m, d, t in zip(
            raw["metadatas"][0], raw["distances"][0], raw["documents"][0]
        )
    ]

    async def _gen():
        context = build_context(hits)
        system = "你是代码助手。只根据下面的资料回答，资料里没有的就说不知道，不要编造。"
        prompt = f"资料：\n{context}\n\n问题：{body.query}"
        async for delta in llm.stream(prompt, system=system):
            yield delta

    return sse_response(_gen(), end_event="end", end_data="done")