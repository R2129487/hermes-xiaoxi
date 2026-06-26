#!/usr/bin/env python3
"""小青 MESH 客户端 v3 — 带状态刷新，稳定版"""
import asyncio
import json
import logging
import time
import urllib.request
import traceback
import websockets

LOG_FILE = '/tmp/xiaoqing_mesh.log'
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('xiaoqing')

MESH_HOST = '101.37.231.143'
MESH_PORT = 8765

def get_token():
    req = urllib.request.Request(
        f'http://{MESH_HOST}:{MESH_PORT}/api/auth/login',
        data=json.dumps({'username': 'admin', 'password': '840601'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    return json.loads(urllib.request.urlopen(req, timeout=10).read())['data']['token']

async def main():
    log.info('=== 小青 MESH 客户端 v3 启动 ===')
    while True:
        try:
            token = get_token()
            uri = f'ws://{MESH_HOST}:{MESH_PORT}/ws/admin?token={token}'
            log.info('连接 MESH...')

            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
                log.info('WebSocket 已连接')
                await ws.send(json.dumps({
                    'type': 'agent_register',
                    'data': {
                        'agent_id': 'admin',
                        'name': '管理员',
                        'role': 'admin',
                    }
                }))
                log.info('已注册在线')

                last_refresh = time.time()

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        t = msg.get('type', '')

                        if t == 'pong':
                            continue

                        log.info(f'收到 type={t}')

                        if t == 'message':
                            data = msg.get('data', {})
                            content = data.get('content', '')
                            from_id = data.get('from_id', '')
                            log.info(f'📩 来自 {from_id}: {content}')
                            await ws.send(json.dumps({
                                'type': 'message',
                                'to': from_id,
                                'content': f'👋 收到: {content}',
                                'from': 'admin',
                            }))
                            log.info(f'✅ 已回复 {from_id}')

                        elif t == 'agents_update':
                            agents = msg.get('data', {}).get('agents', [])
                            online = [f"{a['name']}({a['agent_id']})" for a in agents if a.get('online')]
                            log.info(f'👥 在线: {", ".join(online)}')

                        elif t == 'status':
                            d = msg.get('data', {})
                            log.info(f'📋 {d.get("agent_id")} = {d.get("status")}')

                        elif t in ('task_request', 'task_created', 'task_completed'):
                            log.info(f'📋 {t}: {json.dumps(msg.get("data",{}), ensure_ascii=False)[:150]}')

                        elif t == 'error':
                            log.error(f'❌ {msg.get("data", {})}')

                        # 每60秒刷新一次在线状态
                        if time.time() - last_refresh > 60:
                            log.info('🔄 刷新在线状态')
                            await ws.send(json.dumps({
                                'type': 'agent_register',
                                'data': {
                                    'agent_id': 'admin',
                                    'name': '管理员',
                                    'role': 'admin',
                                }
                            }))
                            last_refresh = time.time()

                    except json.JSONDecodeError:
                        log.warning(f'JSON解析失败')
                    except Exception as e:
                        log.error(f'处理异常: {e}')

        except websockets.ConnectionClosed as e:
            log.warning(f'断开 (code={e.code}): {e.reason}')
        except asyncio.TimeoutError:
            log.warning('超时')
        except Exception as e:
            log.error(f'异常: {e}\n{traceback.format_exc()}')

        log.info('5秒后重连...')
        await asyncio.sleep(5)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info('已退出')
