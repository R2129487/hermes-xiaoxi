#!/usr/bin/env python3
"""小青 MESH 客户端 — 连接本地 MESH，接收消息并回复"""
import asyncio
import json
import logging
import websockets

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger('xiaoqing')

MESH_HOST = '127.0.0.1'
MESH_PORT = 8765
AGENT_ID = 'xiaoqing'

# xiaoqing 专用 token 文件
TOKEN_FILE = '/tmp/xiaoqing_token.txt'

def read_token():
    """从文件读取 xiaoqing 的 token"""
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except Exception:
        return ''


async def handle_message(data: dict, ws) -> str | None:
    """处理收到的消息，返回回复内容"""
    msg_type = data.get('type', '')
    msg_data = data.get('data', data)
    
    if msg_type == 'ping':
        await ws.send(json.dumps({'type': 'pong'}))
        return None
    elif msg_type == 'pong':
        return None
    elif msg_type in ('send', 'message'):
        content = msg_data.get('content', '')
        from_id = msg_data.get('from_id', '') or msg_data.get('from', '')
        call_id = msg_data.get('call_id', '') or data.get('call_id', '')
        
        log.info(f'收到消息 from={from_id}: {content[:100]}...')
        print(f'\n📩 [{from_id}] {content}', flush=True)
        
        # 回复确认
        reply_data = {
            'type': 'message',
            'data': {
                'from_id': AGENT_ID,
                'to_id': from_id,
                'content': f'收到来自 {from_id} 的消息',
            }
        }
        await ws.send(json.dumps(reply_data))
        return content
    else:
        log.info(f'未知消息类型: {msg_type}')
        return None


async def main():
    log.info(f'=== 小青 MESH 客户端启动 (agent_id={AGENT_ID}) ===')
    while True:
        try:
            token = read_token()
            if not token:
                log.error('无法读取 token，重试中...')
                await asyncio.sleep(10)
                continue
            uri = f'ws://{MESH_HOST}:{MESH_PORT}/ws/{AGENT_ID}?token={token}'
            log.info(f'连接 MESH: {uri}')
            
            async with websockets.connect(uri, ping_interval=20, ping_timeout=10) as ws:
                log.info('WebSocket 已连接')
                print(f'✅ 小青 MESH 客户端已上线 (agent_id={AGENT_ID})', flush=True)
                
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                        await handle_message(data, ws)
                    except json.JSONDecodeError:
                        log.warning(f'消息解析失败: {raw[:200]}')
                    except Exception as e:
                        log.error(f'处理消息异常: {e}')
                        
        except websockets.ConnectionClosed:
            log.warning('连接断开，5秒后重连...')
            await asyncio.sleep(5)
        except Exception as e:
            log.error(f'连接异常: {e}')
            await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(main())
