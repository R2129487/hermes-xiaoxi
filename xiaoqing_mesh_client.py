#!/usr/bin/env python3
"""小青 MESH 客户端 — 保持本机在线，处理消息"""
import asyncio
import json
import logging
import time
import urllib.request
import websockets

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('xiaoqing')

MESH_HOST = '101.37.231.143'
MESH_PORT = 8765
ADMIN_USER = 'admin'
ADMIN_PASS = '840601'

class XiaoqingMeshClient:
    def __init__(self):
        self.token = None
        self.ws = None
        self.agent_id = 'xiaoqing'
        self._running = True
        self._last_pong = time.time()

    def _get_admin_token(self):
        """登录 MESH 拿 admin token"""
        req = urllib.request.Request(
            f'http://{MESH_HOST}:{MESH_PORT}/api/auth/login',
            data=json.dumps({'username': ADMIN_USER, 'password': ADMIN_PASS}).encode(),
            headers={'Content-Type': 'application/json'}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        self.token = data['data']['token']
        log.info(f'获取 admin token 成功，长度: {len(self.token)}')

    async def _send_json(self, data: dict):
        if self.ws:
            await self.ws.send(json.dumps(data))

    async def _handle_message(self, raw: str):
        """处理收到的消息"""
        try:
            msg = json.loads(raw)
            msg_type = msg.get('type', '')
            log.info(f'收到消息: type={msg_type}')

            if msg_type == 'pong':
                self._last_pong = time.time()
                return

            if msg_type == 'message':
                data = msg.get('data', {})
                content = data.get('content', '')
                from_id = data.get('from_id', msg.get('from', ''))
                log.info(f'来自 {from_id}: {content}')

                # TODO: 回复消息需要了解 MESH 的消息回复格式
                # 先发回执
                await self._send_json({
                    'type': 'message',
                    'to': from_id,
                    'content': f'[小青收到] {content}',
                    'from': self.agent_id,
                })
                log.info(f'已回复 {from_id}')

            elif msg_type == 'agents_update':
                agents = msg.get('data', {}).get('agents', [])
                online = [a['agent_id'] for a in agents if a.get('online')]
                log.info(f'在线智能体: {online}')

            elif msg_type == 'error':
                log.error(f'MESH 错误: {msg.get("data", {})}')

        except json.JSONDecodeError:
            log.warning(f'无法解析消息: {raw[:100]}')
        except Exception as e:
            log.error(f'处理消息异常: {e}')

    async def connect(self):
        """连接 MESH WebSocket"""
        self._get_admin_token()
        uri = f'ws://{MESH_HOST}:{MESH_PORT}/ws/admin?token={self.token}'

        while self._running:
            try:
                async with websockets.connect(uri, ping_interval=None) as ws:
                    self.ws = ws
                    self._last_pong = time.time()
                    log.info(f'WebSocket 已连接 (agent_id={self.agent_id})')

                    # 注册在线状态
                    await self._send_json({
                        'type': 'agent_register',
                        'data': {
                            'agent_id': self.agent_id,
                            'name': '小青',
                            'role': 'agent',
                            'description': '本机AI助手',
                            'capabilities': ['code_generation', 'file_transfer', 'web_search', 'translation', 'desktop_automation', 'wechat_operations'],
                            'specialties': ['编程开发', '文件管理', '网络搜索', '桌面自动化', '微信操作'],
                        }
                    })
                    log.info('已发送注册消息')

                    # 心跳 + 消息监听
                    async def heartbeat():
                        while self._running:
                            await asyncio.sleep(25)
                            try:
                                await self._send_json({'type': 'ping'})
                                # 检查 pong 超时（60秒）
                                if time.time() - self._last_pong > 60:
                                    log.warning('pong 超时，准备重连')
                                    await ws.close()
                                    break
                            except:
                                break

                    async def listener():
                        async for raw in ws:
                            await self._handle_message(raw)

                    # 并发运行心跳和监听
                    await asyncio.gather(
                        heartbeat(),
                        listener()
                    )

            except websockets.ConnectionClosed as e:
                log.warning(f'连接断开 (code={e.code}): {e.reason}')
            except Exception as e:
                log.error(f'连接异常: {e}')

            if self._running:
                log.info('5秒后重连...')
                await asyncio.sleep(5)

        log.info('客户端已停止')

    def stop(self):
        self._running = False


async def main():
    client = XiaoqingMeshClient()
    try:
        await client.connect()
    except KeyboardInterrupt:
        client.stop()
        log.info('已退出')

if __name__ == '__main__':
    asyncio.run(main())
