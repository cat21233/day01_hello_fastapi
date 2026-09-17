from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional

from routers.auth import get_current_user

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


# ============ D8：/me 升级为真 JWT 保护（D3 假鉴权退役） ============
@router.get("/me")
async def read_me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"], "role": current_user["role"]}