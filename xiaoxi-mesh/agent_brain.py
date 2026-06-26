"""MESH 智能管理员（Agent Brain）
LLM 驱动，分析消息内容，自动路由到合适的智能体或直接回复。
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from openai import AsyncOpenAI

log = logging.getLogger("xiaoxi-mesh")

# 已知智能体的标准信息
KNOWN_AGENTS = {
    "xiaoqing": {
        "name": "小青",
        "description": "本机桌面助手，擅长编程、桌面自动化、微信操作、文件管理",
    },
    "xiaolan": {
        "name": "小蓝",
        "description": "阿里云服务器管理员，7×24在线，擅长服务器运维、网络监控",
    },
    "xiaobai": {
        "name": "小白",
        "description": "新云服务器执行人，擅长度文件处理、QQ操作、下载管理",
    },
    "task-dispatcher": {
        "name": "任务调度器",
        "description": "任务调度服务，负责创建、分配、跟踪和管理任务（如查看磁盘、执行操作、部署等具体事务）",
    },
}

SYSTEM_PROMPT_TEMPLATE = """你是MESH智能管理员，负责分析用户消息并决定由哪个智能体处理。

可用的智能体列表：
{agents_info}

决策规则：
- 编程、桌面自动化、本地操作、微信操作、文件管理 -> 小青
- 服务器运维、网络监控、阿里云相关 -> 小蓝
- QQ操作、文件下载、下载管理、新云服务器相关 -> 小白
- **任务类消息**：如果用户要求"做"某事、"执行"、操作、查看/检查状态、部署/发布等具体操作型请求 -> 任务调度器（task-dispatcher）
  - 例如："帮我查看磁盘"、"部署xxx"、"执行xxx"、"检查服务器状态"、"创建xxx"
- 如果只是简单问候、确认、感谢、闲聊等不需要特定技能的消息 -> 直接回复

输出格式（必须是纯 JSON，不要多余文字）：
1. 如果需要转发给某个智能体完成任务：
{   "action": "forward", "target_agent": "xiaoqing", "reason": "决策理由" }
2. 如果识别为任务型请求，转发给任务调度器：
{   "action": "forward", "target_agent": "task-dispatcher", "reason": "决策理由", "task_data": {{"title": "任务标题", "description": "任务描述"}} }
3. 如果可以直接回复：
{   "action": "reply", "reply_content": "你的回复内容", "reason": "决策理由" }
4. 如果出错或不明确：
{   "action": "error", "reply_content": "错误说明", "reason": "出错原因" }

注意：target_agent 必须是 xiaoqing、xiaolan、xiaobai、task-dispatcher 之一。"""


def _read_api_key(filepath: str) -> Optional[str]:
    """从文件中读取 API key。支持格式：
    - 纯 key 文本
    - "前缀：key" 格式（如"小黑：sk-xxx"）
    - 多行时取第一个有效 key
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return None
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            # "前缀：key" 或 "前缀:key"
            for sep in ("：", ":"):
                if sep in line:
                    line = line.split(sep, 1)[1].strip()
            if line.startswith("sk-"):
                return line
        # 没有 sk- 前缀，返回第一行
        first = content.splitlines()[0].strip()
        return first if first else None
    except FileNotFoundError:
        log.warning(f"[AgentBrain] API key 文件不存在: {filepath}")
        return None
    except Exception as e:
        log.warning(f"[AgentBrain] 读取 API key 文件失败: {e}")
        return None


class AgentBrain:
    """LLM 驱动的智能管理员"""

    def __init__(self, config: dict):
        self.enabled = config.get("enabled", False)
        self.provider = config.get("provider", "dreamfield")
        self.model = config.get("model", "deepseek-v4-flash")
        api_key_file = config.get("api_key_file", "")
        self.system_prompt = config.get("system_prompt", "")

        self.api_key = _read_api_key(api_key_file) if api_key_file else None
        if not self.api_key:
            log.warning("[AgentBrain] 无法获取 API key，将禁用智能管理员")
            self.enabled = False

        if self.enabled:
            # 构建可用智能体信息
            agents_lines = []
            for aid, info in KNOWN_AGENTS.items():
                agents_lines.append(
                    f"  - {info['name']}（{aid}）：{info['description']}"
                )
            agents_info_str = "\n".join(agents_lines)

            self._sys_prompt = (self.system_prompt or SYSTEM_PROMPT_TEMPLATE).format(
                agents_info=agents_info_str
            )

            # API 基础 URL
            base_urls = {
                "dreamfield": "https://www.dreamfield.top/v1",
                "mimo": "https://api.xiaomimimo.com/v1",
                "deepseek": "https://api.deepseek.com/v1",
            }
            base_url = base_urls.get(self.provider, f"https://api.{self.provider}.com/v1")

            self._client = AsyncOpenAI(
                base_url=base_url,
                api_key=self.api_key,
            )
            log.info(
                f"[AgentBrain] 已初始化: provider={self.provider}, "
                f"model={self.model}"
            )
        else:
            self._client = None
            self._sys_prompt = ""

    async def think(
        self, message_content: str, sender: str, available_agents: list | None = None
    ) -> dict:
        """分析消息，返回决策。

        参数:
            message_content: 用户发的消息内容
            sender: 发送者 agent_id
            available_agents: 当前在线智能体列表，与 KNOWN_AGENTS 合并

        返回:
            {"action": "forward"|"reply"|"error", "target_agent": ..., ...}
        """
        if not self.enabled or not self._client:
            return {
                "action": "error",
                "reply_content": "智能管理员未启用或配置不完整",
                "reason": "AgentBrain 未初始化",
            }

        # 构建当前在线智能体信息
        online_info = ""
        if available_agents:
            names = []
            for agent in available_agents:
                aid = agent.get("agent_id", agent.get("id", ""))
                name = agent.get("name", aid)
                desc = agent.get("description", "")
                caps = agent.get("capabilities", [])
                cap_str = f"（能力: {', '.join(caps)}）" if caps else ""
                names.append(f"  - {name}（{aid}）：{desc}{cap_str}")
            if names:
                online_info = "\n当前在线的智能体：\n" + "\n".join(names)

        messages = [
            {"role": "system", "content": self._sys_prompt + online_info},
            {
                "role": "user",
                "content": (
                    f"发送者：{sender}\n"
                    f"消息内容：{message_content}\n\n"
                    f"请分析这条消息并决定如何处理。"
                ),
            },
        ]

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=512,
            )
            raw = response.choices[0].message.content or ""
            result = json.loads(raw)
            action = result.get("action", "error")
            if action not in ("forward", "reply", "error"):
                action = "error"
            return {
                "action": action,
                "target_agent": result.get("target_agent"),
                "reply_content": result.get("reply_content", ""),
                "reason": result.get("reason", ""),
            }
        except json.JSONDecodeError:
            log.warning(f"[AgentBrain] LLM 返回非 JSON: {raw}")
            return {
                "action": "error",
                "reply_content": "智能管理员理解失败，请稍后再试",
                "reason": "LLM 返回格式错误",
            }
        except Exception as e:
            log.error(f"[AgentBrain] LLM 调用失败: {e}")
            return {
                "action": "error",
                "reply_content": "智能管理员暂时不可用，请稍后再试",
                "reason": f"LLM 调用异常: {e}",
            }
