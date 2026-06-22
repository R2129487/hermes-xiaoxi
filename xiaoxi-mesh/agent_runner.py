#!/usr/bin/env python3
"""小希-Mesh 智能体接入脚本

每台机器运行此脚本即可自动连接到消息中转服务器。
用法:
    python3 agent_runner.py --agent xiaoqing
    python3 agent_runner.py --agent xiaobai
    python3 agent_runner.py --agent xiaolan
"""
import argparse
import asyncio
import json
import logging
import signal
import sys
import os

# 把当前目录加到路径，以便导入 client 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client import MeshClient
from executors import get_executors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("agent")

# ── 各智能体配置 ──

AGENT_CONFIGS = {
    "xiaoqing": {
        "name": "小青",
        "server": "ws://101.37.231.143:8765",
        "capabilities": [
            "code_generation", "file_transfer", "web_search",
            "translation", "desktop_automation", "wechat_operations"
        ],
        "specialties": ["编程开发", "文件管理", "网络搜索", "桌面自动化", "微信操作"],
        "description": "本机(Y7000)AI助手，擅长编程、文件管理、桌面自动化、微信消息处理",
    },
    "xiaobai": {
        "name": "小白",
        "server": "ws://101.37.231.143:8765",
        "capabilities": [
            "file_transfer", "system_monitor", "download_management",
            "ssh_operations", "web_search"
        ],
        "specialties": ["文件下载", "系统监控", "服务器运维", "下载站管理"],
        "description": "新云服务器AI助手，擅长文件处理、下载站管理、系统监控",
    },
    "xiaolan": {
        "name": "小蓝",
        "server": "ws://101.37.231.143:8765",
        "capabilities": [
            "system_monitor", "web_search", "code_generation",
            "data_analysis", "api_integration", "task_scheduling"
        ],
        "specialties": ["系统管理", "数据分析", "API集成", "任务调度"],
        "description": "阿里云服务器管理员，7x24在线，负责协调调度",
    },
}


