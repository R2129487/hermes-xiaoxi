from fastapi import APIRouter, Depends
from app_state import perm_mgr
from dependencies import require_token
from models import ApiResponse

router = APIRouter()

@router.get("/api/permissions/check")
async def check_permission(agent_id: str, permission: str, _token_payload: dict = Depends(require_token)):
    allowed = perm_mgr.check_permission(agent_id, permission)
    return ApiResponse(data={"agent_id": agent_id, "permission": permission, "allowed": allowed})

@router.get("/api/permissions/role")
async def get_role_permissions(role: str, _token_payload: dict = Depends(require_token)):
    perms = perm_mgr.get_role_permissions(role)
    return ApiResponse(data={"role": role, "permissions": perms})
