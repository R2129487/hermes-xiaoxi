"""
CodeBuddy MESH 桥接代理 — 在 Windows 上运行

把小黑 Windows 上的 CodeBuddy 变成 MESH 网络的一个编程节点。

用法:
    python codebuddy_bridge.py [--server ws://101.37.231.143:8765] [--token YOUR_TOKEN]

如果没指定 token，会自动通过 /api/auth/login 获取。
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("codebuddy-bridge")

# ── 配置 ──
MESH_SERVER = os.environ.get("MESH_SERVER", "ws://101.37.231.143:8765")
MESH_HTTP = MESH_SERVER.replace("ws://", "http://").replace("wss://", "https://")
AGENT_ID = "codebuddy"
AGENT_NAME = "CodeBuddy"
AGENT_CAPABILITIES = [
    "code_generation",
    "code_review",
    "debugging",
    "refactoring",
    "python_development",
    "javascript_development",
    "file_operations",
]
AGENT_SPECIALTIES = ["python", "javascript", "html", "css", "windows"]
WORK_DIR = Path(os.environ.get("CODEBUDDY_WORK_DIR", str(Path.home() / "codebuddy-work")))
MCP_CONFIG = Path.home() / ".codebuddy" / "mcp.json"


class CodeBuddyBridge:
    """MESH 桥接代理 — 把 CodeBuddy 挂到 MESH 网络上"""

    def __init__(self, server: str, agent_id: str, token: str = ""):
        self.server = server
        self.agent_id = agent_id
        self.token = token
        self.ws = None
        self._running = False
        self._http = httpx.AsyncClient(timeout=30)
        WORK_DIR.mkdir(parents=True, exist_ok=True)

    # ── 生命周期 ──

    async def run(self):
        """主循环：连接 → 注册 → 监听"""
        self._running = True

        # 1. 获取 token（如果没提供）
        if not self.token:
            await self._login()

        # 2. 注册到 MESH
        await self._register()

        # 3. 连接 WebSocket
        while self._running:
            try:
                async with websockets.connect(
                    f"{self.server}/ws/{self.agent_id}",
                    extra_headers={"Authorization": f"Bearer {self.token}"},
                    ping_interval=30,
                ) as ws:
                    self.ws = ws
                    log.info(f"[{self.agent_id}] ✅ 已连接到 MESH")
                    await self._listen(ws)
            except websockets.ConnectionClosed:
                log.warning(f"[{self.agent_id}] 连接断开，5秒后重连")
                await asyncio.sleep(5)
            except Exception as e:
                log.error(f"[{self.agent_id}] 连接异常: {e}")
                await asyncio.sleep(10)

    async def stop(self):
        """停止"""
        self._running = False
        if self.ws:
            await self.ws.close()
        await self._http.aclose()

    # ── 认证 ──

    async def _login(self):
        """通过 admin 账号获取 token"""
        admin_pwd = os.environ.get("MESH_ADMIN_PASSWORD", "")
        if not admin_pwd:
            log.error("未设置 MESH_ADMIN_PASSWORD 环境变量，无法自动获取 token")
            sys.exit(1)

        http_url = MESH_SERVER.replace("ws://", "http://")
        resp = await self._http.post(
            f"{http_url}/api/auth/login",
            json={"username": "admin", "password": admin_pwd},
        )
        if resp.status_code != 200:
            log.error(f"登录失败: {resp.status_code} {resp.text}")
            sys.exit(1)

        data = resp.json().get("data", {})
        self.token = data.get("token", "")
        log.info(f"[{self.agent_id}] 🔑 已获取 token (角色: {data.get('role')})")

    async def _register(self):
        """注册到 MESH（如果未注册的话）"""
        http_url = MESH_SERVER.replace("ws://", "http://")
        resp = await self._http.post(
            f"{http_url}/api/agents/register",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "agent_id": self.agent_id,
                "name": self.agent_name,
                "role": "agent",
                "capabilities": AGENT_CAPABILITIES,
                "specialties": AGENT_SPECIALTIES,
                "description": "CodeBuddy Windows 编程节点",
                "platform": {"os": "windows", "version": sys.platform},
            },
        )

        if resp.status_code == 409:
            log.info(f"[{self.agent_id}] 📋 已注册过，跳过")
        elif resp.status_code == 200:
            log.info(f"[{self.agent_id}] ✅ 注册成功")
        else:
            log.warning(f"[{self.agent_id}] 注册返回: {resp.status_code} {resp.text}")

    # ── 消息处理 ──

    async def _listen(self, ws):
        """监听 MESH 消息"""
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await ws.send(json.dumps({"type": "pong"}))

                elif msg_type == "message":
                    msg_data = data.get("data", {})
                    log.info(f"📩 收到消息: {msg_data.get('content', '')[:80]}")
                    # 普通消息，记录即可
                    await ws.send(json.dumps({
                        "type": "sent",
                        "data": {"message_id": msg_data.get("id", "")},
                    }))

                elif msg_type == "task":
                    task_data = data.get("data", {})
                    log.info(f"📋 收到任务: {task_data.get('description', '')[:80]}")
                    asyncio.create_task(self._handle_task(ws, task_data))

                elif msg_type == "task_request":
                    req_data = data.get("data", {})
                    log.info(f"📋 收到任务请求: {req_data.get('description', '')[:80]}")
                    asyncio.create_task(self._handle_task_request(ws, req_data))

        except websockets.ConnectionClosed:
            raise

    async def _handle_task(self, ws, task_data: dict):
        """处理编程任务"""
        task_id = task_data.get("task_id", "")
        description = task_data.get("description", "")
        required_caps = task_data.get("required_capabilities", [])

        # 创建工作目录
        task_dir = WORK_DIR / f"task_{task_id}"
        task_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 执行任务 & 收集结果
            result = await self._execute_task(description, task_dir)

            # 报告完成
            await ws.send(json.dumps({
                "type": "task_update",
                "task_id": task_id,
                "status": "completed",
                "result": result,
            }))
            log.info(f"[{self.agent_id}] ✅ 任务 {task_id} 完成")

        except Exception as e:
            log.error(f"[{self.agent_id}] ❌ 任务 {task_id} 失败: {e}")
            await ws.send(json.dumps({
                "type": "task_update",
                "task_id": task_id,
                "status": "failed",
                "result": str(e),
            }))

    async def _handle_task_request(self, ws, req_data: dict):
        """处理任务请求（需要确认）"""
        task_id = req_data.get("task_id", "")
        description = req_data.get("description", "")
        from_agent = req_data.get("from_agent", "")

        # 自动接受（无头模式）
        await ws.send(json.dumps({
            "type": "task_response",
            "to": from_agent,
            "task_id": task_id,
            "status": "accepted",
            "reason": "CodeBuddy bridge 自动接受",
        }))

        # 执行
        task_dir = WORK_DIR / f"task_{task_id}"
        task_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = await self._execute_task(description, task_dir)

            # 发送完成通知
            await ws.send(json.dumps({
                "type": "task_completed",
                "data": {
                    "task_id": task_id,
                    "agent_id": self.agent_id,
                    "result": result,
                },
            }))
            log.info(f"[{self.agent_id}] ✅ 任务请求 {task_id} 完成")

        except Exception as e:
            log.error(f"[{self.agent_id}] ❌ 任务请求 {task_id} 失败: {e}")

    # ── 任务执行 ──

    async def _execute_task(self, description: str, task_dir: Path) -> str:
        """执行编程任务，返回结果"""
        # 1. 从描述中提取文件操作
        code_info = self._parse_code_request(description)

        # 2. 写代码文件
        output = []
        for file_info in code_info.get("files", []):
            file_path = task_dir / file_info["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file_info["content"], encoding="utf-8")
            output.append(f"📄 已创建: {file_info['path']}")

        # 3. 如果有运行命令，执行
        run_cmd = code_info.get("run")
        if run_cmd:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *run_cmd.split(),
                    cwd=str(task_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=60
                )
                if stdout:
                    output.append(f"\n📊 输出:\n{stdout.decode('utf-8', errors='replace')}")
                if stderr:
                    output.append(f"\n⚠️ 错误:\n{stderr.decode('utf-8', errors='replace')}")
                output.append(f"\n✅ 退出码: {proc.returncode}")
            except asyncio.TimeoutError:
                output.append("\n⏰ 执行超时")

        # 4. 列出工作目录内容
        files = list(task_dir.iterdir())
        if files:
            output.append(f"\n📁 文件列表:")
            for f in files:
                size = f.stat().st_size
                output.append(f"  {'📄' if f.is_file() else '📁'} {f.name} ({size:,} bytes)")

        return "\n".join(output)

    def _parse_code_request(self, description: str) -> dict:
        """解析任务描述，提取代码请求结构"""
        # 简单的启发式解析
        # 实际可以调用 LLM 来解析，但这里先用简单规则
        result = {"files": [], "run": None}

        # 检测语言
        lang_keywords = {
            "python": [".py", "python", "def ", "import "],
            "javascript": [".js", "function", "const ", "let "],
            "html": [".html", "<html", "<!DOCTYPE"],
            "css": [".css", "{", ":"],
        }

        # 如果描述中包含明显的代码，直接写一个脚本
        lines = description.split("\n")
        code_lines = []
        in_code = False
        code_lang = "python"
        file_name = "script.py"

        for line in lines:
            if line.startswith("```"):
                if in_code:
                    break
                in_code = True
                # 提取语言
                lang = line[3:].strip().lower()
                if lang in ("py", "python"):
                    file_name = "script.py"
                elif lang in ("js", "javascript"):
                    file_name = "script.js"
                elif lang in ("html",):
                    file_name = "index.html"
                continue
            if in_code:
                code_lines.append(line)

        if code_lines:
            result["files"].append({
                "path": file_name,
                "content": "\n".join(code_lines),
            })
        else:
            # 没有代码块，尝试把描述当作自然语言任务
            # 创建一个 README 记录任务
            result["files"].append({
                "path": "README.md",
                "content": f"# 任务: {description}\n\n创建时间: {datetime.now().isoformat()}\n\n由 MESH 自动分配至 CodeBuddy 节点",
            })

        return result

    @property
    def agent_name(self) -> str:
        try:
            import platform
            return f"CodeBuddy@{platform.node()}"
        except Exception:
            return "CodeBuddy@Windows"


# ── 入口 ──

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="CodeBuddy MESH Bridge Agent")
    parser.add_argument("--server", default=MESH_SERVER, help="MESH 服务器地址")
    parser.add_argument("--token", default="", help="JWT Token（留空自动获取）")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    bridge = CodeBuddyBridge(
        server=args.server,
        agent_id=AGENT_ID,
        token=args.token,
    )

    try:
        await bridge.run()
    except KeyboardInterrupt:
        log.info("👋 正在关闭...")
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
