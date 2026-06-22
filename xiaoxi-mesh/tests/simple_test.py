#!/usr/bin/env python3
"""最简单的外网WebSocket连接测试"""
import asyncio, json, websockets, base64, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from auth import Auth
import yaml

async def main():
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")) as f:
        cfg = yaml.safe_load(f)
    a = Auth(cfg["auth"]["secret_key"])
    token = a.create_token("xiaoqing", "agent")

    b64 = base64.b64encode(token.encode()).decode()
    print(f"Token base64: {b64[:40]}...")
    
    async with websockets.connect(f"ws://101.37.231.143:8765/ws/xiaoqing?token={token}") as ws:
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        d = json.loads(raw)
        print(f"✅ 连上了: type={d['type']}, data={d.get('data',{})}")

if __name__ == "__main__":
    asyncio.run(main())
