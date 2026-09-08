from __future__ import annotations
import asyncio, os
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from .system_monitor import Monitor
from .orchestrator import JarvisAgent
from .storage import load, save, log
from .tools import execute
from .live_voice import run_live_voice
from .desktop_events import get_state, set_state
from .scheduler import start as start_scheduler
from .call_watcher import CallWatcher

BASE=Path(__file__).resolve().parent.parent
monitor=Monitor(); agent=JarvisAgent(); _call_watcher=None

def _call_event(title: str):
    set_state(call=title, message=f"Incoming call detected: {title}")
    log("Incoming call", "call.watcher", title, "success")
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast("JARVIS — Incoming call", title, duration=5, threaded=True)
    except Exception:
        pass


def create_app():
    global _call_watcher
    app=FastAPI(title="JARVIS Local",docs_url=None,redoc_url=None)
    start_scheduler(execute)
    if _call_watcher is None:
        _call_watcher=CallWatcher(_call_event); _call_watcher.start()

    @app.get("/",response_class=HTMLResponse)
    async def home():
        html=(BASE/"desktop_ui.html").read_text(encoding="utf-8")
        tag='<script src="/voice.js"></script>'
        return html.replace("</body>", tag + "</body>") if "</body>" in html else html + tag

    @app.get("/voice.js")
    async def voice_js():
        return Response(content=(Path(__file__).with_name("voice.js")).read_text(encoding="utf-8"),media_type="application/javascript")

    @app.get("/api/system")
    async def system(): return monitor.snapshot()

    @app.get("/api/voice-state")
    async def voice_state(): return get_state()

    @app.post("/api/voice-state")
    async def voice_state_set(payload:dict): return set_state(voice=str(payload.get("voice","idle")), message=str(payload.get("message","")))

    @app.get("/api/call")
    async def call_state(): return get_state().get("call")

    @app.post("/api/call/clear")
    async def call_clear(): return set_state(call=None)

    @app.get("/api/schedule")
    async def schedule_list():
        from .scheduler import list_tasks
        return list_tasks()

    @app.post("/api/schedule")
    async def schedule_create(payload:dict):
        from .scheduler import add_task
        return add_task(str(payload.get("run_at","")),str(payload.get("action","")),payload.get("args") or {})

    @app.delete("/api/schedule/{task_id}")
    async def schedule_delete(task_id:str):
        from .scheduler import cancel_task
        return {"ok":cancel_task(task_id)}

    @app.post("/api/chat")
    async def chat(payload:dict):
        text=str(payload.get("text","")).strip(); confirmed=bool(payload.get("confirmed",False))
        if not text:return {"state":"failed","message":"Empty request"}
        return await asyncio.to_thread(agent.handle,text,confirmed)

    @app.post("/api/tool")
    async def tool(payload:dict):
        try:return await asyncio.to_thread(execute,str(payload.get("tool","")),payload.get("args") or {},bool(payload.get("confirmed",False)))
        except Exception as exc:return {"state":"failed","tool":str(payload.get("tool","")),"message":str(exc)}

    @app.get("/api/notes")
    async def notes():return load("notes.json",[])
    @app.post("/api/notes")
    async def save_note(payload:dict):
        notes=load("notes.json",[]); note={"id":str(payload.get("id") or datetime.now().timestamp()),"title":str(payload.get("title","Untitled")),"text":str(payload.get("text","")),"updated":datetime.now().isoformat(timespec="seconds")}; notes=[n for n in notes if n.get("id")!=note["id"]]; notes.insert(0,note); save("notes.json",notes[:500]); log("Save note","notes",note["title"],"success"); return note
    @app.delete("/api/notes/{note_id}")
    async def delete_note(note_id:str): save("notes.json",[n for n in load("notes.json",[]) if str(n.get("id"))!=note_id]); log("Delete note","notes",note_id,"success"); return {"ok":True}
    @app.get("/api/tasks")
    async def tasks():return load("tasks.json",[])
    @app.post("/api/tasks")
    async def save_task(payload:dict):
        tasks=load("tasks.json",[]); task={"id":str(payload.get("id") or datetime.now().timestamp()),"title":str(payload.get("title","Task")),"due":str(payload.get("due","")),"done":bool(payload.get("done",False))}; tasks=[x for x in tasks if x.get("id")!=task["id"]]; tasks.insert(0,task); save("tasks.json",tasks[:500]); log(task["title"],"tasks","Saved","success"); return task
    @app.patch("/api/tasks/{task_id}")
    async def update_task(task_id:str,payload:dict):
        tasks=load("tasks.json",[])
        for x in tasks:
            if str(x.get("id"))==task_id:x.update(payload)
        save("tasks.json",tasks); return next((x for x in tasks if str(x.get("id"))==task_id),None)
    @app.get("/api/calendar")
    async def calendar():return load("calendar.json",[])
    @app.post("/api/calendar")
    async def calendar_add(payload:dict):
        events=load("calendar.json",[]); event={"id":str(datetime.now().timestamp()),"title":str(payload.get("title","Event")),"date":str(payload.get("date",datetime.now().date().isoformat())),"time":str(payload.get("time",""))}; events.append(event); save("calendar.json",events[-500:]); log(event["title"],"calendar","Saved","success"); return event
    @app.get("/api/memory")
    async def memory():return load("memory.json",[])
    @app.delete("/api/memory")
    async def clear_memory():save("memory.json",[]); log("Clear memory","memory","All local memory cleared","success"); return {"ok":True}
    @app.get("/api/activity")
    async def activity():return list(reversed(load("activity.json",[])))[:100]
    defaults={"voice":True,"wake_word":False,"monitor_interval":2,"memory":True,"notifications":True,"startup":False,"confirm_destructive":True}
    @app.get("/api/settings")
    async def settings(): s=defaults.copy(); s.update(load("settings.json",{})); return s
    @app.post("/api/settings")
    async def settings_save(payload:dict):
        current=defaults.copy(); current.update(load("settings.json",{})); current.update(payload)
        if "startup" in payload:
            try:
                from .startup import set_startup
                launcher=str(BASE.parent/"jarvis_desktop.py"); ok,msg=set_startup(bool(payload["startup"]),launcher); current["startup"]=bool(payload["startup"]) if ok else False; log("Startup setting","startup",msg,"success" if ok else "failed")
            except Exception as exc: current["startup"]=False; log("Startup setting","startup",str(exc),"failed")
        save("settings.json",current); return current
    @app.websocket("/api/live")
    async def live_voice(sock:WebSocket):
        await sock.accept()
        try: await run_live_voice(sock)
        except WebSocketDisconnect: pass
        except Exception as exc:
            try: await sock.send_json({"type":"error","message":str(exc)})
            except Exception: pass
        finally:
            try: await sock.close()
            except Exception: pass
    @app.websocket("/ws")
    async def ws(sock:WebSocket):
        await sock.accept()
        try:
            while True:
                await sock.send_json({"type":"system","data":monitor.snapshot()}); await asyncio.sleep(2)
        except (WebSocketDisconnect,asyncio.CancelledError):pass
    return app
