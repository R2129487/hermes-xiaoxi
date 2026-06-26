from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from app_state import registry, store, delegator, audit_log
from dependencies import require_token
from models import ApiResponse, Task, TaskCreateRequest, TaskUpdateRequest

router = APIRouter()

@router.post("/api/tasks/create")
async def create_task(req: TaskCreateRequest, _token_payload: dict = Depends(require_token)):
    task = await delegator.create_task(req)
    audit_log.log("task_create", req.agent_id, {"task_type": req.task_type, "assigned_to": task.assigned_to})
    return ApiResponse(data={"task": task.model_dump()})

@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str, _token_payload: dict = Depends(require_token)):
    task_data = await store.get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail=ApiResponse(error="Task not found").model_dump())
    return ApiResponse(data={"task": task_data})

@router.post("/api/tasks/{task_id}/update")
async def update_task(task_id: str, req: TaskUpdateRequest, _token_payload: dict = Depends(require_token)):
    task_data = await store.get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail=ApiResponse(error="Task not found").model_dump())
    updated = await delegator.update_task(task_id, req)
    audit_log.log("task_update", req.agent_id, {"task_id": task_id, "status": req.status})
    return ApiResponse(data={"task": updated.model_dump()})

@router.get("/api/tasks")
async def list_tasks(agent_id: Optional[str] = None, status: Optional[str] = None, _token_payload: dict = Depends(require_token)):
    tasks = await store.list_tasks(agent_id=agent_id, status=status)
    return ApiResponse(data={"tasks": tasks, "count": len(tasks)})
