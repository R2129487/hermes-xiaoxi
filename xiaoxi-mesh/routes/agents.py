from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from app_state import registry, store, delegator, discovery, audit_log, cfg
from dependencies import require_token, optional_token
from models import ApiResponse, AgentRegister, StatusUpdate

router = APIRouter()


@router.post("/api/agents/register")
async def register_agent(reg: AgentRegister, _token_payload: Optional[dict] = Depends(optional_token)):
    agent_id = reg.agent_id
    existing = registry.get(agent_id) or await store.get_agent(agent_id)
    if existing:
        await store.update_agent(agent_id, role=reg.role, online=True)
        # 更新缓存
        registry.set_online(agent_id)
    else:
        from models import Agent
        agent = Agent(
            agent_id=agent_id,
            name=reg.name or agent_id,
            role=reg.role or "agent",
            online=True,
            capabilities=reg.capabilities or [],
            specialties=reg.specialties or [],
            description=reg.description or "",
        )
        await store.register_agent(agent)
        await registry.register(agent)
    if _token_payload:
        audit_log.log("agent_register", agent_id, {"role": reg.role, "online": True})
    return ApiResponse(data={"agent_id": agent_id, "role": reg.role})


@router.post("/api/agents/{agent_id}/online")
async def agent_online(agent_id: str, _token_payload: Optional[dict] = Depends(optional_token)):
    await store.set_online(agent_id, True)
    registry.set_online(agent_id)
    if _token_payload:
        audit_log.log("agent_online", agent_id, {})
    return ApiResponse(data={"agent_id": agent_id, "online": True})


@router.post("/api/agents/{agent_id}/offline")
async def agent_offline(agent_id: str, _token_payload: Optional[dict] = Depends(optional_token)):
    await store.set_online(agent_id, False)
    registry.set_offline(agent_id)
    if _token_payload:
        audit_log.log("agent_offline", agent_id, {})
    return ApiResponse(data={"agent_id": agent_id, "online": False})


@router.post("/api/agents/{agent_id}/status")
async def update_status(agent_id: str, status: StatusUpdate, _token_payload: Optional[dict] = Depends(optional_token)):
    await store.update_agent(agent_id, status=status.status)
    if _token_payload:
        audit_log.log("status_update", agent_id, status.model_dump())
    return ApiResponse(data={"agent_id": agent_id, "status": status.status})


@router.get("/api/agents")
async def list_agents(_token_payload: Optional[dict] = Depends(optional_token)):
    agents = registry.get_all()
    if not agents:
        agents = await store.list_agents()
    online_count = registry.online_count
    return ApiResponse(data=agents, extra={"online_count": online_count})


@router.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, _token_payload: Optional[dict] = Depends(optional_token)):
    agent = registry.get(agent_id) or await store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=ApiResponse(error="agent not found").model_dump())
    return ApiResponse(data=agent)
