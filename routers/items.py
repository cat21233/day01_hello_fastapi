from fastapi import APIRouter, Query, Depends, Path, HTTPException,Request
from typing import Optional
from pydantic import BaseModel, Field
from routers.auth import get_current_admin
from routers.limits import limiter

router = APIRouter()
fake_items_db = {
    1: {"item_id": 1, "name": "键盘", "price": 199.0},
    2: {"item_id": 2, "name": "鼠标", "price": 99.0},
    3: {"item_id": 3, "name": "显示器", "price": 1299.0},
}
def common_params(skip: int = 0, limit: int = 100):
    return {"skip": skip, "limit": limit}


@router.get("/items/")
@limiter.limit("5/minute")
def read_items(
    request: Request,
    q: Optional[str] = Query(None, max_length=50, description="按名称模糊搜索"),
    commons: dict = Depends(common_params),
):
    items = list(fake_items_db.values())
    if q:
        items = [i for i in items if q in i["name"]]
    return items[commons["skip"]: commons["skip"] + commons["limit"]]
@router.get("/items/{item_id}")
def read_item(
    item_id: int = Path(..., gt=0, description="商品ID，必须大于0"),
):
    if item_id not in fake_items_db:
        raise HTTPException(status_code=404, detail='商品不存在')
    return fake_items_db[item_id]

class ItemPublic(BaseModel):
    item_id: int
    name: str
    # 故意不含 price → 返回时自动被剥掉


@router.get("/items/{item_id}/public", response_model=ItemPublic)
def read_item_public(
    item_id: int = Path(..., gt=0),
):
    if item_id not in fake_items_db:
        raise HTTPException(status_code=404, detail="商品不存在")
    return fake_items_db[item_id]


class Item(BaseModel):
    name: str = Field(..., max_length=50, description="商品名，最长50字符")
    price: float = Field(..., gt=0, description="价格，必须大于0")


@router.post("/items/")
def create_item(item: Item):
    new_id = max(fake_items_db.keys()) + 1
    fake_items_db[new_id] = {"item_id": new_id, **item.model_dump()}
    return fake_items_db[new_id]

@router.delete('/items/{item_id}')
def delete_item(
        item_id: int = Path(...,gt=0, description="商品ID"),
        admin: dict = Depends(get_current_admin)
):
    if item_id not in fake_items_db:
        raise HTTPException(status_code=404, detail="商品不存在")
    removed = fake_items_db.pop(item_id)
    return {"msg": "已删除", "item": removed}