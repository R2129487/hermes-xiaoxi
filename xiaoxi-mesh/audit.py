"""小希-Mesh v2 审计日志模块

记录所有关键操作：登录、消息发送、任务分配、权限变更。
支持异常行为检测（简单频率限制）。
"""
from __future__ import annotations
import json
import logging
import time
from datetime import datetime, timezone
from collections import defaultdict

import aiosqlite

from models import AuditLog

log = logging.getLogger("xiaoxi-mesh.audit")


class AuditLogger:
    """审计日志记录器

    记录所有关键操作，支持异常行为检测。
    """

    def __init__(self, storage, rate_limit_window: int = 60, rate_limit_max: int = 100):
        """初始化审计日志记录器

        Args:
            storage: 存储层实例
            rate_limit_window: 频率限制窗口（秒）
            rate_limit_max: 窗口内最大操作次数
        """
        self._storage = storage
        self._rate_limit_window = rate_limit_window
        self._rate_limit_max = rate_limit_max
        # 内存中的操作频率计数: {agent_id: {action: [(timestamp, count)]}}
        self._rate_counters: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        # 异常告警阈值（仅用于告警，不阻断）
        self._alert_threshold = rate_limit_max * 2
        # 持久化连接（延迟初始化）
        self._rate_db: aiosqlite.Connection | None = None

    async def close(self):
        """关闭持久化连接"""
        if self._rate_db is not None:
            await self._rate_db.close()
            self._rate_db = None

    async def log(self, agent_id: str = "", action: str = "", target: str = "",
                  result: str = "success", details: str = "") -> bool:
        """记录审计日志

        Args:
            agent_id: 操作智能体
            action: 操作类型 (login, logout, message_send, task_create, task_assign, capability_update, permission_change)
            target: 操作目标
            result: 结果 (success, failure, denied)
            details: 额外详情 (JSON 字符串)

        Returns:
            True 表示记录成功；False 表示因频率超限而被拒绝
        """
        allowed = await self._check_rate_limit(agent_id, action)
        if not allowed:
            return False

        entry = AuditLog(
            timestamp=datetime.now(timezone.utc),
            agent_id=agent_id,
            action=action,
            target=target,
            result=result,
            details=details,
        )
        await self._storage.save_audit_log(entry)
        log.info(f"[审计] {agent_id} {action} -> {target} ({result})")

        # 异常行为告警（仅记录不阻断）
        if not allowed:
            pass  # 已在 _check_rate_limit 中记录警告
        return True

    async def log_login(self, agent_id: str, success: bool = True) -> bool:
        """记录登录事件"""
        return await self.log(
            agent_id=agent_id,
            action="login",
            target=agent_id,
            result="success" if success else "failure",
        )

    async def log_logout(self, agent_id: str) -> bool:
        """记录登出事件"""
        return await self.log(
            agent_id=agent_id,
            action="logout",
            target=agent_id,
        )

    async def log_message(self, from_id: str, to_id: str, msg_type: str = "text") -> bool:
        """记录消息发送"""
        return await self.log(
            agent_id=from_id,
            action="message_send",
            target=to_id,
            details=json.dumps({"type": msg_type})
        )

    async def log_task(self, agent_id: str, task_id: str, action: str = "task_create") -> bool:
        """记录任务操作"""
        return await self.log(
            agent_id=agent_id,
            action=action,
            target=task_id,
        )

    async def log_capability_update(self, agent_id: str, capabilities: list[str]) -> bool:
        """记录能力更新"""
        return await self.log(
            agent_id=agent_id,
            action="capability_update",
            target=agent_id,
            details=json.dumps({"capabilities": capabilities})
        )

    async def log_permission_change(self, admin_id: str, target_role: str, details: str = "") -> bool:
        """记录权限变更"""
        return await self.log(
            agent_id=admin_id,
            action="permission_change",
            target=target_role,
            details=details,
        )

    async def get_logs(self, limit: int = 100, agent_id: str = None,
                       action: str = None) -> list[AuditLog]:
        """获取审计日志"""
        return await self._storage.get_audit_logs(limit, agent_id, action)

    async def get_recent_activity(self, limit: int = 20) -> list[dict]:
        """获取最近活动（用于 Dashboard）"""
        logs = await self._storage.get_audit_logs(limit)
        return [
            {
                "timestamp": l.timestamp.isoformat() if isinstance(l.timestamp, str) else l.timestamp,
                "agent_id": l.agent_id,
                "action": l.action,
                "target": l.target,
                "result": l.result,
            }
            for l in logs
        ]

    # ------------------------------------------------------------------
    # 持久化与频率限制（核心逻辑）
    # ------------------------------------------------------------------

    async def _ensure_rate_db(self):
        """确保持久化表存在并加载历史数据"""
        if self._rate_db is not None:
            return
        db_path = self._storage.db_path
        self._rate_db = await aiosqlite.connect(str(db_path))
        await self._rate_db.execute(
            """CREATE TABLE IF NOT EXISTS rate_limits (
                agent_id TEXT,
                action TEXT,
                timestamp REAL
            )"""
        )
        await self._rate_db.commit()
        await self._load_counters()

    async def _load_counters(self):
        """从持久化表加载窗口内的频率数据到内存"""
        window_start = time.time() - self._rate_limit_window
        cursor = await self._rate_db.execute(
            "SELECT agent_id, action, timestamp FROM rate_limits WHERE timestamp > ?",
            (window_start,)
        )
        rows = await cursor.fetchall()
        for agent_id, action, ts in rows:
            self._rate_counters[agent_id][action].append(ts)
        await cursor.close()

    async def _add_rate_entry(self, agent_id: str, action: str):
        """将当前操作写入持久化表"""
        now = time.time()
        await self._rate_db.execute(
            "INSERT INTO rate_limits (agent_id, action, timestamp) VALUES (?, ?, ?)",
            (agent_id, action, now)
        )
        await self._rate_db.commit()

    async def _check_rate_limit(self, agent_id: str, action: str) -> bool:
        """检查操作频率限制

        Returns:
            True: 允许操作；False: 超过限制，应拒绝操作
        """
        if not agent_id:
            return True

        await self._ensure_rate_db()

        now = time.time()
        window_start = now - self._rate_limit_window
        timestamps = self._rate_counters[agent_id][action]

        # 清理内存中过期的记录
        timestamps[:] = [t for t in timestamps if t > window_start]

        # 将当前操作写入持久化表（先写，保证数据不丢失）
        await self._add_rate_entry(agent_id, action)

        # 将当前时间戳加入内存
        timestamps.append(now)

        count = len(timestamps)

        # 频率限制生效逻辑
        if count > self._rate_limit_max:
            log.warning(
                f"[审计频率限制] 智能体 {agent_id} 操作 {action} 次数 {count} "
                f"超过限制 {self._rate_limit_max} 次/{self._rate_limit_window}s，已拒绝"
            )
            return False

        # 超过告警阈值（仅告警，不阻断）
        if count > self._alert_threshold:
            log.warning(
                f"[审计告警] 智能体 {agent_id} 操作 {action} 频率异常: "
                f"{count} 次/{self._rate_limit_window}秒 (阈值: {self._alert_threshold})"
            )

        return True

    # ------------------------------------------------------------------
    # 统计接口（仅使用内存数据，不涉及 DB，保持与之前兼容）
    # ------------------------------------------------------------------

    def get_rate_stats(self, agent_id: str = None) -> dict:
        """获取操作频率统计"""
        now = time.time()
        window_start = now - self._rate_limit_window
        stats = {}
        agents = [agent_id] if agent_id else list(self._rate_counters.keys())
        for aid in agents:
            agent_stats = {}
            for action, timestamps in self._rate_counters.get(aid, {}).items():
                recent = [t for t in timestamps if t > window_start]
                agent_stats[action] = len(recent)
            if agent_stats:
                stats[aid] = agent_stats
        return stats
