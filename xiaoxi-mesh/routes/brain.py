"""智能管理员配置 API 路由"""
from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException

import app_state
from agent_brain import AgentBrain

router = APIRouter()


@router.get("/api/brain/config")
async def get_brain_config():
    """返回当前 brain 配置（API key 遮罩显示）"""
    brain_cfg = app_state.cfg.get("agent_brain", {})
    api_key_file = brain_cfg.get("api_key_file", "")
    api_key_masked = ""
    if api_key_file:
        try:
            with open(api_key_file, encoding="utf-8") as f:
                key = f.read().strip()
            if key:
                api_key_masked = key[:10] + "••••" if len(key) > 10 else key
        except Exception:
            pass
    return {
        "enabled": brain_cfg.get("enabled", False),
        "provider": brain_cfg.get("provider", ""),
        "model": brain_cfg.get("model", ""),
        "api_key_masked": api_key_masked,
        "api_key_file": api_key_file,
        "system_prompt": brain_cfg.get("system_prompt", ""),
    }


@router.post("/api/brain/config")
async def update_brain_config(data: dict):
    """更新 brain 配置并热重载"""
    # 1. 读取当前 config.yaml
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 2. 更新 agent_brain 段
    if "agent_brain" not in config:
        config["agent_brain"] = {}

    brain_cfg = config["agent_brain"]
    if "enabled" in data:
        brain_cfg["enabled"] = bool(data["enabled"])
    if "provider" in data:
        brain_cfg["provider"] = str(data["provider"])
    if "model" in data:
        brain_cfg["model"] = str(data["model"])
    if "api_key_file" in data:
        brain_cfg["api_key_file"] = str(data["api_key_file"])
    if "api_key" in data and data["api_key"] and "••••" not in data["api_key"]:
        # 写入 API key 到文件
        key_file = brain_cfg.get("api_key_file", "")
        if key_file:
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(data["api_key"])
    if "system_prompt" in data:
        brain_cfg["system_prompt"] = str(data["system_prompt"])

    # 3. 写回 config.yaml
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    # 4. 重新初始化 brain 实例
    new_brain = AgentBrain(brain_cfg)
    app_state.brain = new_brain
    app_state.cfg = config

    return {"success": True}


@router.post("/api/brain/test")
async def test_brain(data: dict):
    """测试 brain 连接：发送一条消息让 brain.think() 处理"""
    message = data.get("message", "你好")
    brain = app_state.brain
    if not brain or not brain.enabled:
        raise HTTPException(status_code=400, detail="智能管理员未启用或配置不完整")
    result = await brain.think(message, "admin", [])
    return {"success": True, "result": result}
