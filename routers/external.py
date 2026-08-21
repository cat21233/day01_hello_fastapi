from fastapi import APIRouter, Path
import httpx
router = APIRouter()

@router.get("/external/users/{user_id}")
async def get_external_user(user_id: int = Path(..., gt=0, description="用户id")):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://jsonplaceholder.typicode.com/users/{user_id}")
        return resp.json()