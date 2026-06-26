from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from app_state import auth, cfg, perm_mgr, audit_log
from models import ApiResponse

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/api/auth/login")
async def login(req: LoginRequest):
    admin_cfg = cfg.get("admin", {})
    if req.username != admin_cfg.get("username", "admin"):
        await audit_log.log_login(req.username, False)
        raise HTTPException(401, "用户名或密码错误")
    stored_hash = admin_cfg.get("password_hash", "")
    if not stored_hash:
        raise HTTPException(500, "服务未配置管理员密码，请在 config.yaml 中设置 admin.password_hash")
    elif not auth.verify_password(req.password, stored_hash):
        await audit_log.log_login(req.username, False)
        raise HTTPException(401, "用户名或密码错误")
    permissions = perm_mgr.get_permissions_for_token("admin")
    token = auth.create_token_with_permissions("admin", "admin", permissions)
    await audit_log.log_login("admin", True)
    return ApiResponse(data={
        "token": token,
        "role": "admin",
        "permissions": permissions,
        "expires_in": cfg["auth"]["token_expire_hours"] * 3600,
    })
