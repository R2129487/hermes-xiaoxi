# 小希-Mesh 消息中转服务

为 AI 助手团队（小白、小青、小蓝）搭建的消息中转服务，参考 OpenAI Codex / Raft 架构。

## 架构

```
┌─────────────────────────────────────────┐
│          消息中转服务器 (阿里云)            │
│  WebSocket (实时) + HTTP API (管理/离线)  │
│            SQLite 持久化存储               │
└──────────┬──────────────┬───────────────┘
           │              │
     ┌─────┴─────┐  ┌────┴─────┐
     │   小白     │  │   小青   │  ...
     │  (新云)    │  │ (Y7000)  │
     └───────────┘  └──────────┘
```

## 快速开始

```bash
# 1. 装依赖
pip install -r requirements.txt

# 2. 启动服务
python3 server.py

# 3. 注册智能体（在其他机器上）
curl -X POST http://SERVER_IP:8765/api/agents/register \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "xiaoqing", "name": "小青", "role": "agent"}'
# 返回 token，保存好

# 4. 客户端连接
python3 -c "
import asyncio
from client import MeshClient

async def main():
    c = MeshClient('ws://SERVER_IP:8765', 'xiaoqing', 'YOUR_TOKEN')
    c.on_message(lambda m: print(f'收到: {m[\"content\"]}'))
    await asyncio.gather(
        c.connect(),
        # 5秒后发条消息
        (asyncio.sleep(5), c.send('xiaobai', '你好小白'))
    )

asyncio.run(main())
"
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/auth/login` | 管理员登录 |
| POST | `/api/agents/register` | 注册智能体 |
| GET | `/api/agents` | 智能体列表 |
| GET | `/api/agents/{id}` | 智能体详情 |
| GET | `/api/messages/{id}` | 获取离线消息 |
| POST | `/api/messages/send` | 发送消息 |
| POST | `/api/agents/status` | 更新状态 |
| WS | `/ws/{agent_id}` | 实时通信 |

## WebSocket 消息格式

**发送消息:**
```json
{"type": "send", "to": "xiaobai", "content": "你好", "data_type": "text"}
```

**接收消息:**
```json
{"type": "message", "data": {"from_id": "xiaobai", "content": "你好", ...}}
```

**心跳:**
```json
{"type": "ping"}  →  {"type": "pong"}
```
