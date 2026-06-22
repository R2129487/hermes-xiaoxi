#!/usr/bin/env python3
"""在远程服务器上验证给定的token"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from auth import Auth
import yaml
import jwt

with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")) as f:
    cfg = yaml.safe_load(f)
secret = cfg["auth"]["secret_key"]
a = Auth(secret)

# 读取token（从文件传入）
with open("/tmp/token_to_verify.txt") as f:
    token = f.read().strip()

p = a.verify_token(token)
print(f"Auth.verify_token: {'✅' if p else '❌'}", end="")
if p:
    print(f" agent_id={p.agent_id}", end="")
print()

try:
    d = jwt.decode(token, secret, algorithms=["HS256"])
    print(f"jwt.decode: ✅ payload={d}")
except Exception as e:
    print(f"jwt.decode: ❌ {e}")
