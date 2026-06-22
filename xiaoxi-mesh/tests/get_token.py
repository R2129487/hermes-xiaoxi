#!/usr/bin/env python3
"""在阿里云上生成token，用于本地测试连接"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import Auth
import yaml

async def main():
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")) as f:
        cfg = yaml.safe_load(f)
    a = Auth(cfg["auth"]["secret_key"])
    token = a.create_token("xiaoqing", "agent")
    # 直接输出纯token
    print(token, end="")

if __name__ == "__main__":
    asyncio.run(main())
