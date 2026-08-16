"""
Day 1 · 第一个 FastAPI 应用
运行方式：uv run uvicorn main:app --reload
浏览器打开：http://127.0.0.1:8000
自动 API 文档：http://127.0.0.1:8000/docs
"""

# 从 fastapi 库导入 FastAPI 类（fastapi 是 Web 框架本体）
from fastapi import FastAPI
from pydantic import BaseModel

# 创建一个 FastAPI 实例，整个应用围绕它构建
app = FastAPI()


# @app.get("/") 是一个「装饰器」：把下面的函数注册成 HTTP GET / 路由
# 访问 http://127.0.0.1:8000/ 时，FastAPI 就会调用 read_root 并返回它的返回值
@app.get("/")
def read_root():
    # 返回 Python 字典，FastAPI 会自动转成 JSON 响应（Content-Type: application/json）
    return {"message": "Hello World"}
class Item(BaseModel):
    name:str
    price:float

@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id": item_id}
@app.post("/items")
def create_item(item:Item):
    return item
