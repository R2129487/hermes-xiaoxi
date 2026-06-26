from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app_state import registry, store, delegator, discovery, audit_log
from dependencies import require_token
from models import ApiResponse
from decision_engine import extract_required_capability

router = APIRouter()

class DecideRequest(BaseModel):
    agent_id: str
    task_type: str
    context: dict = {}

class ExecuteRequest(BaseModel):
    agent_id: str
    target_agent: str
    task_type: str
    context: dict = {}

@router.post("/api/decisions/decide")
async def decide(req: DecideRequest, _token_payload: dict = Depends(require_token)):
    required_cap = extract_required_capability(req.task_type)
    if not required_cap:
        return ApiResponse(data={"decision": "no_delegation", "agent_id": req.agent_id, "reason": "no capability required"})
    suitable = await discovery.find_agents_by_capability(required_cap)
    if suitable:
        return ApiResponse(data={"decision": "delegate", "candidates": suitable, "required_capability": required_cap})
    return ApiResponse(data={"decision": "self", "agent_id": req.agent_id, "reason": "no suitable agent found"})

@router.post("/api/decisions/execute")
async def execute(req: ExecuteRequest, _token_payload: dict = Depends(require_token)):
    result = await delegator.delegate_task(req.agent_id, req.target_agent, req.task_type, req.context)
    audit_log.log("task_execute", req.agent_id, {"target": req.target_agent, "task_type": req.task_type, "success": result})
    return ApiResponse(data={"success": result, "task_type": req.task_type})
