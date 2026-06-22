#!/usr/bin/env python3
"""直接用urllib测试WebSocket HTTP Upgrade请求"""
import asyncio, json, sys, os, base64
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def main():
    # 生成token
    from auth import Auth
    import yaml
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")) as f:
        cfg = yaml.safe_load(f)
    a = Auth(cfg["auth"]["secret_key"])
    local_token = a.create_token("xiaoqing", "agent")

    # 用远程生成的那个
    remote_b64 = "ZXlKaGJHY2lPaUpJVXpJMU5pSXNJblI1Y0NJNklrcFhWQ0o5LmV5SmhaMlZ1ZEY5cFpDSTZJbmhwWVc5eGFXNW5JaXdpY205c1pTSTZJbUZuWlc1MElpd2laWGh3SWpveE56Z3lNemd3TVRVMUxqSXpNamN5TVN3aWFXRjBJam94TnpneU1USXdPVFUxTGpJek1qY3lObjAuU0w1eFZEbHFGR2ZiZmdEOFhoUGhud2FyRkltbGs5UEhiRUNlclpYS0hobw=="
    remote_token = base64.b64decode(remote_b64).decode()

    print("测试1: 本地token → 远程服务器验证")
    # 通过HTTP API让远程验证token
    import httpx
    async with httpx.AsyncClient() as cli:
        # 发一条消息用本地token作为from
        r = await cli.post("http://101.37.231.143:8765/api/messages/send", json={
            "from_id": "xiaoqing", "to_id": "xiaobai",
            "content": "本地token测试", "type": "text"
        })
        print(f"  HTTP消息发送: {r.status_code}")

        # 从远程SSH触发token验证
        import subprocess
        # 直接用ssh验证
        process = await asyncio.create_subprocess_exec(
            "ssh", "-p", "50198", "root@101.37.231.143",
            f"cd /opt/xiaoxi-mesh && python3 -c 'from auth import Auth; import yaml; a=Auth(yaml.safe_load(open(\"config.yaml\"))[\"auth\"][\"secret_key\"]); p=a.verify_token(\"{local_token}\"); print(\"LOCAL_TOKEN_VERIFIED:\" + str(p is not None))'",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        print(f"  远程验证本地token: {stdout.decode().strip()}")

        process2 = await asyncio.create_subprocess_exec(
            "ssh", "-p", "50198", "root@101.37.231.143",
            f"cd /opt/xiaoxi-mesh && python3 -c 'from auth import Auth; import yaml; a=Auth(yaml.safe_load(open(\"config.yaml\"))[\"auth\"][\"secret_key\"]); p=a.verify_token(\"{remote_token}\"); print(\"REMOTE_TOKEN_VERIFIED:\" + str(p is not None))'",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout2, stderr2 = await process2.communicate()
        print(f"  远程验证远程token: {stdout2.decode().strip()}")

if __name__ == "__main__":
    asyncio.run(main())
