#!/usr/bin/env python3
"""检查token中有无URL特殊字符"""
import sys, os, base64, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from auth import Auth
import yaml

with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")) as f:
    cfg = yaml.safe_load(f)
a = Auth(cfg["auth"]["secret_key"])
token = a.create_token("xiaoqing", "agent")

print(f"Token: {token}")
print(f"长度: {len(token)}")
print(f"第一部分: {token.split('.')[0]}")
print(f"第二部分: {token.split('.')[1]}")

# Check for URL-unsafe chars
unsafe = re.findall(r'[^a-zA-Z0-9\-._~]', token)
print(f"URL不安全字符: {unsafe if unsafe else '无'}")

# The issue might be the dot - let me check
print(f"包含.号: {'.' in token}")
print(f"包含=号: {'=' in token}")

# Compare with what curl would send
import urllib.parse
encoded = urllib.parse.quote(token, safe='')
print(f"URL编码后长度: {len(encoded)}")
print(f"URL编码: {encoded[:40]}...")

# Let me also try connecting using urllib to see the response
import urllib.request
try:
    req = urllib.request.Request(f"http://101.37.231.143:8765/api/agents/xiaoqing")
    resp = urllib.request.urlopen(req, timeout=5)
    print(f"\nHTTP API响应: {resp.status}")
except Exception as e:
    print(f"HTTP API错误: {e}")
