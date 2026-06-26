from typing import Optional
from fastapi import APIRouter, Query, Depends
from app_state import auth, audit_log
from dependencies import require_token
from models import ApiResponse

router = APIRouter()

@router.post("/api/tokens/create")
async def create_token(agent_id: str = Query(...), role: str = Query("agent"), _token_payload: dict = Depends(require_token)):
    token = auth.create_token(agent_id, role)
    audit_log.log("token_create", agent_id, {"role": role, "token_prefix": token[:16]})
    return ApiResponse(data={"token": token, "agent_id": agent_id, "role": role})

@router.post("/api/tokens/verify")
async def verify_token(token: str, _token_payload: dict = Depends(require_token)):
    payload = auth.verify_token(token)
    if not payload:
        return ApiResponse(error="invalid token")
    return ApiResponse(data={"valid": True, "payload": payload})
