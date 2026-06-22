#!/usr/bin/env python3
"""在远程生成token，输出为base64编码"""
import asyncio, base64, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import Auth
import yaml

async def main():
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    a = Auth(cfg["auth"]["secret_key"])
    token = a.create_token("xiaoqing", "agent")
    encoded = base64.b64encode(token.encode()).decode()
    print(encoded, end="")

if __name__ == "__main__":
    asyncio.run(main())
