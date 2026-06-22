#!/usr/bin/env python3
"""在阿里云上测试 token 生成和 WebSocket 连接"""
import asyncio, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import websockets
from auth import Auth
import yaml

async def main():
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")) as f:
        cfg = yaml.safe_load(f)

    a = Auth(cfg["auth"]["secret_key"])
    token = a.create_token("xiaoqing", "agent")

    # 1. 验证token
    payload = a.verify_token(token)
    assert payload, "Token验证失败"
    print(f"[1] Token验证通过: agent_id={payload.agent_id}")

    # 2. HTTP 查询智能体
    import httpx
    async with httpx.AsyncClient() as cli:
        r = await cli.get("http://localhost:8765/api/agents/xiaoqing")
        assert r.status_code == 200, f"HTTP {r.status_code}"
        print(f"[2] 智能体存在: {r.json()['data']['name']}")

    # 3. WebSocket连接
    async with websockets.connect(f"ws://localhost:8765/ws/xiaoqing?token={token}") as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        d = json.loads(raw)
        print(f"[3] WS连接成功: type={d['type']}")

        # 4. 发送消息
        await ws.send(json.dumps({"type": "send", "to": "broadcast", "content": "在阿里云本地测试消息"}))
        conf = await asyncio.wait_for(ws.recv(), timeout=5)
        c = json.loads(conf)
        print(f"[4] 消息发送成功: type={c['type']}")

        # 5. Ping
        await ws.send(json.dumps({"type": "ping"}))
        pong = await asyncio.wait_for(ws.recv(), timeout=5)
        print(f"[5] Pong: {json.loads(pong)['type']}")

    print("\n✅ 本地测试全部通过")
    print(f"Token (前20字符): {token[:20]}")

if __name__ == "__main__":
    asyncio.run(main())
