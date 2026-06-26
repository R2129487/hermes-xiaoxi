from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from starlette.routing import WebSocketRoute

from app_state import store, registry, delegator, log
from routes import (
    health_router,
    auth_router,
    agents_router,
    messages_router,
    capabilities_router,
    tasks_router,
    decisions_router,
    audit_router,
    tokens_router,
    permissions_router,
    stats_router,
    brain_router,
)
from web_ui import get_web_html
from websocket_handler import websocket_endpoint, _send_to_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.init()
    await registry.load_from_db()
    delegator.set_broadcast(_send_to_agent)
    log.info("小希-Mesh v2 服务启动完成")
    yield
    await store.close()
    log.info("小希-Mesh v2 服务关闭")


app = FastAPI(title="小希-Mesh v2", version="2.0.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(messages_router)
app.include_router(capabilities_router)
app.include_router(tasks_router)
app.include_router(decisions_router)
app.include_router(audit_router)
app.include_router(tokens_router)
app.include_router(permissions_router)
app.include_router(stats_router)
app.include_router(brain_router)


@app.get("/")
@app.get("/web/")
@app.get("/web/login")
async def web_ui():
    return HTMLResponse(content=get_web_html())


# Add WebSocket route using Starlette's WebSocketRoute
# The endpoint receives a WebSocket session with path_params populated
async def ws_handler(session):
    agent_id = session.path_params["agent_id"]
    await websocket_endpoint(session, agent_id)


app.router.routes.append(WebSocketRoute("/ws/{agent_id:str}", endpoint=ws_handler))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8765, reload=False)
