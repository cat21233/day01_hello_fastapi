"""
Day 2 · FastAPI 进阶：查询参数 + 字段校验 + 依赖注入
运行：cd 项目目录后 → uvicorn main:app --port 8000
文档：http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, Query, Path, Depends
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI()

# 内存版"数据库"：重启服务即清空，仅用于演示（真实项目用 MySQL/Redis）
fake_items_db = {
    1: {"item_id": 1, "name": "键盘", "price": 199.0},
    2: {"item_id": 2, "name": "鼠标", "price": 99.0},
    3: {"item_id": 3, "name": "显示器", "price": 1299.0},
}

# ---- D1 保留：根路由 ----
@app.get("/")
def read_root():
    return {"message": "Hello World"}

# ---- 依赖函数：被 Depends 自动调用，返回分页参数 ----
# 它就是一个普通函数，不需要任何特殊装饰。
# 关键点：多个接口都要"分页"时，写一次就够了，后面用 Depends 复用。
def common_params(skip: int = 0, limit: int = 100):
    return {"skip": skip, "limit": limit}

# ---- D2 新增①：查询参数 + 依赖注入 ----
# q 是「查询参数」：写在 URL 的 ? 后面，如 /items/?q=鼠标
# commons 是「依赖注入」：FastAPI 自动调用 common_params() 把返回值塞进来
@app.get("/items/")
def read_items(
    q: Optional[str] = Query(None, max_length=50, description="按名称模糊搜索"),
    commons: dict = Depends(common_params),
):
    items = list(fake_items_db.values())
    if q:  # 有搜索词就过滤
        items = [i for i in items if q in i["name"]]
    # 用 commons 里的 skip/limit 做分页切片
    return items[commons["skip"]: commons["skip"] + commons["limit"]]

# ---- D2 新增②：路径参数 + 字段校验 ----
# Path(..., gt=0) 含义：item_id 必填（... 表示必填），且必须大于 0
# 传 /items/0 或 /items/-5 会被自动拦截返回 422，不用你写一行 if 判断
@app.get("/items/{item_id}")
def read_item(
    item_id: int = Path(..., gt=0, description="商品ID，必须大于0"),
):
    if item_id not in fake_items_db:
        return {"error": "not found"}
    return fake_items_db[item_id]

# ---- D2 增强③：请求体模型 + 字段校验 ----
# Field(..., max_length=50) 含义：name 必填，且最长 50 字符
# Field(..., gt=0) 含义：price 必填，且必须大于 0（价格不能是负的）
class Item(BaseModel):
    name: str = Field(..., max_length=50, description="商品名，最长50字符")
    price: float = Field(..., gt=0, description="价格，必须大于0")

# POST 用增强后的模型：FastAPI 会自动按 Field 规则校验请求体
@app.post("/items/")
def create_item(item: Item):
    new_id = max(fake_items_db.keys()) + 1
    # item.model_dump() 把 Pydantic 对象转成普通 dict（Pydantic v2 写法）
    fake_items_db[new_id] = {"item_id": new_id, **item.model_dump()}
    return fake_items_db[new_id]
