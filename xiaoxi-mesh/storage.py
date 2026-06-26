"""小希-Mesh v2 数据存储层 (SQLite)

支持智能体、消息、任务、审计日志、Token 等数据的持久化存储。
"""
from __future__ import annotations
import asyncio
import json
import sqlite3
from datetime import datetime, timezone
import aiosqlite
from pathlib import Path
from typing import Optional
from models import Agent, Message, Task, AuditLog


class Storage:
    def __init__(self, db_path: str = "data/messenger.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self):
        """初始化数据库表并创建持久连接"""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = sqlite3.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'agent',
                token_hash TEXT NOT NULL DEFAULT '',
                public_key TEXT,
                online INTEGER NOT NULL DEFAULT 0,
                last_seen TEXT,
                registered_at TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                capabilities TEXT NOT NULL DEFAULT '[]',
                specialties TEXT NOT NULL DEFAULT '[]',
                platform TEXT NOT NULL DEFAULT '{}',
                description TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'text',
                content TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'normal',
                reply_to TEXT,
                created_at TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_messages_to
                ON messages(to_id, delivered, created_at);
            CREATE INDEX IF NOT EXISTS idx_messages_from
                ON messages(from_id, created_at);
            CREATE TABLE IF NOT EXISTS tokens (
                token_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                revoked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                assigned_to TEXT,
                assigned_by TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                required_capabilities TEXT NOT NULL DEFAULT '[]',
                result TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_assigned
                ON tasks(assigned_to);
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                agent_id TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT '',
                result TEXT NOT NULL DEFAULT 'success',
                details TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_logs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_audit_agent
                ON audit_logs(agent_id);
            CREATE INDEX IF NOT EXISTS idx_audit_action
                ON audit_logs(action);
            CREATE TABLE IF NOT EXISTS capability_cache (
                capability TEXT PRIMARY KEY,
                agent_ids TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL
            );
        """)
        await self._db.commit()

    async def close(self):
        """关闭持久连接"""
        if self._db:
            await self._db.close()
            self._db = None

    # ── 智能体操作 ──

    async def register_agent(self, agent: Agent) -> bool:
        """注册新智能体，返回是否成功"""
        async with self._lock:
            exists = await self._db.execute_fetchall(
                "SELECT 1 FROM agents WHERE agent_id = ?", (agent.agent_id,)
            )
            if exists:
                return False
            await self._db.execute(
                """INSERT INTO agents (agent_id, name, role, token_hash,
                   public_key, registered_at, metadata, capabilities,
                   specialties, platform, description)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (agent.agent_id, agent.name, agent.role, agent.token_hash,
                 agent.public_key, agent.registered_at.isoformat(),
                 json.dumps(agent.metadata), json.dumps(agent.capabilities),
                 json.dumps(agent.specialties), json.dumps(agent.platform),
                 agent.description)
            )
            await self._db.commit()
            return True

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取单个智能体"""
        async with self._lock:
            cur = await self._db.execute(
                "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
            )
            row = await cur.fetchone()
            if not row:
                return None
            return self._row_to_agent(row)

    async def list_agents(self) -> list[Agent]:
        """列出所有智能体"""
        async with self._lock:
            cur = await self._db.execute("SELECT * FROM agents ORDER BY name")
            rows = await cur.fetchall()
            return [self._row_to_agent(r) for r in rows]

    async def update_agent(self, agent_id: str, **kwargs) -> bool:
        """更新智能体字段"""
        allowed = {"name", "role", "public_key", "metadata", "capabilities",
                    "specialties", "platform", "description"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        # 处理列表/字典类型的 JSON 序列化
        for k in ("capabilities", "specialties", "platform", "metadata"):
            if k in updates and not isinstance(updates[k], str):
                updates[k] = json.dumps(updates[k])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [agent_id]
        async with self._lock:
            await self._db.execute(
                f"UPDATE agents SET {set_clause} WHERE agent_id = ?", values
            )
            await self._db.commit()
        return True

    async def delete_agent(self, agent_id: str) -> bool:
        """删除智能体"""
        async with self._lock:
            cur = await self._db.execute(
                "DELETE FROM agents WHERE agent_id = ?", (agent_id,)
            )
            await self._db.commit()
            return cur.rowcount > 0

    async def set_online(self, agent_id: str, online: bool):
        """设置智能体在线状态"""
        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                "UPDATE agents SET online = ?, last_seen = ? WHERE agent_id = ?",
                (1 if online else 0, now, agent_id)
            )
            await self._db.commit()

    async def set_token_hash(self, agent_id: str, token_hash: str):
        """设置智能体 token 哈希"""
        async with self._lock:
            await self._db.execute(
                "UPDATE agents SET token_hash = ? WHERE agent_id = ?",
                (token_hash, agent_id)
            )
            await self._db.commit()

    # ── 消息操作 ──

    async def save_message(self, msg: Message):
        """保存消息"""
        async with self._lock:
            await self._db.execute(
                """INSERT INTO messages (id, from_id, to_id, type, content,
                   priority, reply_to, created_at, delivered)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (msg.id, msg.from_id, msg.to_id, msg.type, msg.content,
                 msg.priority, msg.reply_to, msg.created_at.isoformat(),
                 1 if msg.delivered else 0)
            )
            await self._db.commit()

    async def get_undelivered(self, agent_id: str, limit: int = 100, offset: int = 0) -> list[Message]:
        """获取未投递消息（分页）"""
        async with self._lock:
            cur = await self._db.execute(
                """SELECT * FROM messages
                   WHERE (to_id = ? OR to_id = 'broadcast')
                     AND delivered = 0
                   ORDER BY created_at ASC
                   LIMIT ? OFFSET ?""",
                (agent_id, limit, offset)
            )
            rows = await cur.fetchall()
            msgs = []
            for r in rows:
                msgs.append(Message(
                    id=r["id"], from_id=r["from_id"], to_id=r["to_id"],
                    type=r["type"], content=r["content"],
                    priority=r["priority"], reply_to=r["reply_to"],
                    created_at=r["created_at"], delivered=bool(r["delivered"]),
                ))
            return msgs

    async def mark_delivered(self, msg_id: str):
        """标记消息已投递"""
        async with self._lock:
            await self._db.execute(
                "UPDATE messages SET delivered = 1 WHERE id = ?", (msg_id,)
            )
            await self._db.commit()

    async def mark_all_delivered(self, agent_id: str):
        """标记所有发给该智能体的消息（含广播）为已读"""
        async with self._lock:
            await self._db.execute(
                "UPDATE messages SET delivered = 1 WHERE (to_id = ? OR to_id = 'broadcast') AND delivered = 0",
                (agent_id,)
            )
            await self._db.commit()

    async def get_recent_messages(self, limit: int = 50) -> list[Message]:
        """获取最近消息"""
        async with self._lock:
            cur = await self._db.execute(
                "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = await cur.fetchall()
            return [Message(
                id=r["id"], from_id=r["from_id"], to_id=r["to_id"],
                type=r["type"], content=r["content"],
                priority=r["priority"], reply_to=r["reply_to"],
                created_at=r["created_at"], delivered=bool(r["delivered"]),
            ) for r in rows]

    # ── Token 管理 ──

    async def save_token(self, token_id: str, agent_id: str, role: str,
                         expires_at: Optional[str] = None):
        """保存 token"""
        async with self._lock:
            await self._db.execute(
                """INSERT INTO tokens (token_id, agent_id, role, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (token_id, agent_id, role,
                 datetime.now(timezone.utc).isoformat(), expires_at)
            )
            await self._db.commit()

    async def revoke_token(self, token_id: str):
        """撤销 token"""
        async with self._lock:
            await self._db.execute(
                "UPDATE tokens SET revoked = 1 WHERE token_id = ?",
                (token_id,)
            )
            await self._db.commit()

    async def list_tokens(self, agent_id: Optional[str] = None) -> list[dict]:
        """列出 token"""
        async with self._lock:
            if agent_id:
                cur = await self._db.execute(
                    "SELECT * FROM tokens WHERE agent_id = ?", (agent_id,)
                )
            else:
                cur = await self._db.execute("SELECT * FROM tokens")
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # ── 任务操作 (v2) ──

    async def create_task(self, task: Task) -> bool:
        """创建任务"""
        async with self._lock:
            await self._db.execute(
                """INSERT INTO tasks (task_id, description, assigned_to,
                   assigned_by, status, required_capabilities, result,
                   created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (task.task_id, task.description, task.assigned_to,
                 task.assigned_by, task.status,
                 json.dumps(task.required_capabilities), task.result,
                 task.created_at.isoformat(), task.updated_at.isoformat())
            )
            await self._db.commit()
            return True

    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取单个任务"""
        async with self._lock:
            cur = await self._db.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            )
            row = await cur.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    async def update_task(self, task_id: str, **kwargs) -> bool:
        """更新任务"""
        allowed = {"status", "result", "assigned_to", "description"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return False
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "required_capabilities" in updates and not isinstance(updates["required_capabilities"], str):
            updates["required_capabilities"] = json.dumps(updates["required_capabilities"])
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]
        async with self._lock:
            await self._db.execute(
                f"UPDATE tasks SET {set_clause} WHERE task_id = ?", values
            )
            await self._db.commit()
        return True

    async def list_tasks(self, status: Optional[str] = None,
                         agent_id: Optional[str] = None) -> list[Task]:
        """列出任务"""
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if agent_id:
            conditions.append("assigned_to = ?")
            params.append(agent_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        async with self._lock:
            cur = await self._db.execute(
                f"SELECT * FROM tasks {where} ORDER BY created_at DESC",
                params
            )
            rows = await cur.fetchall()
            return [self._row_to_task(r) for r in rows]

    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        async with self._lock:
            cur = await self._db.execute(
                "DELETE FROM tasks WHERE task_id = ?", (task_id,)
            )
            await self._db.commit()
            return cur.rowcount > 0

    # ── 审计日志 (v2) ──

    async def save_audit_log(self, log: AuditLog):
        """保存审计日志"""
        async with self._lock:
            await self._db.execute(
                """INSERT INTO audit_logs (timestamp, agent_id, action,
                   target, result, details)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (log.timestamp.isoformat(), log.agent_id, log.action,
                 log.target, log.result, log.details)
            )
            await self._db.commit()

    async def get_audit_logs(self, limit: int = 100, agent_id: Optional[str] = None,
                             action: Optional[str] = None) -> list[AuditLog]:
        """获取审计日志"""
        conditions = []
        params = []
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if action:
            conditions.append("action = ?")
            params.append(action)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        async with self._lock:
            cur = await self._db.execute(
                f"SELECT * FROM audit_logs {where} ORDER BY timestamp DESC LIMIT ?",
                params + [limit]
            )
            rows = await cur.fetchall()
            return [AuditLog(
                id=r["id"],
                timestamp=r["timestamp"],
                agent_id=r["agent_id"],
                action=r["action"],
                target=r["target"],
                result=r["result"],
                details=r["details"],
            ) for r in rows]

    # ── 能力缓存 (v2) ──

    async def update_capability_cache(self, capability: str, agent_ids: list[str]):
        """更新能力缓存"""
        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            await self._db.execute(
                """INSERT OR REPLACE INTO capability_cache
                   (capability, agent_ids, updated_at)
                   VALUES (?, ?, ?)""",
                (capability, json.dumps(agent_ids), now)
            )
            await self._db.commit()

    async def get_capability_agents(self, capability: str) -> list[str]:
        """获取具备某能力的智能体列表"""
        async with self._lock:
            cur = await self._db.execute(
                "SELECT agent_ids FROM capability_cache WHERE capability = ?",
                (capability,)
            )
            row = await cur.fetchone()
            if not row:
                return []
            return json.loads(row["agent_ids"])

    async def refresh_capability_cache(self):
        """从 agents 表重建能力缓存（单次事务）"""
        async with self._lock:
            # 直接查询所有 agents
            cur = await self._db.execute("SELECT agent_id, capabilities FROM agents")
            rows = await cur.fetchall()
            cap_map: dict[str, list[str]] = {}
            for row in rows:
                agent_id = row["agent_id"]
                caps = json.loads(row["capabilities"]) if row["capabilities"] else []
                for cap in caps:
                    cap_map.setdefault(cap, []).append(agent_id)
            await self._db.execute("DELETE FROM capability_cache")
            now = datetime.now(timezone.utc).isoformat()
            for cap, agent_ids in cap_map.items():
                await self._db.execute(
                    "INSERT INTO capability_cache (capability, agent_ids, updated_at) VALUES (?, ?, ?)",
                    (cap, json.dumps(agent_ids), now)
                )
            await self._db.commit()

    # ── 统计 ──

    async def get_stats(self) -> dict:
        """获取系统统计信息"""
        async with self._lock:
            agent_count_row = await (await self._db.execute("SELECT COUNT(*) as c FROM agents")).fetchone()
            agent_count = agent_count_row["c"]
            online_count_row = await (await self._db.execute("SELECT COUNT(*) as c FROM agents WHERE online=1")).fetchone()
            online_count = online_count_row["c"]
            msg_count_row = await (await self._db.execute("SELECT COUNT(*) as c FROM messages")).fetchone()
            msg_count = msg_count_row["c"]
            task_count_row = await (await self._db.execute("SELECT COUNT(*) as c FROM tasks")).fetchone()
            task_count = task_count_row["c"]
            pending_tasks_row = await (await self._db.execute("SELECT COUNT(*) as c FROM tasks WHERE status='pending'")).fetchone()
            pending_tasks = pending_tasks_row["c"]
            return {
                "agent_count": agent_count,
                "online_count": online_count,
                "message_count": msg_count,
                "task_count": task_count,
                "pending_tasks": pending_tasks,
            }

    # ── 内部辅助 ──

    def _row_to_agent(self, row) -> Agent:
        """将数据库行转换为 Agent 对象"""
        last_seen = row["last_seen"]
        if last_seen and isinstance(last_seen, str):
            try:
                last_seen = datetime.fromisoformat(last_seen)
            except ValueError:
                last_seen = None
        reg_at = row["registered_at"]
        if reg_at and isinstance(reg_at, str):
            try:
                reg_at = datetime.fromisoformat(reg_at)
            except ValueError:
                reg_at = datetime.now(timezone.utc)
        return Agent(
            agent_id=row["agent_id"],
            name=row["name"],
            role=row["role"],
            token_hash=row["token_hash"],
            public_key=row["public_key"],
            online=bool(row["online"]),
            last_seen=last_seen,
            registered_at=reg_at,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            capabilities=json.loads(row["capabilities"]) if row["capabilities"] else [],
            specialties=json.loads(row["specialties"]) if row["specialties"] else [],
            platform=json.loads(row["platform"]) if row["platform"] else {},
            description=row["description"] or "",
        )

    def _row_to_task(self, row) -> Task:
        """将数据库行转换为 Task 对象"""
        created = row["created_at"]
        updated = row["updated_at"]
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                created = datetime.now(timezone.utc)
        if isinstance(updated, str):
            try:
                updated = datetime.fromisoformat(updated)
            except ValueError:
                updated = datetime.now(timezone.utc)
        return Task(
            task_id=row["task_id"],
            description=row["description"],
            assigned_to=row["assigned_to"],
            assigned_by=row["assigned_by"],
            status=row["status"],
            required_capabilities=json.loads(row["required_capabilities"]) if row["required_capabilities"] else [],
            result=row["result"],
            created_at=created,
            updated_at=updated,
        )
