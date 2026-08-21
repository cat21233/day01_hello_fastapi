from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class Address(BaseModel):
    city: str
    street: Optional[str] = None
class User(BaseModel):
    name: str
    age: Optional[int] = None      # 可选字段，不传则为 None
    address: Address                # 嵌套：必须是一个符合 Address 结构的对象
    tags: List[str] = []            # 带默认值的列表，不传则为空列表 []


@router.post("/users/")
def create_user(user: User):
    # 嵌套模型 + 列表都会被 FastAPI 自动解析、校验、生成文档
    return {"msg": "用户已创建", "user": user}

def get_token(x_token: str = Header(..., description="请求头里带 X-Token")):
    if x_token != "secret-token":
        raise HTTPException(status_code=400, detail="无效 Token")
    return x_token


# get_current_user 内部 Depends(get_token) → 这就是"子依赖"：先跑父依赖
def get_current_user(token: str = Depends(get_token)):
    return {"username": "cat21233", "token": token}


@router.get("/me")
async def read_me(user: dict = Depends(get_current_user)):
    return user
