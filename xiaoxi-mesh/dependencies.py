"""FastAPI 依赖项 - token 验证"""
from fastapi import Header, HTTPException

from app_state import auth


async def require_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "缺少 Authorization header")
    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]
    if not token:
        raise HTTPException(401, "缺少 token")
    payload = auth.verify_token(token)
    if not payload:
        raise HTTPException(401, "Token 无效或已过期")
    return payload


async def optional_token(authorization: str = Header(None)):
    if not authorization:
        return None
    token = authorization
    if token.startswith("Bearer "):
        token = token[7:]
    if not token:
        return None
    try:
        return auth.verify_token(token)
    except Exception:
        return None
