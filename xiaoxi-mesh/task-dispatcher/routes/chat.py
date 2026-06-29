"""
调度员 - 聊天智能体 API 路由
轻量 LLM 调度代理：听懂用户需求 → 调 Task Dispatcher API 分派 → 回报
持久化存储，支持多智能体切换对话
"""
from __future__ import annotations

import json
import os
import asyncio
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from models import Task, TaskLog, now_str
from routes.auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])

# 全局引用，在 dispatcher.py 中注入
config: dict = None  # type: ignore
storage: object = None  # type: ignore
dispatcher_core: object = None  # type: ignore
mesh_client: object = None  # type: ignore
mesh_remote_client: object = None  # type: ignore

# MESH ID 映射（本地ID → 远程MESH上的实际ID）
AGENT_ID_MAP = {
    "xiao-lan": "xiaolan",
    "xiao-bai": "xiaobai",
    "xiao-qing": "xiaoqing",
    "xiao-hei": "xiaohei",
}

# ==================== MiMo LLM 客户端 ====================

_llm_client: Optional[httpx.AsyncClient] = None
_llm_config: dict = {}
_tools: list[dict] = []


def _load_llm_config():
    """从 config 加载 LLM 配置"""
    global _llm_config
    agent_cfg = config.get("dispatcher_agent", {})
    llm_cfg = agent_cfg.get("llm", {})
    key_path = llm_cfg.get("api_key_path", "")
    api_key = llm_cfg.get("api_key", "")

    if key_path:
        expanded = os.path.expanduser(key_path)
        if os.path.exists(expanded):
            with open(expanded, "r") as f:
                api_key = f.read().strip()

    _llm_config = {
        "base_url": llm_cfg.get("base_url", "https://api.xiaomimimo.com/v1"),
        "api_key": api_key,
        "model": llm_cfg.get("model", "mimo-v2-omni"),
        "max_tokens": llm_cfg.get("max_tokens", 2048),
        "temperature": llm_cfg.get("temperature", 0.7),
    }


async def _get_llm_client() -> httpx.AsyncClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = httpx.AsyncClient(timeout=60)
    return _llm_client


def _get_tools() -> list[dict]:
    """获取 function calling 工具定义"""
    if _tools:
        return _tools

    _tools.append({
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "创建新任务并自动分派给合适的智能体",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务标题"},
                    "description": {"type": "string", "description": "任务详细描述"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "required_skills": {"type": "string", "description": "所需能力，逗号分隔"},
                },
                "required": ["title", "description"],
            },
        },
    })
    _tools.append({
        "type": "function",
        "function": {
            "name": "get_task_status",
            "description": "获取任务状态和进度",
            "parameters": {"type": "object", "properties": {
                "task_id": {"type": "string"},
            }, "required": ["task_id"]},
        },
    })
    _tools.append({
        "type": "function",
        "function": {
            "name": "list_agents",
            "description": "获取可用智能体列表",
            "parameters": {"type": "object", "properties": {}},
        },
    })
    _tools.append({
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "查询记忆系统，获取各智能体的职责分工和任务分配规则。当不确定任务该分给谁时先查记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如'磁盘''网站''安全'"},
                },
                "required": ["query"],
            },
        },
    })
    return _tools


def _get_system_prompt(agent_id: str = "dispatcher") -> str:
    """获取系统 prompt，可按智能体不同返回不同 prompt"""
    agent_cfg = config.get("dispatcher_agent", {})
    agent_prompts = agent_cfg.get("agent_prompts", {})
    if agent_id in agent_prompts:
        return agent_prompts[agent_id]
    return agent_cfg.get("system_prompt", "你是「调度员」，一个任务调度智能体。听懂用户的请求，创建任务并跟踪进度。")


def _format_history_for_agent(history_rows: list[dict], current_message: str) -> str:
    """把最近20轮对话格式化成上下文，通过MESH转发给智能体"""
    parts = []
    for r in history_rows:
        role = r.get("role", "")
        content = r.get("content", "")
        if role == "system" or role == "tool" or not content:
            continue
        label = "用户" if role == "user" else "你"
        parts.append(f"{label}: {content}")
    # 只取最近20条 + 当前消息
    recent = parts[-20:] if len(parts) > 20 else parts
    recent.append(f"用户: {current_message}")
    return "\n".join(recent)


