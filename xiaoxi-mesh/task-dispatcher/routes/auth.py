"""
用户认证与授权 API 路由
提供 JWT 登录/注册、用户管理、权限验证依赖
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Header
from models import User, Agent, now_str
from storage import Storage

# 全局引用，在 dispatcher.py 中注入
storage: Storage = None  # type: ignore

router = APIRouter(prefix="/api/auth", tags=["auth"])

# JWT 配置（生产环境应通过环境变量设置）
JWT_SECRET = os.environ.get("JWT_SECRET", "xiaoxi-task-dispatcher-secret-key-2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 168  # 7天


# ==================== JWT 依赖函数 ====================


async def get_current_user(authorization: str = Header(None)):
    """从 Authorization header 提取并验证 JWT token，返回 User 对象"""
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少认证信息")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="无效的认证格式")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效的 token")

        user = await storage.get_user(user_id=user_id)
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")

        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的 token")


async def require_admin(user: User = Depends(get_current_user)):
    """检查当前用户是否为 admin 角色"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


# ==================== 工具函数 ====================


def _hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(
        password.encode("utf-8"), password_hash.encode("utf-8")
    )


def _create_token(user: User) -> str:
    """生成 JWT token"""
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _safe_user(user: User) -> dict:
    """返回安全的用户信息（不含密码哈希）"""
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "created_at": user.created_at,
    }


# ==================== API 路由 ====================


@router.post("/register")
async def register(body: dict):
    """注册新用户（无需登录，首次使用）"""
    try:
        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()
        display_name = (body.get("display_name") or "").strip() or username
        role = (body.get("role") or "operator").strip()

        if not username or len(username) < 2:
            return {"code": 1, "message": "用户名至少2个字符"}
        if not password or len(password) < 6:
            return {"code": 1, "message": "密码至少6个字符"}
        if role not in ("admin", "operator", "observer"):
            return {"code": 1, "message": "无效的角色"}
        # 普通注册不能自封 admin
        if role == "admin":
            role = "operator"

        # 检查用户名是否已存在
        existing = await storage.get_user(username=username)
        if existing:
            return {"code": 1, "message": "用户名已被注册"}

        user = User(
            id=str(uuid.uuid4())[:8],
            username=username,
            password_hash=_hash_password(password),
            display_name=display_name,
            role=role,
        )
        created = await storage.create_user(user)

        # 同步创建智能体条目（让用户在联系人中可见）
        agent = Agent(
            id=f"user_{user.id}",
            name=display_name,
            type="user",
            capabilities="chat",
            status="online",
            connection_type="local",
        )
        existing_agent = await storage.get_agent(agent.id)
        if not existing_agent:
            await storage.create_agent(agent)

        return {"code": 0, "message": "注册成功", "data": _safe_user(created)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def login(body: dict):
    """用户登录，返回 JWT token"""
    try:
        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()

        if not username or not password:
            return {"code": 1, "message": "用户名和密码不能为空"}

        user = await storage.get_user(username=username)
        if not user:
            return {"code": 1, "message": "用户名或密码错误"}

        if not _verify_password(password, user.password_hash):
            return {"code": 1, "message": "用户名或密码错误"}

        token = _create_token(user)

        # 更新用户对应的 agent 状态（标记在线）
        agent_id = f"user_{user.id}"
        existing = await storage.get_agent(agent_id)
        if existing:
            await storage.update_agent(agent_id, {"status": "online", "last_seen": now_str()})

        return {
            "code": 0,
            "message": "登录成功",
            "data": {
                "token": token,
                "user": _safe_user(user),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    # 刷新 last_seen
    agent_id = f"user_{user.id}"
    existing = await storage.get_agent(agent_id)
    if existing:
        await storage.update_agent(agent_id, {"last_seen": now_str()})
    return {"code": 0, "data": _safe_user(user)}


@router.get("/users")
async def list_users(admin: User = Depends(require_admin)):
    """获取用户列表（仅 admin）"""
    try:
        users = await storage.get_users()
        return {"code": 0, "data": [_safe_user(u) for u in users]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}")
async def update_user(user_id: str, body: dict, admin: User = Depends(require_admin)):
    """修改用户信息/角色（仅 admin）"""
    try:
        user = await storage.get_user(user_id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        updates = {}
        if "display_name" in body:
            name = (body["display_name"] or "").strip()
            if name:
                updates["display_name"] = name
        if "role" in body:
            role = (body["role"] or "").strip()
            if role in ("admin", "operator", "observer"):
                updates["role"] = role
        if "password" in body:
            pwd = (body["password"] or "").strip()
            if len(pwd) >= 6:
                updates["password_hash"] = _hash_password(pwd)

        if not updates:
            return {"code": 1, "message": "没有可更新的字段"}

        updated = await storage.update_user(user_id, updates)
        return {"code": 0, "message": "更新成功", "data": _safe_user(updated)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(require_admin)):
    """删除用户（仅 admin，不能删除自己）"""
    try:
        if user_id == admin.id:
            return {"code": 1, "message": "不能删除自己"}

        user = await storage.get_user(user_id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        ok = await storage.delete_user(user_id)
        if ok:
            return {"code": 0, "message": f"用户 {user.username} 已删除"}
        return {"code": 1, "message": "删除失败"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
