from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from routers.limits import limiter

from pydantic import BaseModel, Field

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
fake_users_db = {
    "zihao": {"username": "zihao", "hashed_password": pwd.hash("123456"), "role": "admin"},
    "test": {"username": 'test', "hashed_password": pwd.hash("123456"), "role": "user"}
}
SECRET_KEY = 'my-secret-key-2026'
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 天


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


# ============ JWT 认证核心（全项目共用） ============
# 读卡器：自动从请求头 Authorization: Bearer <token> 抽出 token
#
# 为什么用 HTTPBearer 而不是 OAuth2PasswordBearer？
#   OAuth2PasswordBearer 会让 Swagger 的 Authorize 走 OAuth2 password 流程——
#   即以 form-data 去打 tokenUrl，而我们的 /token 收的是 JSON body（LoginRequest）。
#   两边对不上 → Swagger 永远拿不到 token → 点 Execute 只能看到 401。
#   HTTPBearer 只要求 Swagger 弹一个「填 token」的输入框，与真实调用方式完全一致。
#
# auto_error=False：缺 token 时不自动抛 403，交给下面手动抛 401 —— 保持「未认证=401」语义
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="粘贴 POST /token 返回的 access_token（只填 token 本身，不要加 Bearer 前缀）",
)


# 辅助函数：统一签发（自动加 exp）
def _create_token(payload: dict, expires_minutes: int) -> str:
    payload = payload.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# 保安：验签依赖（只认 access 类型，refresh token 不许当 access 用）
def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)):
    # ① 没带票据 → 401（缺的是身份，不是权限，所以不能是 403）
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # ② 带了票据 → 从凭据里取出 token 字符串，往下验签
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="无效 token")
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise HTTPException(status_code=401, detail="无效 token")
        return {"username": username, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="无效或过期 token")


# 门卫队长：认证(401)之后再来鉴权(403)
def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


@router.post("/token")
@limiter.limit("3/minute")
def token_login(request: Request, item: LoginRequest):
    user = fake_users_db.get(item.username)
    if not user or not pwd.verify(item.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail='用户名或密码错误')
    base_payload = {"sub": item.username, "role": user["role"]}
    access_token = _create_token({**base_payload, "type": "access"}, ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token = _create_token({**base_payload, "type": "refresh"}, REFRESH_TOKEN_EXPIRE_MINUTES)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/refresh")
def refresh_token_login(item: RefreshRequest):
    try:
        payload = jwt.decode(item.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="无效或过期 refresh token")
        username: str = payload.get("sub")
        role: str = payload.get("role")
        new_access = _create_token(
            {"sub": username, "role": role, "type": "access"},
            ACCESS_TOKEN_EXPIRE_MINUTES
        )
        return {"access_token": new_access, "token_type": "bearer"}
    except JWTError:
        raise HTTPException(status_code=401, detail="无效或过期 refresh token")