# ==================== Function 执行器 ====================

async def _execute_function(name: str, args: dict) -> dict:
    port = config.get("server", {}).get("port", 8767)

    if name == "create_task":
        title = args.get("title", "未命名任务")
        desc = args.get("description", "")
        priority = args.get("priority", "medium")
        skills = args.get("required_skills", "")

        task = Task(title=title, description=desc, priority=priority, required_skills=skills)
        created = await storage.create_task(task)
        await storage.add_log(TaskLog(
            task_id=created.id, action="created",
            details=f"调度员创建任务：{title}",
        ))
        dispatched = await dispatcher_core.auto_dispatch(created)
        return {
            "task_id": dispatched.id, "title": dispatched.title,
            "status": dispatched.status,
            "assigned_to": dispatched.assigned_to or "未分配",
            "message": f"任务已创建（ID: {dispatched.id}），状态：{dispatched.status}",
        }

    elif name == "get_task_status":
        task_id = args.get("task_id", "")
        result = await dispatcher_core.track_progress(task_id)
        return result if "error" not in result else {"error": result["error"]}

    elif name == "list_agents":
        agents = await storage.get_agents()
        return {"agents": [
            {"id": a.id, "name": a.name, "status": a.status,
             "capabilities": a.capabilities,
             "current_load": a.current_load, "max_load": a.max_load}
            for a in agents
        ]}

    elif name == "search_memory":
        query = args.get("query", "")
        if not query:
            return {"results": []}
        results = await storage.search_memory(query)
        return {"results": [
            {"key": r["key"], "value": r["value"], "category": r["category"]}
            for r in results
        ]}

    return {"error": f"未知 function: {name}"}


# ==================== LLM 调用 ====================

async def _call_llm(messages: list[dict], agent_id: str = "dispatcher") -> dict:
    client = await _get_llm_client()
    _load_llm_config()

    body = {
        "model": _llm_config["model"],
        "messages": messages,
        "max_tokens": _llm_config["max_tokens"],
        "temperature": _llm_config["temperature"],
        "tools": _get_tools(),
        "tool_choice": "auto",
    }

    resp = await client.post(
        f"{_llm_config['base_url']}/chat/completions",
        headers={
            "Authorization": f"Bearer {_llm_config['api_key']}",
            "Content-Type": "application/json",
        },
        json=body,
    )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {resp.status_code}")

    return resp.json()


# ==================== 持久化历史管理 ====================


async def _load_history(session_id: str, agent_id: str = "dispatcher") -> list[dict]:
    """从数据库加载历史，如果为空则插入 system prompt"""
    rows = await storage.get_chat_history(session_id)
    if not rows:
        # 新会话，写入 system prompt
        system_content = _get_system_prompt(agent_id)
        await storage.save_chat_message(session_id, "system", system_content)
        return [{"role": "system", "content": system_content}]

    # 转换 DB 行 → LLM messages
    messages = []
    for r in rows:
        role = r["role"]
        msg = {"role": role}
        if role == "tool":
            msg["tool_call_id"] = r["tool_call_id"]
            msg["content"] = r["content"]
        elif role == "assistant":
            msg["content"] = r.get("content") or ""
            if r.get("tool_calls"):
                msg["tool_calls"] = r["tool_calls"]
        else:
            msg["content"] = r.get("content") or ""
        messages.append(msg)

    # 确保第一条是 system
    if not messages or messages[0]["role"] != "system":
        system_content = _get_system_prompt(agent_id)
        messages.insert(0, {"role": "system", "content": system_content})

    return messages