class AgentRunner:
    """智能体运行器 - 自动连接、注册能力、处理消息"""

    def __init__(self, agent_id: str, token: str = None):
        if agent_id not in AGENT_CONFIGS:
            raise ValueError(f"未知智能体: {agent_id}，可选: {list(AGENT_CONFIGS.keys())}")

        cfg = AGENT_CONFIGS[agent_id]
        self.agent_id = agent_id
        self.name = cfg["name"]
        self.server_http = cfg["server"].replace("ws://", "http://").replace("wss://", "https://")
        self.server_ws = cfg["server"]
        self.token = token
        self.capabilities = cfg["capabilities"]
        self.specialties = cfg["specialties"]
        self.description = cfg["description"]
        self._running = False
        self.client = None
        
        # 加载执行器
        self.executors = get_executors(agent_id)
        log.info(f"   加载了 {len(self.executors)} 个执行器")

    async def _ensure_token(self):
        """确保有可用的 token：先尝试注册，已存在则用 admin 获取新 token"""
        if self.token:
            return

        import httpx
        async with httpx.AsyncClient(timeout=10) as http:
            # 1. 尝试注册（首次会成功并返回 token）
            try:
                r = await http.post(f"{self.server_http}/api/agents/register", json={
                    "agent_id": self.agent_id,
                    "name": self.name,
                    "role": "agent",
                    "capabilities": self.capabilities,
                    "specialties": self.specialties,
                    "description": self.description,
                })
                if r.status_code == 200:
                    data = r.json()
                    self.token = data.get("data", {}).get("token", "")
                    if self.token:
                        log.info(f"✅ 注册成功，已获取 token")
                        return
            except Exception as e:
                log.warning(f"注册失败: {e}")

            # 2. 已注册，用 admin 登录获取新 token
            log.info(f"智能体已存在，用 admin 获取 token...")
            try:
                r = await http.post(f"{self.server_http}/api/auth/login", json={
                    "username": "admin", "password": "admin123"
                })
                admin_token = r.json().get("data", {}).get("token", "")
                if not admin_token:
                    log.error("admin 登录失败")
                    return

                # 用 admin token 为智能体生成新 token
                r = await http.post(
                    f"{self.server_http}/api/tokens/create",
                    params={"agent_id": self.agent_id, "role": "agent"},
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
                if r.status_code == 200:
                    self.token = r.json().get("data", {}).get("token", "")
                    log.info(f"✅ 已获取新 token")
                else:
                    log.error(f"获取 token 失败: {r.status_code} {r.text[:100]}")
            except Exception as e:
                log.error(f"获取 token 异常: {e}")

    async def start(self):
        """启动智能体"""
        log.info(f"🚀 {self.name} 启动中...")

        # 确保有 token
        await self._ensure_token()
        if not self.token:
            log.error(f"❌ {self.name} 无法获取 token，退出")
            return

        # 创建客户端
        self.client = MeshClient(
            server_url=self.server_ws,
            agent_id=self.agent_id,
            token=self.token,
        )
        self.client.set_capabilities(self.capabilities, self.specialties)

        log.info(f"   能力: {', '.join(self.capabilities)}")

        # 设置回调
        self.client.on_message(self._handle_message)
        self.client.on_status(self._handle_status)

        # 连接并注册
        self._running = True
        try:
            await self.client.connect()
            log.info(f"✅ {self.name} 已连接到消息服务器")

            # 保持运行
            while self._running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            log.info(f"⏹ {self.name} 收到停止信号")
        except Exception as e:
            log.error(f"❌ {self.name} 异常: {e}")
        finally:
            await self.stop()

    async def stop(self):
        """停止智能体"""
        self._running = False
        if self.client:
            await self.client.disconnect()
        log.info(f"👋 {self.name} 已断开连接")

    async def _handle_message(self, msg: dict):
        """处理收到的消息"""
        msg_type = msg.get("type", "unknown")
        from_id = msg.get("from", "unknown")
        content = msg.get("content", "")

        if msg_type == "ping":
            return  # 心跳忽略

        log.info(f"📩 收到消息 [{msg_type}] 来自 {from_id}: {content[:100]}")

        # 根据消息类型处理
        if msg_type == "task":
            await self._handle_task(msg)
        elif msg_type == "agent_call":
            await self._handle_agent_call(msg)
        elif msg_type == "text":
            await self._handle_text(msg)
        else:
            log.info(f"   未处理的消息类型: {msg_type}")

    async def _handle_task(self, msg: dict):
        """处理任务委派"""
        task_id = msg.get("metadata", {}).get("task_id", "unknown")
        content = msg.get("content", "")
        from_id = msg.get("from", "")
        log.info(f"📋 收到任务 [{task_id}]: {content}")

        # 回复收到
        if self.client:
            await self.client.send(from_id, f"收到任务 [{task_id}]，开始执行...", "text")

            # TODO: 这里可以接入实际的任务执行逻辑
            # 暂时只回复收到
            await self.client.send(from_id, f"任务 [{task_id}] 执行完成", "text")

    async def _handle_agent_call(self, msg: dict):
        """处理跨智能体调用"""
        action = msg.get("content", "")
        params = msg.get("metadata", {}).get("params", {})
        from_id = msg.get("from", "")
        call_id = msg.get("call_id", "")
        
        log.info(f"📞 收到调用请求: {action}({json.dumps(params, ensure_ascii=False)[:100]})")

        # 查找执行器
        executor = self.executors.get(action)
        if not executor:
            error_msg = f"未找到执行器: {action}"
            log.warning(f"   {error_msg}")
            if self.client:
                await self.client.send(from_id, f"调用失败: {error_msg}", "text")
            return

        # 执行
        try:
            result = await executor(params)
            log.info(f"   执行结果: {json.dumps(result, ensure_ascii=False)[:200]}")
            
            # 发送结果
            if self.client:
                result_text = json.dumps(result, ensure_ascii=False, indent=2)
                await self.client.send(from_id, result_text, "text")
        except Exception as e:
            error_msg = f"执行异常: {str(e)}"
            log.error(f"   {error_msg}")
            if self.client:
                await self.client.send(from_id, error_msg, "text")

    async def _handle_text(self, msg: dict):
        """处理普通文本消息"""
        from_id = msg.get("from", "")
        content = msg.get("content", "")
        log.info(f"💬 [{from_id}]: {content}")

    def _handle_status(self, data: dict):
        """处理状态变更"""
        agent_id = data.get("agent_id", "")
        status = data.get("status", "")
        log.info(f"🔄 状态变更: {agent_id} -> {status}")


def main():
    parser = argparse.ArgumentParser(description="小希-Mesh 智能体接入脚本")
    parser.add_argument("--agent", "-a", required=True,
                        choices=list(AGENT_CONFIGS.keys()),
                        help="智能体ID")
    parser.add_argument("--token", "-t", default=None,
                        help="认证Token（不提供则尝试注册获取）")
    parser.add_argument("--list", "-l", action="store_true",
                        help="列出所有可用智能体")
    args = parser.parse_args()

    if args.list:
        print("可用智能体:")
        for aid, cfg in AGENT_CONFIGS.items():
            print(f"  {aid}: {cfg['name']} - {cfg['description']}")
            print(f"       能力: {', '.join(cfg['capabilities'])}")
        return

    runner = AgentRunner(args.agent, args.token)

    # 优雅关闭
    loop = asyncio.new_event_loop()

    def shutdown_handler():
        loop.create_task(runner.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown_handler)
        except NotImplementedError:
            pass  # Windows 不支持

    try:
        loop.run_until_complete(runner.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
