"""
routers/prompts.py —— Prompt 管理路由（t-235）

把 llm_service/prompts.py 的注册表暴露成 HTTP 接口：
  GET  /prompts           列出所有 prompt（名字 + 前 50 字预览）
  GET  /prompts/{name}    查看某个 prompt 的完整文本
  POST /prompts/preview   动态选择 + 预览：给定 prompt 名和用户消息，
                          返回「即将发给 LLM 的 messages」，但不真正调用（方便调试拼装对不对）

这样改 prompt 不用动代码、不用翻源码，前端/测试也能随时看当前有哪些角色。
"""
from fastapi import APIRouter
from pydantic import BaseModel

from llm_service.prompts import get_prompt, list_prompts

router = APIRouter(prefix="/prompts", tags=["prompts"])


class PromptPreview(BaseModel):
    name: str
    preview: str          # 前 50 字，列表页用，避免长文本刷屏


class SelectIn(BaseModel):
    name: str             # 要用的 prompt 名
    user_message: str     # 用户消息，用来拼 messages


@router.get("")
async def list_all() -> list[PromptPreview]:
    return [
        PromptPreview(name=n, preview=get_prompt(n)[:50])
        for n in list_prompts()
    ]


@router.get("/{name}")
async def get_one(name: str) -> dict:
    return {"name": name, "text": get_prompt(name)}


@router.post("/preview")
async def preview_messages(body: SelectIn) -> dict:
    """动态选择 + 预览：把 system + user 拼成最终要发给 LLM 的 messages。

    只返回拼装结果，不调用模型——用来确认 prompt 和消息结构对不对。
    """
    system = get_prompt(body.name)
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": body.user_message},
        ]
    }
