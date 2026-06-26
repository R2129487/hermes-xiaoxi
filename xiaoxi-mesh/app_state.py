"""共享应用状态 - 配置 + 全局组件实例"""
from __future__ import annotations
import asyncio
import logging

import yaml
from fastapi import WebSocket

from auth import Auth
from storage import Storage
from permissions import PermissionManager
from audit import AuditLogger
from collaboration import AgentRegistry, TaskRouter, TaskDelegator, CapabilityDiscovery
from decision_engine import DecisionEngine
from agent_brain import AgentBrain

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("xiaoxi-mesh")

with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

srv_cfg = cfg["server"]
auth_cfg = cfg["auth"]
store_cfg = cfg["storage"]
limits = cfg["limits"]

auth = Auth(secret_key=auth_cfg["secret_key"],
            token_expire_hours=auth_cfg["token_expire_hours"])
store = Storage(db_path=store_cfg["db_path"])

perm_mgr = PermissionManager(cfg.get("permissions", {}).get("roles", {}))
audit_log = AuditLogger(store, rate_limit_window=60, rate_limit_max=100)
registry = AgentRegistry(store)
router = TaskRouter(registry)
delegator = TaskDelegator(store, router, audit_log)
discovery = CapabilityDiscovery(registry, store)

connections: dict[str, WebSocket] = {}
connection_lock = asyncio.Lock()

decision_engine = DecisionEngine(agent_id="server", capabilities=[])

# Agent Brain（智能管理员）
brain_cfg = cfg.get("agent_brain", {})
if brain_cfg.get("enabled", False):
    brain = AgentBrain(brain_cfg)
    log.info("[AppState] AgentBrain 已初始化")
else:
    brain = None
    log.info("[AppState] AgentBrain 未启用")
