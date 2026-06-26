from typing import Optional
from fastapi import APIRouter, Depends
from app_state import audit_log
from dependencies import require_token
from models import ApiResponse

router = APIRouter()

@router.get("/api/audit/logs")
async def get_audit_logs(agent_id: Optional[str] = None, action: Optional[str] = None, limit: int = 100, offset: int = 0, _token_payload: dict = Depends(require_token)):
    logs = await audit_log.query(agent_id=agent_id, action=action, limit=limit, offset=offset)
    return ApiResponse(data={"logs": logs, "count": len(logs)})
