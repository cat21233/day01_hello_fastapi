"""
Day 3 · FastAPI 进阶：Pydantic v2 进阶 + response_model + 子依赖 + async
运行：cd 项目目录后 → uvicorn main:app --port 8000
文档：http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, Query, Path, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

app = FastAPI()

# 内存版"数据库"：重启服务即清空，仅用于演示（真实项目用 MySQL/Redis）
fake_items_db = {
    1: {"item_id": 1, "name": "键盘", "price": 199.0},
    2: {"item_id": 2, "name": "鼠标", "price": 99.0},
    3: {"item_id": 3, "name": "显示器", "price": 1299.0},
}

# ============ D1 保留：根路由 ============
@app.get("/")
def read_root():
    return {"message": "Hello World"}


# ============ D2：查询参数 + 依赖注入 ============
def common_params(skip: int = 0, limit: int = 100):
    return {"skip": skip, "limit": limit}


@app.get("/items/")
def read_items(
    q: Optional[str] = Query(None, max_length=50, description="按名称模糊搜索"),
    commons: dict = Depends(common_params),
):
    items = list(fake_items_db.values())
    if q:
        items = [i for i in items if q in i["name"]]
    return items[commons["skip"]: commons["skip"] + commons["limit"]]


@app.get("/items/{item_id}")
def read_item(
    item_id: int = Path(..., gt=0, description="商品ID，必须大于0"),
):
    if item_id not in fake_items_db:
        return {"error": "not found"}
    return fake_items_db[item_id]


# 请求体模型 + 字段校验（D2）
class Item(BaseModel):
    name: str = Field(..., max_length=50, description="商品名，最长50字符")
    price: float = Field(..., gt=0, description="价格，必须大于0")


@app.post("/items/")
def create_item(item: Item):
    new_id = max(fake_items_db.keys()) + 1
    fake_items_db[new_id] = {"item_id": new_id, **item.model_dump()}
    return fake_items_db[new_id]


# ============ D3 新增①：Pydantic v2 进阶 — 嵌套模型 + Optional 默认值 ============
# 嵌套模型：一个模型里包含另一个模型（真实数据常这样，如"用户"含"地址"）
class Address(BaseModel):
    city: str
    street: Optional[str] = None   # Optional + 默认值 None：可不填


class User(BaseModel):
    name: str
    age: Optional[int] = None      # 可选字段，不传则为 None
    address: Address                # 嵌套：必须是一个符合 Address 结构的对象
    tags: List[str] = []            # 带默认值的列表，不传则为空列表 []


@app.post("/users/")
def create_user(user: User):
    # 嵌套模型 + 列表都会被 FastAPI 自动解析、校验、生成文档
    return {"msg": "用户已创建", "user": user}


# ============ D3 新增②：response_model — 约束「返回」字段 ============
# 问题：read_item 现在会连 price 一起返回，但有些场景(如对外 API)不想暴露内部价格
# 解决：定义"对外模型"，只声明允许返回的字段，FastAPI 自动过滤多余字段
class ItemPublic(BaseModel):
    item_id: int
    name: str
    # 故意不含 price → 返回时自动被剥掉


@app.get("/items/{item_id}/public", response_model=ItemPublic)
def read_item_public(
    item_id: int = Path(..., gt=0),
):
    if item_id not in fake_items_db:
        raise HTTPException(status_code=404, detail="商品不存在")
    return fake_items_db[item_id]


# ============ D3 新增③：async def 异步路由 ============
# 写法上只把 def 换成 async def。区别：
# - async def 函数里可以用 await 调用其他异步操作(如异步查数据库、调大模型API)
# - 当该接口在 await 等待 I/O 时，事件循环能去处理别的请求 → 高并发
@app.get("/health")
async def health():
    return {"status": "ok", "mode": "async"}


# ============ D3 新增④：子依赖（依赖的依赖）============
# 鉴权是后端刚需：很多接口都要"先验证 token，再取用户信息"
# 子依赖让它变成可复用的两层：get_token 校验 → get_current_user 取用户
def get_token(x_token: str = Header(..., description="请求头里带 X-Token")):
    if x_token != "secret-token":
        raise HTTPException(status_code=400, detail="无效 Token")
    return x_token


# get_current_user 内部 Depends(get_token) → 这就是"子依赖"：先跑父依赖
def get_current_user(token: str = Depends(get_token)):
    return {"username": "cat21233", "token": token}


@app.get("/me")
async def read_me(user: dict = Depends(get_current_user)):
    return user
