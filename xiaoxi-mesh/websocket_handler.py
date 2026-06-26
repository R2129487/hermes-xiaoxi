"""WebSocket 连接管理与消息投递"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from app_state import (
    auth, store, connections, connection_lock,
    log, audit_log, registry, discovery, delegator, limits,
    brain,
)
from models import Message


async def _send_json(ws: WebSocket, data: dict):
    try:
        await ws.send_json(data)
    except Exception:
        pass


def _get_token(ws: WebSocket) -> Optional[str]:
    auth_header = ws.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    token = ws.query_params.get("token")
    return token


async def _send_to_agent(agent_id: str, data: dict):
    async with connection_lock:
        ws = connections.get(agent_id)
    if ws:
        await _send_json(ws, data)
    else:
        content = json.dumps(data.get("data", data))
        msg = Message(
            from_id="system",
            to_id=agent_id,
            type=data.get("type", "text"),
            content=content,
        )
        await store.save_message(msg)


async def _try_deliver(msg: Message):
    async with connection_lock:
        if msg.to_id == "broadcast":
            for aid, ws in list(connections.items()):
                if aid != msg.from_id:
                    await _send_json(ws, {
                        "type": "message",
                        "data": msg.model_dump(mode="json"),
                    })
            return
        ws = connections.get(msg.to_id)
    if ws:
        await _send_json(ws, {
            "type": "message",
            "data": msg.model_dump(mode="json"),
        })
        msg.delivered = True
        await store.mark_delivered(msg.id)


async def _send_broadcast(data: dict):
    async with connection_lock:
        targets = list(connections.values())
    await asyncio.gather(*[
        asyncio.wait_for(_send_json(ws, data), timeout=5)
        for ws in targets
    ], return_exceptions=True)


async def websocket_endpoint(ws: WebSocket, agent_id: str):
    token = _get_token(ws)
    log.info(f"[WS] 收到连接: agent_id={agent_id}, token={token[:20] if token else 'None'}...")
    if not token:
        log.warning(f"[WS] 缺少token, agent_id={agent_id}")
        await ws.close(code=4001, reason="缺少 token")
        return
    payload = auth.verify_token(token)
    if not payload:
        log.warning(f"[WS] token验证失败, agent_id={agent_id}")
        await ws.close(code=4001, reason="token 验证失败")
        return
    if payload.agent_id != agent_id:
        log.warning(f"[WS] agent_id不匹配: payload={payload.agent_id}, url={agent_id}")
        await ws.close(code=4001, reason="token 验证失败")
        return
    log.info(f"[WS] token验证通过, agent_id={agent_id}, role={payload.role}")
    agent = registry.get(agent_id)
    if not agent:
        log.info(f"[WS] 智能体未注册, agent_id={agent_id}, 自动注册")
        from models import Agent as AgentModel
        new_agent = AgentModel(
            agent_id=agent_id,
            name=agent_id,
            role=payload.role or "agent",
            online=True,
        )
        await store.register_agent(new_agent)
        await registry.register(new_agent)
        log.info(f"[WS] 智能体自动注册成功: agent_id={agent_id}")
    log.info(f"[WS] 执行accept, agent_id={agent_id}")
    await ws.accept()
    async with connection_lock:
        connections[agent_id] = ws
    registry.set_online(agent_id)
    await store.set_online(agent_id, True)
    await audit_log.log_login(agent_id, True)
    await _send_broadcast({
        "type": "status",
        "data": {"agent_id": agent_id, "status": "online", "name": agent.name},
    })
    undelivered = await store.get_undelivered(agent_id)
    for msg in undelivered:
        await _send_json(ws, {"type": "message", "data": msg.model_dump(mode="json")})
    await store.mark_all_delivered(agent_id)
    log.info(f"[{agent_id}] 已连接 (在线: {len(connections)})")
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send_json(ws, {"type": "error", "message": "JSON 格式错误"})
                continue
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await _send_json(ws, {"type": "pong"})
            elif msg_type == "send":
                to_raw = data.get("to")  # None 表示用户没指定目标
                to_id = to_raw or "broadcast"
                msg = Message(
                    from_id=agent_id,
                    to_id=to_id,
                    type=data.get("data_type", "text"),
                    content=data.get("content", ""),
                    priority=data.get("priority", "normal"),
                    reply_to=data.get("reply_to"),
                )
                if len(msg.content) > limits["max_message_size"]:
                    await _send_json(ws, {"type": "error", "message": "消息超过大小限制"})
                    continue
                await store.save_message(msg)
                # 智能路由：发给 admin 或未指定目标时，走 AgentBrain
                if brain and brain.enabled and (to_raw is None or to_id == "admin"):
                    decision = await brain.think(msg.content, agent_id, None)
                    log.info(
                        f"[AgentBrain] 决策: action={decision['action']}, "
                        f"target={decision.get('target_agent')}, "
                        f"reason={decision.get('reason')}"
                    )
                    if decision["action"] == "forward":
                        target = decision.get("target_agent")
                        if target:
                            msg.to_id = target
                            await _try_deliver(msg)
                            await audit_log.log_message(agent_id, target, msg.type)
                    elif decision["action"] == "reply":
                        await _send_json(ws, {
                            "type": "message",
                            "data": {
                                "from_id": "admin",
                                "to_id": agent_id,
                                "type": "text",
                                "content": decision.get("reply_content", ""),
                            },
                        })
                    else:
                        await _send_json(ws, {"type": "error", "message": decision.get("reply_content", "无法处理此消息")})
                else:
                    await _try_deliver(msg)
                    await audit_log.log_message(agent_id, msg.to_id, msg.type)
                await _send_json(ws, {
                    "type": "sent",
                    "data": {"message_id": msg.id},
                })
            elif msg_type == "status":
                status = data.get("status", "online")
                online = status == "online"
                if online:
                    registry.set_online(agent_id)
                else:
                    registry.set_offline(agent_id)
                await store.set_online(agent_id, online)
                await _send_broadcast({
                    "type": "status",
                    "data": {"agent_id": agent_id, "status": status},
                })
            elif msg_type == "task":
                to_id = data.get("to", "auto")
                task_desc = data.get("description", data.get("content", ""))
                required_caps = data.get("required_capabilities", [])
                task = await delegator.create_task(
                    description=task_desc,
                    required_capabilities=required_caps,
                    assigned_to=to_id,
                    assigned_by=agent_id,
                )
                await _send_json(ws, {
                    "type": "task_created",
                    "data": task.model_dump(mode="json"),
                })
            elif msg_type == "task_update":
                task_id = data.get("task_id", "")
                new_status = data.get("status", "")
                result = data.get("result", "")
                if task_id:
                    if new_status:
                        await store.update_task(task_id, status=new_status)
                    if result:
                        await store.update_task(task_id, result=result)
                    await _send_json(ws, {"type": "task_updated", "data": {"task_id": task_id}})
            elif msg_type == "agent_call":
                target_id = data.get("to", "")
                if target_id:
                    call_msg = {
                        "type": "agent_call",
                        "data": {
                            "from_id": agent_id,
                            "content": data.get("content", ""),
                            "call_id": data.get("call_id", ""),
                        }
                    }
                    await _send_to_agent(target_id, call_msg)
                    await _send_json(ws, {"type": "call_sent", "data": {"to": target_id}})
            elif msg_type == "task_request":
                target_id = data.get("to", "")
                if target_id:
                    task_req_msg = {
                        "type": "task_request",
                        "data": {
                            "task_id": data.get("task_id", ""),
                            "description": data.get("description", ""),
                            "required_capability": data.get("required_capability", ""),
                            "from_agent": agent_id,
                            "timeout": data.get("timeout", 10.0),
                        }
                    }
                    await _send_to_agent(target_id, task_req_msg)
                    await _send_json(ws, {"type": "task_request_sent", "data": {"to": target_id, "task_id": data.get("task_id", "")}})
            elif msg_type == "task_response":
                target_id = data.get("to", "")
                if target_id:
                    task_resp_msg = {
                        "type": "task_response",
                        "data": {
                            "task_id": data.get("task_id", ""),
                            "status": data.get("status", "accepted"),
                            "reason": data.get("reason", ""),
                        }
                    }
                    await _send_to_agent(target_id, task_resp_msg)
                    await _send_json(ws, {"type": "task_response_sent", "data": {"to": target_id, "task_id": data.get("task_id", "")}})
            elif msg_type == "capability_update":
                capabilities = data.get("capabilities", [])
                specialties = data.get("specialties", [])
                await registry.update_capabilities(agent_id, capabilities, specialties)
                await audit_log.log_capability_update(agent_id, capabilities)
                await _send_broadcast({
                    "type": "capability_update",
                    "data": {
                        "agent_id": agent_id,
                        "capabilities": capabilities,
                        "specialties": specialties,
                    }
                })
            elif msg_type == "discover":
                query = data.get("query", "")
                if query:
                    results = discovery.search_capabilities(query)
                    await _send_json(ws, {
                        "type": "discovery_result",
                        "data": [r.model_dump() for r in results],
                    })
                else:
                    matrix = discovery.get_capability_matrix()
                    await _send_json(ws, {
                        "type": "discovery_result",
                        "data": matrix,
                    })
    except WebSocketDisconnect:
        pass
    finally:
        async with connection_lock:
            connections.pop(agent_id, None)
        registry.set_offline(agent_id)
        await store.set_online(agent_id, False)
        await audit_log.log_logout(agent_id)
        await _send_broadcast({
            "type": "status",
            "data": {"agent_id": agent_id, "status": "offline"},
        })
        log.info(f"[{agent_id}] 已断开 (在线: {len(connections)})")
