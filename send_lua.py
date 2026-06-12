#!/usr/bin/env python3
import json, urllib.request, sys

script_file = sys.argv[1] if len(sys.argv) > 1 else "/home/caowei/xiaoxi-project/send_oled.lua"

with open(script_file) as f:
    script = f.read()

token = "***= "Bearer " + token

data = json.dumps({"script": script}).encode()
req = urllib.request.Request(
    "http://192.168.1.12/api/lua/run",
    data=data,
    headers={"Content-Type": "application/json", "Authorization": auth},
    method="POST"
)
resp = urllib.request.urlopen(req, timeout=15)
print(resp.read().decode())
