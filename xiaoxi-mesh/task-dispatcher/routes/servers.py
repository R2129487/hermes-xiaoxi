"""服务器管理 API 路由"""
from fastapi import APIRouter, HTTPException
from models import Server, now_str
from storage import Storage

storage: Storage = None

router = APIRouter(prefix="/api/servers", tags=["servers"])


@router.get("")
async def list_servers():
    try:
        servers = await storage.get_servers()
        return {"code": 0, "data": [s.model_dump() for s in servers]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_server(server: Server):
    try:
        existing = await storage.get_server(server.id)
        if existing:
            raise HTTPException(status_code=400, detail=f"服务器 {server.id} 已存在")
        created = await storage.create_server(server)
        return {"code": 0, "message": "添加成功", "data": created.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{server_id}")
async def get_server(server_id: str):
    try:
        s = await storage.get_server(server_id)
        if not s:
            raise HTTPException(status_code=404, detail="服务器不存在")
        return {"code": 0, "data": s.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{server_id}")
async def update_server(server_id: str, updates: dict):
    try:
        s = await storage.get_server(server_id)
        if not s:
            raise HTTPException(status_code=404, detail="服务器不存在")
        allowed = {"name", "host", "port", "ssh_user", "location", "status", "remark"}
        clean = {k: v for k, v in updates.items() if k in allowed}
        updated = await storage.update_server(server_id, clean)
        return {"code": 0, "message": "已更新", "data": updated.model_dump() if updated else None}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{server_id}")
async def delete_server(server_id: str):
    try:
        s = await storage.get_server(server_id)
        if not s:
            raise HTTPException(status_code=404, detail="服务器不存在")
        await storage.delete_server(server_id)
        return {"code": 0, "message": "已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
