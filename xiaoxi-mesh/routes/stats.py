from fastapi import APIRouter, Depends
from app_state import registry, store
from dependencies import require_token
from models import ApiResponse

router = APIRouter()

@router.get("/api/stats")
async def get_stats(_token_payload: dict = Depends(require_token)):
    stats = await store.get_stats()
    stats["online_count"] = registry.online_count
    return ApiResponse(data=stats)
