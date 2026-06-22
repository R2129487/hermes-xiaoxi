#!/usr/bin/env python3
"""调试：测试本地生成的token能否连阿里云"""
import asyncio, json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import jwt
import websockets
from auth import Auth
import yaml

async def main():
    # 读取本地config
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")) as f:
        cfg = yaml.safe_load(f)

    a = Auth(cfg["auth"]["secret_key"])
    token = a.create_token("xiaoqing", "agent")

    # 验证JWT结构
    payload = jwt.decode(token, cfg["auth"]["secret_key"], algorithms=["HS256"], options={"verify_exp": False})
    print(f"JWT payload: {payload}")

    # 尝试连接
    print(f"\n连接 ws://101.37.231.143:8765/ws/xiaoqing?token={token[:20]}...")
    try:
        async with websockets.connect(f"ws://101.37.231.143:8765/ws/xiaoqing?token={token}") as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(raw)
            print(f"✅ 连接成功: type={d['type']}")
    except websockets.exceptions.InvalidStatus as e:
        print(f"❌ 连接失败: HTTP {e.response.status_code}")
        body = await e.response.text() if hasattr(e.response, 'text') else "N/A"
        print(f"   响应体: {body[:200]}")
    except Exception as e:
        print(f"❌ 异常: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
