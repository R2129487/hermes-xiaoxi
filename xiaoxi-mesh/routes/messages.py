from typing import Optional
from fastapi import APIRouter, Depends
from app_state import registry, store, delegator, audit_log, cfg
from dependencies import optional_token, require_token
from models import ApiResponse, Message

router = APIRouter()

@router.get("/api/messages/undelivered")
async def get_undelivered_messages(agent_id: str, _token_payload: Optional[dict] = Depends(optional_token)):
    msgs = await store.get_undelivered(agent_id)
    return ApiResponse(data={"messages": msgs, "count": len(msgs)})

@router.post("/api/messages/send")
async def send_message(msg: Message, _token_payload: Optional[dict] = Depends(require_token)):
    await store.save_message(msg)
    await delegator.deliver(msg)
    if _token_payload:
        audit_log.log("message_send", msg.sender, {"target": msg.receiver, "msg_type": msg.msg_type})
    return ApiResponse(data={"message_id": msg.message_id, "status": "sent"})