async def _save_message(session_id: str, role: str, content: str,
                         tool_calls: list = None, tool_call_id: str = None,
                         user_id: str = None):
    """保存消息到数据库（带日志）"""
    tc_str = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
    try:
        row_id = await storage.save_chat_message(session_id, role, content or "",
                                                 tool_calls=tc_str, tool_call_id=tool_call_id,
                                                 user_id=user_id)
        if row_id:
            print(f"[Chat] 💾 已保存: session={session_id} role={role} user={user_id} id={row_id}")
        else:
            print(f"[Chat] ⚠️ 保存返回0: session={session_id} role={role} user={user_id}")
    except Exception as e:
        print(f"[Chat] ❌ _save_message 异常: session={session_id} role={role} err={e}")


# ==================== API 路由 ====================


@router.post("")
async def chat(request: dict, user=Depends(get_current_user)):
    """
    聊天接口（异步）：接收消息 → 创建任务 → 后台处理
    返回 task_id，前端轮询 /api/chat/status/{task_id} 获取状态和回复
    """
    import uuid
    message = request.get("message", "").strip()
    session_id = request.get("session_id", "default")
    agent_id = request.get("agent_id", "dispatcher")

    if not message:
        return {"code": 1, "message": "消息不能为空"}

    # 刷新用户 last_seen（标记在线）
    agent_id_self = f"user_{user.id}"
    existing = await storage.get_agent(agent_id_self)
    if existing:
        await storage.update_agent(agent_id_self, {"last_seen": now_str()})

    task_id = uuid.uuid4().hex[:12]
    await storage.create_message_task(task_id, session_id, message, agent_id, user.id)

    # 后台异步处理
    asyncio.create_task(_process_message(task_id, message, session_id, agent_id, user))

    return {"code": 0, "data": {"task_id": task_id, "status": "received", "detail": "服务器已收到"}}


async def _process_message(task_id: str, message: str, session_id: str, agent_id: str, user):
    """后台异步处理消息，逐步更新状态"""
    print(f"[Chat] 📨 收到消息: task={task_id} agent={agent_id} session={session_id} user={user.id}")
    try:
        await storage.update_message_task(task_id, "processing", "处理中")
        # ── 用户间私聊 ──
        target_user = await storage.get_user(user_id=agent_id)
        if target_user is not None:
            await storage.update_message_task(task_id, "forwarding", f"转发至 {target_user.display_name or target_user.username}")
            # 存到发送者的会话
            await _save_message(session_id, "user", message, user_id=user.id)
            # 存到接收者的会话（双向同步）
            # 用排序保证双方用同一 session ID
            ids = sorted([user.id, agent_id])
            peer_session = f"session_user_{ids[0]}_{ids[1]}"
            await _save_message(peer_session, "user", message, user_id=user.id)
            # 标记完成（用户间消息不需要等待回复）
            await storage.update_message_task(task_id, "completed", "已送达")
            return

        # ── 本地智能体（xiao-qing）──
        if agent_id == "xiao-qing":
            await storage.update_message_task(task_id, "forwarding", "转至 小青")
            await _save_message(session_id, "user", message, user_id=user.id)

            # 写入 inbox 给 watcher
            import json as _json
            inbox_dir = '/tmp/hermes_mesh_inbox/'
            os.makedirs(inbox_dir, exist_ok=True)
            inbox_path = os.path.join(inbox_dir, f'{task_id}.json')
            with open(inbox_path, 'w') as f:
                _json.dump({
                    'task_id': task_id,
                    'from': user.id,
                    'message': message,
                    'session': session_id,
                    'time': __import__("models").now_str(),
                }, f, ensure_ascii=False)

            # 等待 watcher/智能体回复（最多等 60 秒）
            import asyncio
            for _ in range(60):
                await asyncio.sleep(1)
                task = await storage.get_message_task(task_id)
                if task and task["status"] in ("completed", "failed"):
                    break
            return

        # ── 其他智能体：通过 MESH 转发（只发最新消息，不带历史）──
        if agent_id != "dispatcher":
            await storage.update_message_task(task_id, "forwarding", f"转至 {agent_id}")
            await _save_message(session_id, "user", message, user_id=user.id)

            client = mesh_client
            if client:
                target_id = AGENT_ID_MAP.get(agent_id, agent_id)
                # 直接转发最新消息，不带历史上下文
                reply = await client.send_to_agent(target_id, message, timeout=60)
                if reply:
                    await storage.update_message_task(task_id, "completed", "已回复", reply)
                    await _save_message(session_id, "assistant", reply, user_id=user.id)
                    return
            await storage.update_message_task(task_id, "failed", f"智能体 {agent_id} 未回复")
            return

        # ── 调度员：走 MiMo LLM ──
        history = await _load_history(session_id, agent_id)
        history.append({"role": "user", "content": message})
        await _save_message(session_id, "user", message, user_id=user.id)

        max_rounds = 5
        for _round in range(max_rounds):
            llm_response = await _call_llm(history)
            choice = llm_response.get("choices", [{}])[0]
            msg = choice.get("message", {})

            if not msg:
                await storage.update_message_task(task_id, "failed", "LLM 返回为空")
                return

            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                reply = msg.get("content", "好的，已处理完成。")
                await storage.update_message_task(task_id, "completed", "已回复", reply)
                await _save_message(session_id, "assistant", reply, user_id=user.id)
                return

            history.append({
                "role": "assistant",
                "content": msg.get("content", ""),
                "tool_calls": tool_calls,
            })
            await _save_message(session_id, "assistant", msg.get("content", ""),
                                 tool_calls=tool_calls, user_id=user.id)

            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name", "")
                func_args_str = tc.get("function", {}).get("arguments", "{}")
                try:
                    func_args = json.loads(func_args_str)
                except json.JSONDecodeError:
                    func_args = {}
                try:
                    result = await _execute_function(func_name, func_args)
                except Exception as e:
                    result = {"error": str(e)}
                result_str = json.dumps(result, ensure_ascii=False)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result_str,
                })
                await _save_message(session_id, "tool", result_str,
                                     tool_call_id=tc.get("id", ""), user_id=user.id)

        # 达到最大轮次
        final = history[-1].get("content", "请求处理完毕，但未能给出最终回复。")
        await storage.update_message_task(task_id, "completed", "已处理", final)
        await _save_message(session_id, "assistant", final, user_id=user.id)

    except Exception as e:
        await storage.update_message_task(task_id, "failed", str(e))


