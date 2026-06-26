"""小希-Mesh v2 消息中转服务 - 兼容入口

保留 server:app 引用，确保 uvicorn server:app 仍可启动。
"""
from main import app
