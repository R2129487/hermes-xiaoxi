"""小希-Mesh v2 客户端 SDK

各智能体通过此 SDK 接入消息中转服务，支持能力声明、任务请求、智能体互相调用。

用法:
    client = MeshClient("ws://101.37.231.143:8765", "xiaoqing", "your-token")
    client.set_capabilities(["code_review", "translation"], ["python", "rust"])
    await client.connect()
    await client.send("xiaobai", "你好小白")
    await client.request_task("帮我审查这段代码")
"""
from __future__ import annotations
import asyncio
import json
import logging
import httpx
from typing import Callable, Optional

import websockets

log = logging.getLogger("xiaoxi-mesh-client")


class MeshClient:
    def __init__(self, server_url: str, agent_id: str, token: str):
        """初始化客户端

        Args:
            server_url: 服务器地址 (如 http://101.37.231.143:8765)
            agent_id: 智能体 ID
            token: JWT Token
        """
        self.server_url = server_url.rstrip("/")
        self.agent_id = agent_id
        self.token = token
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._on_message: Optional[Callable] = None
        self._on_status: Optional[Callable] = None
        self._on_task: Optional[Callable] = None
        self._on_agent_call: Optional[Callable] = None
        self._on_capability_update: Optional[Callable] = None
        self._on_task_request: Optional[Callable] = None
        self._on_task_response: Optional[Callable] = None
        self._capabilities: list[str] = []
        self._specialties: list[str] = []
        # 任务确认等待表: task_id → asyncio.Future
        self._pending_confirmations: dict = {}

    # ── 事件回调 ──

    def on_message(self, callback: Callable):
        """收到消息回调: callback(msg: dict)"""
        self._on_message = callback
        return self

    def on_status(self, callback: Callable):
        """状态变更回调: callback(data: dict)"""
        self._on_status = callback
        return self

    def on_task(self, callback: Callable):
        """收到任务回调: callback(data: dict)"""
        self._on_task = callback
        return self

    def on_agent_call(self, callback: Callable):
        """收到智能体调用回调: callback(data: dict)"""
        self._on_agent_call = callback
        return self

    def on_capability_update(self, callback: Callable):
        """能力更新回调: callback(data: dict)"""
        self._on_capability_update = callback
        return self

    def on_task_request(self, callback: Callable):
        """收到任务请求回调: callback(data: dict)"""
        self._on_task_request = callback
        return self

    def on_task_response(self, callback: Callable):
        """收到任务响应回调: callback(data: dict)"""
        self._on_task_response = callback
        return self

    # ── 能力管理 ──

    def set_capabilities(self, capabilities: list[str], specialties: list[str] = None):
        """设置自身能力（连接后自动上报）"""
        self._capabilities = capabilities
        self._specialties = specialties or []

    async def update_capabilities(self, capabilities: list[str],
                                   specialties: list[str] = None):
        """运行时更新能力"""
        self._capabilities = capabilities
        if specialties is not None:
            self._specialties = specialties
        if self.ws:
            await self.ws.send(json.dumps({
                "type": "capability_update",
                "capabilities": self._capabilities,
                "specialties": self._specialties,
            }))

    async def discover_capabilities(self, query: str = ""):
        """查询能力

        Args:
            query: 搜索关键词，空字符串返回全部能力矩阵
        """
        if not self.ws:
            log.warning("未连接")
            return None
        await self.ws.send(json.dumps({
            "type": "discover",
            "query": query,
        }))

    # ── 任务相关 ──

    async def request_task(self, description: str,
                           required_capabilities: list[str] = None,
                           target: str = "auto"):
        """请求任务（自动路由或指定目标）

        Args:
            description: 任务描述
            required_capabilities: 需要的能力
            target: 目标智能体 ID，"auto" 表示自动路由
        """
        if not self.ws:
            log.warning("未连接")
            return
        await self.ws.send(json.dumps({
            "type": "task",
            "to": target,
            "description": description,
            "required_capabilities": required_capabilities or [],
        }))

    async def update_task_status(self, task_id: str, status: str = "",
                                  result: str = ""):
        """更新任务状态"""
        if not self.ws:
            return
        data = {"type": "task_update", "task_id": task_id}
        if status:
            data["status"] = status
        if result:
            data["result"] = result
        await self.ws.send(json.dumps(data))

    async def complete_task(self, task_id: str, result: str = ""):
        """完成任务"""
        await self.update_task_status(task_id, "completed", result)

    # ── 智能体互相调用 ──

    async def call_agent(self, target_id: str, content: str,
                         call_id: str = "", params: dict = None):
        """调用其他智能体

        Args:
            target_id: 目标智能体 ID
            content: 调用内容/指令（capability名称）
            call_id: 调用 ID（用于追踪响应）
            params: 调用参数
        """
        if not self.ws:
            log.warning("未连接")
            return
        payload = {
            "type": "agent_call",
            "to": target_id,
            "content": content,
            "call_id": call_id,
        }
        if params:
            payload["metadata"] = {"params": params}
        await self.ws.send(json.dumps(payload))

    # ── 任务确认机制 ──

    async def send_task_request(self, target_id: str, task_id: str,
                                 description: str, required_capability: str = "",
                                 timeout: float = 10.0):
        """发送任务请求（需要对方确认）

        Args:
            target_id: 目标智能体 ID
            task_id: 任务 ID
            description: 任务描述
            required_capability: 所需能力
            timeout: 确认超时(秒)
        """
        if not self.ws:
            log.warning("未连接，任务请求未发送")
            return
        await self.ws.send(json.dumps({
            "type": "task_request",
            "to": target_id,
            "task_id": task_id,
            "description": description,
            "required_capability": required_capability,
            "from_agent": self.agent_id,
            "timeout": timeout,
        }))

    async def send_task_response(self, target_id: str, task_id: str,
                                  status: str = "accepted", reason: str = ""):
        """发送任务响应（ACCEPT/REJECT）

        Args:
            target_id: 发送方智能体 ID
            task_id: 任务 ID
            status: "accepted" 或 "rejected"
            reason: 拒绝原因（可选）
        """
        if not self.ws:
            log.warning("未连接，任务响应未发送")
            return
        await self.ws.send(json.dumps({
            "type": "task_response",
            "to": target_id,
            "task_id": task_id,
            "status": status,
            "reason": reason,
        }))

    async def wait_for_task_confirmation(self, task_id: str,
                                          timeout: float = 10.0) -> dict:
        """等待任务确认（阻塞直到收到响应或超时）

        Returns:
            {"status": "accepted"/"rejected"/"timed_out", "reason": "..."}
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_confirmations[task_id] = future
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return {"status": "timed_out", "reason": f"等待确认超时({timeout}s)"}
        finally:
            self._pending_confirmations.pop(task_id, None)

    # ── HTTP API 方法 ──

    async def query_task(self, task_id: str) -> Optional[dict]:
        """通过 HTTP 查询任务详情"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.server_url}/api/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self.token}"}
            )
            data = resp.json()
            return data.get("data") if data.get("success") else None

    async def list_tasks(self, status: str = None) -> list[dict]:
        """通过 HTTP 查询任务列表"""
        url = f"{self.server_url}/api/tasks"
        if status:
            url += f"?status={status}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {self.token}"})
            data = resp.json()
            return data.get("data", []) if data.get("success") else []

    async def discover_remote(self, query: str = "") -> dict:
        """通过 HTTP 查询能力"""
        url = f"{self.server_url}/api/capabilities"
        if query:
            url = f"{self.server_url}/api/capabilities/search/{query}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {self.token}"})
            data = resp.json()
            return data.get("data", {}) if data.get("success") else {}

    # ── 连接管理 ──

    async def connect(self):
        """连接到消息服务器（自动重连，连接后自动上报能力）"""
        uri = f"{self.server_url}/ws/{self.agent_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        self._running = True
        while self._running:
            try:
                self.ws = await websockets.connect(uri, ping_interval=30, extra_headers=headers)
                log.info(f"[{self.agent_id}] 已连接到消息服务器")

                # 连接后自动上报能力
                if self._capabilities:
                    await self.update_capabilities(self._capabilities, self._specialties)

                await self._listen()
            except (websockets.ConnectionClosed, OSError) as e:
                if self._running:
                    log.warning(f"[{self.agent_id}] 连接断开，5秒后重连: {e}")
                    await asyncio.sleep(5)
            except Exception as e:
                log.error(f"[{self.agent_id}] 连接异常: {e}")
                if self._running:
                    await asyncio.sleep(10)

    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self.ws:
            await self.ws.close()
            self.ws = None

    # ── 消息收发 ──

    async def send(self, to: str, content: str, msg_type: str = "text",
                   priority: str = "normal", reply_to: Optional[str] = None):
        """发送消息给指定智能体或 broadcast"""
        if not self.ws:
            log.warning("未连接，消息未发送")
            return None
        payload = {
            "type": "send",
            "to": to,
            "content": content,
            "data_type": msg_type,
            "priority": priority,
        }
        if reply_to:
            payload["reply_to"] = reply_to
        await self.ws.send(json.dumps(payload))

    async def broadcast(self, content: str, msg_type: str = "text"):
        """广播消息"""
        await self.send("broadcast", content, msg_type)

    async def update_status(self, status: str = "online",
                            message: Optional[str] = None):
        """更新在线状态"""
        if not self.ws:
            return
        payload = {"type": "status", "status": status}
        if message:
            payload["message"] = message
        await self.ws.send(json.dumps(payload))

    # ── 内部 ──

    async def _listen(self):
        """消息监听循环（连接断开后自动清理待确认任务）"""
        try:
            async for raw in self.ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                if msg_type == "pong":
                    continue

                elif msg_type == "message":
                    msg_data = data.get("data", {})
                    log.info(f"[{self.agent_id}] 收到来自 {msg_data.get('from_id')} 的消息")
                    if self._on_message:
                        await self._safe_call(self._on_message, msg_data)

                elif msg_type == "status":
                    status_data = data.get("data", {})
                    if self._on_status:
                        await self._safe_call(self._on_status, status_data)

                elif msg_type == "task":
                    task_data = data.get("data", {})
                    log.info(f"[{self.agent_id}] 收到任务: {task_data.get('task_id')}")
                    if self._on_task:
                        await self._safe_call(self._on_task, task_data)

                elif msg_type == "agent_call":
                    call_data = data.get("data", {})
                    log.info(f"[{self.agent_id}] 收到来自 {call_data.get('from_id')} 的调用")
                    if self._on_agent_call:
                        await self._safe_call(self._on_agent_call, call_data)

                elif msg_type == "capability_update":
                    cap_data = data.get("data", {})
                    if self._on_capability_update:
                        await self._safe_call(self._on_capability_update, cap_data)

                elif msg_type == "task_request":
                    req_data = data.get("data", {})
                    log.info(f"[{self.agent_id}] 收到任务请求: {req_data.get('task_id')}")
                    if self._on_task_request:
                        await self._safe_call(self._on_task_request, req_data)

                elif msg_type == "task_response":
                    resp_data = data.get("data", {})
                    log.info(f"[{self.agent_id}] 收到任务响应: {resp_data.get('task_id')} -> {resp_data.get('status')}")
                    # 解除 wait_for_task_confirmation 的等待
                    task_id = resp_data.get("task_id", "")
                    future = self._pending_confirmations.get(task_id)
                    if future and not future.done():
                        future.set_result(resp_data)
                    if self._on_task_response:
                        await self._safe_call(self._on_task_response, resp_data)

                elif msg_type == "discovery_result":
                    result_data = data.get("data", [])
                    log.info(f"[{self.agent_id}] 能力发现结果: {len(result_data)} 条")

                elif msg_type == "error":
                    log.warning(f"[{self.agent_id}] 服务端错误: {data.get('message')}")

                elif msg_type in ("sent", "task_created", "task_updated", "call_sent"):
                    pass  # 确认消息，静默处理
        finally:
            # 连接断开，清理所有待确认的 Future（防止协程泄漏）
            for task_id, future in list(self._pending_confirmations.items()):
                if not future.done():
                    future.set_exception(ConnectionError("WebSocket 连接已断开"))
            self._pending_confirmations.clear()

    async def _safe_call(self, callback, *args):
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            log.error(f"回调异常: {e}")
