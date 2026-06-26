from typing import Optional
from fastapi import APIRouter, Depends
from app_state import registry, store, discovery, audit_log
from dependencies import optional_token
from models import ApiResponse, CapabilityUpdate

router = APIRouter()

@router.post("/api/capabilities/update")
async def update_capabilities(update: CapabilityUpdate, _token_payload: Optional[dict] = Depends(optional_token)):
    await discovery.update_capabilities(update.agent_id, update.capabilities)
    if _token_payload:
        audit_log.log("capabilities_update", update.agent_id, {"count": len(update.capabilities)})
    return ApiResponse(data={"agent_id": update.agent_id, "capabilities_count": len(update.capabilities)})

@router.get("/api/capabilities/query")
async def query_capabilities(agent_id: Optional[str] = None, capability: Optional[str] = None, _token_payload: Optional[dict] = Depends(optional_token)):
    if agent_id:
        caps = await discovery.get_agent_capabilities(agent_id)
        return ApiResponse(data={"agent_id": agent_id, "capabilities": caps})
    if capability:
        agents = await discovery.find_agents_by_capability(capability)
        return ApiResponse(data={"capability": capability, "agents": agents})
    all_caps = await discovery.list_all_capabilities()
    return ApiResponse(data={"capabilities": all_caps})
