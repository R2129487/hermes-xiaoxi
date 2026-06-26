#!/usr/bin/env python3
"""
AP 模拟器 — 模拟手机端 App 与 MESH 服务端通讯
用法:
  ./ap_simulator.py                        # 交互模式，连上后监听消息
  ./ap_simulator.py --test                 # 自动测试，发消息后等回复
  ./ap_simulator.py --send "你好"          # 发一条消息后退出

模拟 Flutter App (小青) 的全部行为:
  1. HTTP 登录获取 Token
  2. WebSocket 连接 (URL 带 token)
  3. 注册 agent (role=user)
  4. 发送/接收消息
  5. 心跳 (ping/pong)
"""
import asyncio
import json
import sys
import time
import urllib.request
import websockets

MESH_HOST = '101.37.231.143'
MESH_PORT = 8765

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def login():
    """HTTP 登录获取 Token"""
    req = urllib.request.Request(
        f'http://{MESH_HOST}:{MESH_PORT}/api/auth/login',
        data=json.dumps({'username': 'admin', 'password': '840601'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    token = resp['data']['token']
    log(f"✅ 登录成功，token前20位: {token[:20]}...")
    return token

async def listen(ws, timeout_sec=10):
    """监听消息，最多等 timeout_sec 秒"""
    messages = []
    try:
        async with asyncio.timeout(timeout_sec):
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get('type') == 'pong':
                    continue
                messages.append(msg)
    except TimeoutError:
        pass
    return messages

async def ap_session(token, mode='interactive', send_text=None):
    """AP 会话"""
    uri = f'ws://{MESH_HOST}:{MESH_PORT}/ws/admin?token={token}'
    log(f"🔗 连接 MESH {MESH_HOST}:{MESH_PORT}")
    
    async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
        log("✅ WebSocket 已连接")

        # 注册 agent
        await ws.send(json.dumps({
            'type': 'agent_register',
            'data': {
                'agent_id': 'admin',
                'name': '手机端管理员',
                'role': 'user',
                'description': 'AP模拟器',
            }
        }))
        log("📝 已注册 agent (role=user)")

        # 获取在线列表
        await ws.send(json.dumps({'type': 'get_agents'}))
        
        if mode == 'send_once':
            await asyncio.sleep(0.5)
            await ws.send(json.dumps({
                'type': 'message',
                'to': 'xiaoqing',
                'content': send_text or '你好，我是手机端App'
            }, ensure_ascii=False))
            log(f"📤 已发送: {send_text or '你好，我是手机端App'}")
            log("⏳ 等待回复...")
            msgs = await listen(ws, timeout_sec=10)
            for m in msgs:
                log(f"📩 {m.get('type')}: {json.dumps(m, ensure_ascii=False)[:300]}")
                if m.get('type') == 'message':
                    log(f"💬 回复: {m.get('data', {}).get('content','')}")
            return msgs

        elif mode == 'test':
            await asyncio.sleep(0.5)
            
            tests = [
                ('[测试1] 普通消息', {'type': 'message', 'to': 'xiaoqing', 'content': '你好小青，AP模拟器测试'}),
                ('[测试2] 指令消息', {'type': 'message', 'to': 'xiaoqing', 'content': '现在几点了'}),
                ('[测试3] 获取智能体', {'type': 'get_agents'}),
            ]
            
            for name, payload in tests:
                await ws.send(json.dumps(payload, ensure_ascii=False))
                log(f"📤 {name}")
                await asyncio.sleep(1)
            
            log("⏳ 等待回复（15秒）...")
            msgs = await listen(ws, timeout_sec=15)
            log(f"📊 共收到 {len(msgs)} 条非心跳消息:")
            for m in msgs:
                log(f"  type={m.get('type')}: {json.dumps(m, ensure_ascii=False)[:200]}")
            return msgs

        else:  # interactive
            log("📡 交互模式启动，等待服务端消息...")
            log("💡 在微信上给小青发消息，看能不能同步过来")
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    t = msg.get('type', '')
                    if t == 'pong':
                        continue
                    log(f"📩 type={t}: {json.dumps(msg, ensure_ascii=False)[:400]}")
                    if t == 'message':
                        d = msg.get('data', {})
                        log(f"💬 来自 {d.get('from_id','?')}: {d.get('content','')}")
                    elif t == 'agents_update':
                        agents = msg.get('data', {}).get('agents', [])
                        online = [f"{a.get('name','?')}({a.get('agent_id','?')})" for a in agents if a.get('online')]
                        log(f"👥 在线: {', '.join(online) if online else '无'}")
                    elif t == 'error':
                        log(f"❌ 错误: {msg.get('data', {})}")
            except websockets.ConnectionClosed:
                log("⚠️ 连接断开")

async def main():
    import argparse
    parser = argparse.ArgumentParser(description='AP 模拟器')
    parser.add_argument('--test', action='store_true', help='自动测试模式')
    parser.add_argument('--send', type=str, help='发一条消息后退出')
    args = parser.parse_args()

    if args.test:
        mode = 'test'
    elif args.send:
        mode = 'send_once'
    else:
        mode = 'interactive'

    try:
        token = login()
        await ap_session(token, mode=mode, send_text=args.send)
    except (ConnectionRefusedError, OSError) as e:
        log(f"❌ 连接失败: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"❌ 异常: {e}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("\n👋 已退出")