# 状态查询 API
@router.get("/status/{task_id}")
async def get_message_status(task_id: str):
    """查询消息处理状态"""
    task = await storage.get_message_task(task_id)
    if not task:
        return {"code": 1, "message": "任务不存在"}
    return {"code": 0, "data": task}


@router.post("/status/update")
async def update_message_status(request: dict):
    """更新消息任务状态（智能体回调用）"""
    task_id = request.get("task_id", "")
    status = request.get("status", "")
    detail = request.get("detail", "")
    if not task_id or not status:
        return {"code": 1, "message": "缺少 task_id 或 status"}
    ok = await storage.update_message_task(task_id, status, detail)
    return {"code": 0 if ok else 1, "data": {"task_id": task_id, "status": status}}


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str = "default", user=Depends(get_current_user)):
    """获取聊天历史（过滤掉 system 消息，简化工具有用信息）"""
    try:
        rows = await storage.get_chat_history(session_id, user_id=user.id)
        clean = []
        for r in rows:
            if r["role"] == "system":
                continue
            item = {"role": r["role"], "content": r.get("content", "")}
            item["timestamp"] = r.get("timestamp", "")
            if r["role"] not in ("tool",) and not (r["role"] == "assistant" and not r.get("content")):
                clean.append(item)
        return {"code": 0, "data": {"session_id": session_id, "messages": clean}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions(user=Depends(get_current_user)):
    """获取当前用户的会话列表"""
    try:
        sessions = await storage.get_sessions(user_id=user.id)
        result = []
        for s in sessions:
            sid = s["session_id"]
            title = await storage.get_session_title(sid, user_id=user.id)
            result.append({
                "session_id": sid,
                "title": title,
                "last_time": s.get("last_time", ""),
            })
        return {"code": 0, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, user=Depends(get_current_user)):
    """删除会话"""
    try:
        await storage.delete_session(session_id, user_id=user.id)
        return {"code": 0, "message": "已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_chat_agents():
    """获取可聊天的智能体列表（DB智能体 + 配置了 agent_prompts 的）"""
    try:
        from datetime import datetime, timezone, timedelta
        # 从 DB 获取所有智能体
        db_agents = await storage.get_agents()
        # 从配置获取 agent_prompts
        agent_cfg = config.get("dispatcher_agent", {})
        configured_prompts = agent_cfg.get("agent_prompts", {})

        result = []
        now = datetime.now(timezone.utc)
        offline_threshold = timedelta(minutes=5)  # 5分钟不活跃=离线

        # 智能体样式
        AGENT_STYLES = {
            "dispatcher": {"avatar": "调", "color": "#3498db"},
            "xiao-qing": {"avatar": "青", "color": "#e67e22"},
            "xiao-lan":  {"avatar": "蓝", "color": "#3498db"},
            "xiao-bai":  {"avatar": "白", "color": "#95a5a6"},
            "xiao-hei":  {"avatar": "黑", "color": "#e74c3c"},
        }
        for agent in db_agents:
            style = AGENT_STYLES.get(agent.id, {})
            is_configured = agent.id in configured_prompts

            # user 类型：根据 last_seen 判断在线状态
            status = agent.status
            if agent.type == "user" and agent.last_seen:
                try:
                    last_seen_dt = datetime.fromisoformat(agent.last_seen)
                    if last_seen_dt.tzinfo is None:
                        last_seen_dt = last_seen_dt.replace(tzinfo=timezone.utc)
                    if now - last_seen_dt > offline_threshold:
                        status = "offline"
                except (ValueError, TypeError):
                    status = "offline"

            result.append({
                "id": agent.id,
                "name": agent.name,
                "nickname": agent.nickname or "",
                "type": agent.type if hasattr(agent, 'type') else 'agent',
                "avatar": style.get("avatar", agent.name[0] if agent.name else "?"),
                "avatar_color": agent.avatar_color if hasattr(agent, 'avatar_color') and agent.avatar_color else 0xFF888888,
                "pinned": agent.pinned if hasattr(agent, 'pinned') and agent.pinned else False,
                "color": style.get("color", "#95a5a6"),
                "status": status,
                "capabilities": agent.capabilities,
                "description": configured_prompts.get(agent.id, "")[:50] if configured_prompts.get(agent.id) else "",
                "has_prompt": is_configured,
                "group": "member",
            })

        return {"code": 0, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/settings")
async def update_agent_settings(agent_id: str, body: dict):
    """更新智能体用户设置（备注名、头像颜色等）"""
    try:
        from models import now_str
        allowed = {"nickname", "avatar_color", "pinned", "capabilities"}
        clean = {k: v for k, v in body.items() if k in allowed}
        if not clean:
            return {"code": 1, "message": "没有可更新的字段"}
        clean["last_seen"] = now_str()
        ok = await storage.update_agent(agent_id, clean)
        if ok:
            return {"code": 0, "message": "设置已更新"}
        return {"code": 1, "message": "智能体不存在"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reply")
async def agent_reply(request: dict):
    """智能体回复接口：将回复写入会话，可选更新消息任务状态"""
    try:
        session_id = request.get("session_id", "")
        content = request.get("content", "").strip()
        task_id = request.get("task_id", "")
        status = request.get("status", "completed")
        user_id = request.get("user_id", "")
        if not session_id or not content:
            return {"code": 1, "message": "缺少 session_id 或 content"}
        await _save_message(session_id, "assistant", content, user_id=user_id or None)
        # 如果有 task_id，更新消息任务状态
        if task_id:
            detail = "智能体已回复" if status == "completed" else status
            await storage.update_message_task(task_id, status, detail, content)
        return {"code": 0, "data": {"reply": content, "session_id": session_id}}
    except Exception as e:
        return {"code": 1, "message": str(e)}