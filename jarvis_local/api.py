from __future__ import annotations
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from .system_monitor import Monitor

BASE=Path(__file__).resolve().parent.parent
monitor=Monitor()


def create_app():
    app=FastAPI(title="JARVIS Local")
    @app.get("/",response_class=HTMLResponse)
    async def home():
        return (BASE/"desktop_ui.html").read_text(encoding="utf-8")
    @app.get("/api/system")
    async def system(): return monitor.snapshot()
    @app.post("/api/chat")
    async def chat(payload:dict):
        from .orchestrator import JarvisAgent
        text=str(payload.get("text","")).strip()
        if not text:return {"state":"failed","message":"Empty request"}
        return await asyncio.to_thread(JarvisAgent().handle,text)
    @app.websocket("/ws")
    async def ws(sock:WebSocket):
        await sock.accept()
        try:
            while True:
                await sock.send_json({"type":"system","data":monitor.snapshot()})
                await asyncio.sleep(2)
        except (WebSocketDisconnect,asyncio.CancelledError): pass
    return app
