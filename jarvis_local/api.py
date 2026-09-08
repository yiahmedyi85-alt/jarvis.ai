from __future__ import annotations
import asyncio
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from .system_monitor import Monitor
from .orchestrator import JarvisAgent
from .storage import load, save, log
from .tools import execute, CONFIRM_REQUIRED

BASE = Path(__file__).resolve().parent.parent
monitor = Monitor()
agent = JarvisAgent()


def create_app():
    app = FastAPI(title="JARVIS Local", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def home():
        return (BASE / "desktop_ui.html").read_text(encoding="utf-8")

    @app.get("/api/system")
    async def system(): return monitor.snapshot()

    @app.post("/api/chat")
    async def chat(payload: dict):
        text = str(payload.get("text", "")).strip()
        confirmed = bool(payload.get("confirmed", False))
        if not text: return {"state":"failed", "message":"Empty request"}
        return await asyncio.to_thread(agent.handle, text, confirmed)

    @app.post("/api/tool")
    async def tool(payload: dict):
        name = str(payload.get("tool", "")); args = payload.get("args") or {}
        confirmed = bool(payload.get("confirmed", False))
        try: return await asyncio.to_thread(execute, name, args, confirmed)
        except Exception as exc: return {"state":"failed", "tool":name, "message":str(exc)}

    @app.get("/api/notes")
    async def notes(): return load("notes.json", [])

    @app.post("/api/notes")
    async def save_note(payload: dict):
        notes = load("notes.json", [])
        note = {"id": str(payload.get("id") or datetime.now().timestamp()), "title": str(payload.get("title", "Untitled")), "text": str(payload.get("text", "")), "updated": datetime.now().isoformat(timespec="seconds")}
        notes = [n for n in notes if n.get("id") != note["id"]]
        notes.insert(0, note); save("notes.json", notes[:500]); log("Save note", "notes", note["title"], "success"); return note

    @app.delete("/api/notes/{note_id}")
    async def delete_note(note_id: str):
        notes = [n for n in load("notes.json", []) if str(n.get("id")) != note_id]
        save("notes.json", notes); log("Delete note", "notes", note_id, "success"); return {"ok":True}

    @app.get("/api/tasks")
    async def tasks(): return load("tasks.json", [])

    @app.post("/api/tasks")
    async def save_task(payload: dict):
        tasks = load("tasks.json", [])
        task = {"id": str(payload.get("id") or datetime.now().timestamp()), "title": str(payload.get("title", "Task")), "due": str(payload.get("due", "")), "done": bool(payload.get("done", False))}
        tasks = [x for x in tasks if x.get("id") != task["id"]]; tasks.insert(0, task); save("tasks.json", tasks[:500]); log(task["title"], "tasks", "Saved", "success"); return task

    @app.get("/api/calendar")
    async def calendar(): return load("calendar.json", [])

    @app.post("/api/calendar")
    async def calendar_add(payload: dict):
        events=load("calendar.json", []); event={"id":str(datetime.now().timestamp()),"title":str(payload.get("title","Event")),"date":str(payload.get("date",datetime.now().date().isoformat())),"time":str(payload.get("time",""))}; events.append(event); save("calendar.json",events[-500:]); return event

    @app.get("/api/memory")
    async def memory(): return load("memory.json", [])

    @app.delete("/api/memory")
    async def clear_memory(): save("memory.json", []); log("Clear memory", "memory", "All local memory cleared", "success"); return {"ok":True}

    @app.get("/api/activity")
    async def activity(): return list(reversed(load("activity.json", [])))[:100]

    @app.get("/api/settings")
    async def settings(): return load("settings.json", {"voice":True,"wake_word":False,"monitor_interval":2,"memory":True,"notifications":True,"startup":False,"confirm_destructive":True})

    @app.post("/api/settings")
    async def settings_save(payload: dict):
        current=load("settings.json", {}); current.update(payload); save("settings.json",current); return current

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        try:
            while True:
                await sock.send_json({"type":"system","data":monitor.snapshot()})
                await asyncio.sleep(2)
        except (WebSocketDisconnect, asyncio.CancelledError): pass
    return app
