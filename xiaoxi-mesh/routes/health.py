from fastapi import APIRouter
from app_state import registry

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok", "agents_online": registry.online_count, "version": "2.0"}
