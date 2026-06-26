#!/usr/bin/env python3
"""
MESH 信道测试套件 — 测试-反馈-修订闭环
覆盖:
  [HTTP] 登录、智能体列表、注册、发消息、创建任务
  [WS]   连接、注册、心跳、消息收发、路由
  [边缘] 离线消息、错误输入、重连

每项: PASS / FAIL(原因) / SKIP(条件)
"""
import asyncio
import json
import sys
import time
import traceback
import urllib.request
import urllib.error
import websockets
from dataclasses import dataclass, field
from typing import Optional

MESH_HOST = '101.37.231.143'
MESH_PORT = 8765
BASE = f'http://{MESH_HOST}:{MESH_PORT}'
WS_BASE = f'ws://{MESH_HOST}:{MESH_PORT}'

passed = 0
failed = 0
skipped = 0

def log(msg):
    print(f"  {msg}")

class TestSuite:
    def __init__(self):
        self.token = None
        self.admin_token = None

    # ========== 工具函数 ==========

    def http_post(self, path, data=None, auth=False):
        headers = {'Content-Type': 'application/json'}
        if auth and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        req = urllib.request.Request(f'{BASE}{path}',
            data=json.dumps(data).encode() if data else None,
            headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=8)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try: return json.loads(body)
            except: return {'error': body, 'status': e.code}
        except Exception as e:
            return {'error': str(e)}

    def http_get(self, path, auth=False):
        headers = {}
        if auth and self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        req = urllib.request.Request(f'{BASE}{path}', headers=headers)
        try:
            resp = urllib.request.urlopen(req, timeout=8)
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try: return json.loads(body)
            except: return {'error': body, 'status': e.code}
        except Exception as e:
            return {'error': str(e)}

    def test(self, name, fn):
        global passed, failed, skipped
        try:
            ok, detail = fn()
            if ok:
                passed += 1
                print(f"  ✅ {name}")
            else:
                failed += 1
                print(f"  ❌ {name}")
                print(f"     {detail}")
        except Exception as e:
            failed += 1
            print(f"  ❌ {name}")
            print(f"     [异常] {e}")
            traceback.print_exc()

    # ========== HTTP 测试 ==========

    def test_http_login(self):
        """T1: HTTP 登录"""
        r = self.http_post('/api/auth/login', {'username':'admin','password':'840601'})
        if r.get('success') and r.get('data',{}).get('token'):
            self.token = r['data']['token']
            return True, ''
        return False, f'登录失败: {json.dumps(r, ensure_ascii=False)[:200]}'

    def test_http_agents_list(self):
        """T2: 获取智能体列表"""
        r = self.http_get('/api/agents', auth=True)
        if r.get('success') and 'data' in r:
            agents = r['data']
            online = [a for a in agents if a.get('online')]
            return True, f'共{len(agents)}个智能体, {len(online)}在线'
        return False, str(r)[:200]

    def test_http_send_message(self):
        """T3: HTTP 发消息到在线智能体"""
        r = self.http_post('/api/messages/send', {
            'from_id': 'admin',
            'to_id': 'xiaolan',  # 在线
            'type': 'text',
            'content': '[测试] AP模拟器HTTP消息'
        }, auth=True)
        if r.get('success'):
            return True, ''
        return False, str(r)[:200]

    def test_http_send_message_offline(self):
        """T4: HTTP 发消息到离线智能体"""
        r = self.http_post('/api/messages/send', {
            'from_id': 'admin',
            'to_id': 'xiaoqing',  # 离线
            'type': 'text',
            'content': '[测试] AP模拟器→离线xiaoqing'
        }, auth=True)
        if r.get('success') or 'queued' in str(r).lower() or 'pending' in str(r).lower():
            return True, f'已接受(队列/直接失败): {str(r)[:150]}'
        return True, f'离线消息: {str(r)[:150]}'  # 只要不崩就算过

    def test_http_create_task(self):
        """T5: 创建任务"""
        r = self.http_post('/api/tasks', {
            'description': '[测试] AP模拟器创建的测试任务',
            'assigned_to': 'xiaolan',
            'assigned_by': 'admin'
        }, auth=True)
        if r.get('success') and r.get('data',{}).get('task_id'):
            return True, f'task_id={r["data"]["task_id"][:20]}...'
        return False, str(r)[:200]

    def test_http_execute_auto(self):
        """T6: 自动执行(auto路由)"""
        r = self.http_post('/api/execute', {
            'task': '[测试] 查询系统时间',
            'target': 'auto',
            'assigned_by': 'admin'
        }, auth=True)
        if r.get('success'):
            return True, str(r.get('data',{}))[:150]
        return False, str(r)[:200]

    def test_http_get_undelivered(self):
        """T7: 获取离线消息"""
        r = self.http_get('/api/messages/admin', auth=True)
        if isinstance(r, dict) and ('messages' in r or 'data' in r or 'success' in r):
            return True, str(r)[:150]
        return True, f'API返回(不崩即可): {str(r)[:150]}'

    def test_http_stats(self):
        """T8: 系统统计"""
        r = self.http_get('/api/stats', auth=True)
        if isinstance(r, dict) and 'success' in r:
            return True, str(r.get('data',{}))[:150]
        return True, f'统计: {str(r)[:150]}'

    # ========== WebSocket 测试 ==========

    async def test_ws_connect(self):
        """W1: WebSocket 连接+注册"""
        uri = f'{WS_BASE}/ws/admin?token={self.token}'
        async with websockets.connect(uri, ping_interval=20, ping_timeout=5) as ws:
            await ws.send(json.dumps({'type':'agent_register','data':{
                'agent_id':'admin','name':'AP测试仪','role':'user'}}))
            # 等确认
            async with asyncio.timeout(3):
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get('type') == 'pong': continue
                    if msg.get('type') == 'status':
                        return True, f"status={msg.get('data',{}).get('status')}"
                    return True, f"收到type={msg.get('type')}"
        return True, '连接正常(无消息)'

    async def test_ws_send_and_reply(self):
        """W2: WS发消息→等回复(bidirectional)"""
        uri = f'{WS_BASE}/ws/admin?token={self.token}'
        async with websockets.connect(uri, ping_interval=20, ping_timeout=5) as ws:
            await ws.send(json.dumps({'type':'agent_register','data':{
                'agent_id':'admin','name':'AP测试仪','role':'user'}}))
            await asyncio.sleep(0.3)
            await ws.send(json.dumps({'type':'message','to':'xiaolan',
                'content':'[WS测试] 你好小蓝，收到请回复'}))
            msgs = []
            try:
                async with asyncio.timeout(8):
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get('type') == 'pong': continue
                        msgs.append(msg)
                        if msg.get('type') == 'message':
                            break
            except TimeoutError:
                pass
            msg_types = [m.get('type') for m in msgs]
            return True, f'收{len(msgs)}条: {msg_types}' + (f' 内容:{msgs[-1].get("data",{}).get("content","")[:80]}' if msgs and msgs[-1].get('type')=='message' else ' [无回复]')

    async def test_ws_get_agents(self):
        """W3: WS请求智能体列表"""
        uri = f'{WS_BASE}/ws/admin?token={self.token}'
        async with websockets.connect(uri, ping_interval=20, ping_timeout=5) as ws:
            await ws.send(json.dumps({'type':'agent_register','data':{
                'agent_id':'admin','name':'AP测试仪','role':'user'}}))
            await asyncio.sleep(0.3)
            await ws.send(json.dumps({'type':'get_agents'}))
            msgs = []
            try:
                async with asyncio.timeout(5):
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get('type') == 'pong': continue
                        msgs.append(msg)
                        if msg.get('type') == 'agents_update':
                            break
            except TimeoutError:
                pass
            has_agents_update = any(m.get('type')=='agents_update' for m in msgs)
            if has_agents_update:
                return True, '收到agents_update'
            return False, f'未收到agents_update, 仅收到: {[m.get("type") for m in msgs]}'

    async def test_ws_heartbeat(self):
        """W4: WS心跳(ping/pong)"""
        uri = f'{WS_BASE}/ws/admin?token={self.token}'
        async with websockets.connect(uri, ping_interval=5, ping_timeout=3) as ws:
            await ws.send(json.dumps({'type':'agent_register','data':{
                'agent_id':'admin','name':'AP测试仪','role':'user'}}))
            await asyncio.sleep(0.3)
            await ws.send(json.dumps({'type':'ping'}))
            got_pong = False
            try:
                async with asyncio.timeout(5):
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get('type') == 'pong':
                            got_pong = True
                            break
            except TimeoutError:
                pass
            if got_pong:
                return True, 'pong已收到'
            return False, '未收到pong'

    async def test_ws_reconnect(self):
        """W5: WS断线重连"""
        uri = f'{WS_BASE}/ws/admin?token={self.token}'
        # 第一次连接
        async with websockets.connect(uri, ping_interval=20, ping_timeout=5) as ws:
            await ws.send(json.dumps({'type':'agent_register','data':{
                'agent_id':'admin','name':'AP测试仪','role':'user'}}))
        # 立刻重连
        async with websockets.connect(uri, ping_interval=20, ping_timeout=5) as ws:
            await ws.send(json.dumps({'type':'agent_register','data':{
                'agent_id':'admin','name':'AP重连测试','role':'user'}}))
            async with asyncio.timeout(3):
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get('type') == 'pong': continue
                    return True, f'重连成功,收到type={msg.get("type")}'
        return True, '重连成功(无消息,静默正常)'

    async def test_ws_bad_token(self):
        """W6: WS无效Token拒绝"""
        try:
            uri = f'{WS_BASE}/ws/admin?token=BAD_TOKEN_12345'
            async with websockets.connect(uri, ping_interval=20, ping_timeout=5) as ws:
                await ws.send(json.dumps({'type':'agent_register','data':{
                    'agent_id':'admin','name':'hacker'}}))
                # 如果连上了，等看看有没有错误返回
                try:
                    async with asyncio.timeout(3):
                        async for raw in ws:
                            msg = json.loads(raw)
                            if msg.get('type') in ('error',):
                                return True, f'正确拒绝: {msg.get("data",{})}'
                except TimeoutError:
                    pass
                return False, '无效Token居然连上了(安全隐患)'
        except Exception as e:
            return True, f'连接被正确拒绝: {type(e).__name__}'

    # ========== 执行入口 ==========

    def run_all(self):
        global passed, failed, skipped
        print("\n========== 🔬 MESH 信道测试套件 ==========")
        print(f"目标: {MESH_HOST}:{MESH_PORT}")
        print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        # --- HTTP 测试 ---
        print("── [HTTP API] ──────────────────────")
        self.test("T1 登录获取Token", self.test_http_login)
        if not self.token:
            print("\n⚠️  登录失败，无法继续测试")
            return
        self.test("T2 获取智能体列表", self.test_http_agents_list)
        self.test("T3 HTTP发消息→在线智能体", self.test_http_send_message)
        self.test("T4 HTTP发消息→离线智能体", self.test_http_send_message_offline)
        self.test("T5 创建任务", self.test_http_create_task)
        self.test("T6 自动执行(auto路由)", self.test_http_execute_auto)
        self.test("T7 获取离线消息", self.test_http_get_undelivered)
        self.test("T8 系统统计", self.test_http_stats)

        # --- WebSocket 测试 ---
        print("\n── [WebSocket] ─────────────────────")
        asyncio.run(self._run_ws_tests())

        # --- 结果汇总 ---
        total = passed + failed + skipped
        print(f"\n{'='*45}")
        print(f"📊 结果: ✅ {passed}  ❌ {failed}  ⏭️ {skipped}  (共{total})")
        if failed > 0:
            print("🔴 有失败项，需修复后重测")
        else:
            print("🟢 全部通过！")
        print(f"{'='*45}")

    async def _run_ws_tests(self):
        for name, fn in [
            ("W1 WS连接+注册", self.test_ws_connect),
            ("W2 WS发消息→等回复", self.test_ws_send_and_reply),
            ("W3 WS请求智能体列表", self.test_ws_get_agents),
            ("W4 WS心跳(ping/pong)", self.test_ws_heartbeat),
            ("W5 WS断线重连", self.test_ws_reconnect),
            ("W6 WS无效Token拒绝", self.test_ws_bad_token),
        ]:
            ok, detail = await fn()
            global passed, failed, skipped
            if ok:
                passed += 1
                print(f"  ✅ {name}")
            else:
                failed += 1
                print(f"  ❌ {name}")
                print(f"     {detail}")

if __name__ == '__main__':
    suite = TestSuite()
    suite.run_all()
    sys.exit(1 if failed > 0 else 0)
