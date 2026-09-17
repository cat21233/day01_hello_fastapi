# routers/llm_practice.py
# D12 闭卷练习骨架 —— 把每个 ____ 补上，先想再填，别照抄
# 填完后的测试方法见文件底部说明
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse          # ① 流式响应要用的类
from openai import OpenAI

from config import settings

router = APIRouter()

# 客户端：指向 Agnes 的 OpenAI 兼容端点（api_key / base_url 已从 settings 读，不用背）
client = OpenAI(
    api_key=settings.agnes_api_key,
    base_url=settings.agnes_base_url,
)


def llm_stream_generator(prompt: str):
    stream = client.chat.completions.create(
        model=settings.agnes_model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,                        # ② 关键开关：开启流式（填 True）
    )
    for chunk in stream:
        # ③ 取这一小块新增的文字，存到 delta（两层属性，中间用 . 连）
        delta = chunk.choices[0].delta.content or ""
        if delta:
            # ④ 拼成 SSE 一帧并 yield（格式：data:内容 + 两个换行）
            yield f"data:{delta}\n\n"
    # ⑤ 结尾：发一个自定义 end 事件，让前端知道可以关连接
    yield "event: end\ndata: done\n\n"


@router.get("/llm/chat")
def llm_chat(prompt: str = Query(..., min_length=1)):   # ⑥ 查询参数必填写法
    # ⑦ 用流式响应类包住生成器；⑧ 声明内容类型（SSE 的 MIME）
    return llm_stream_generator(
        StreamingResponse(prompt),
        media_type="text/event-stream",
    )


# ───────────────────────── 测试步骤 ─────────────────────────
# 1. 把上面 8 处 ____ 全部补全
# 2. 将本文件内容覆盖到 routers/llm.py（原 llm.py 已 git 跟踪，填错可 git checkout 恢复）
# 3. 启动：.\.venv\Scripts\python.exe -m uvicorn main:app
# 4. 浏览器开 static/sse_test.html，看是否逐字流出、结尾不再重复刷
# 5. 把你的完整代码发我，我逐行 review
