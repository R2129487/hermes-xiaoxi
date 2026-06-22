#!/usr/bin/env python3
"""生成aliciyun token并输出base64编码"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import Auth
import yaml
import base64

async def main():
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")) as f:
        cfg = yaml.safe_load(f)
    a = Auth(cfg["auth"]["secret_key"])
    for name in ["xiaobai", "xiaoqing", "xiaolan"]:
        t = a.create_token(name, "agent" if name != "xiaolan" else "admin")
        b64 = base64.b64encode(t.encode()).decode()
        print(f"{name}:{b64}")

asyncio.run(main())
