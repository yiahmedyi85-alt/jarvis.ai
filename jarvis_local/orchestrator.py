from __future__ import annotations
import re
from .providers import GeminiProvider
from .tools import execute
from .storage import log, load, save
from .system_monitor import Monitor
from datetime import datetime

class JarvisAgent:
    def __init__(self): self.llm = GeminiProvider()
    def _memory_context(self): return load("memory.json", [])[-20:]
    def handle(self, text: str, confirmed: bool = False):
        t=text.strip(); low=t.lower()
        if not t:return {"state":"failed","message":"Empty request","tool":"orchestrator"}
        try:
            if re.search(r"\b(cpu|ram|memory|disk|gpu|battery|system status|computer status|most cpu)\b",low):
                d=Monitor().snapshot(); return {"state":"completed","tool":"system.status","data":d,"message":self._system_message(d)}
            if re.search(r"open (my )?downloads",low): return execute("folder.downloads",{})
            m=re.match(r"(?:jarvis[, ]*)?(?:open|launch|start) (.+)$",t,re.I)
            if m:return execute("app.open",{"target":m.group(1).strip()})
            m=re.match(r"(?:jarvis[, ]*)?(?:search|google) (?:the web )?(?:for )?(.+)$",t,re.I)
            if m:return execute("web.search",{"query":m.group(1).strip()})
            m=re.match(r"(?:jarvis[, ]*)?open (https?://\S+|www\.\S+)$",t,re.I)
            if m:return execute("browser.open",{"url":m.group(1)})
            if "summarize this page" in low or "summarize the page" in low:
                return {"state":"failed","tool":"browser.summarize","message":"I need an accessible page URL or browser-content provider to summarize a page. I did not pretend to read it."}
            if "play some music" in low or "play music" in low:return execute("app.open",{"target":"Spotify"})
            if "check my calendar" in low or "what's next" in low:
                events=load("calendar.json",[]); today=datetime.now().date().isoformat(); today_events=[e for e in events if e.get("date")==today]
                return {"state":"completed","tool":"calendar.local","data":today_events,"message":("Today: "+", ".join(e.get("title","Event") for e in today_events)) if today_events else "No events are scheduled for today."}
            if "create a task" in low and len(t.split())<=4:
                return {"state":"completed","tool":"tasks.local","message":"Task panel opened. Add a title and optional due date there."}
            m=re.match(r"(?:jarvis[, ]*)?(?:create|make) (?:a )?folder(?: called| named)? (.+)$",t,re.I)
            if m:return execute("file.create_folder",{"path":m.group(1).strip()})
            m=re.match(r"(?:jarvis[, ]*)?(?:delete|remove) (?:file )?(.+)$",t,re.I)
            if m:return execute("file.delete",{"path":m.group(1).strip()},confirmed=confirmed)
            if re.search(r"\b(list|show) (my )?(files|downloads)\b",low):return execute("file.list",{})
            if re.search(r"\b(search|find) .*files?\b",low):
                q=re.sub(r".*?\b(?:search|find)(?: for)?\s+","",t,flags=re.I).strip(); return execute("file.search",{"query":q})
            if re.search(r"\b(remember|save this|remember that)\b",low):
                mem=load("memory.json",[]); mem.append({"text":t,"source":"user","type":"non-sensitive","saved":datetime.now().isoformat(timespec="seconds")}); save("memory.json",mem[-200:]); log(t,"memory","Saved local memory","success"); return {"state":"completed","tool":"memory.save","message":"Saved that as local non-sensitive memory."}
            reply=self.llm.chat(t,memory=self._memory_context()); return {"state":"speaking","tool":"llm.chat","message":reply}
        except Exception as exc:
            log(t,"orchestrator",str(exc),"failed"); return {"state":"failed","tool":"orchestrator","message":str(exc)}
    @staticmethod
    def _system_message(d):
        parts=[f"CPU {d['cpu']:.0f}%",f"RAM {d['memory']:.0f}%",f"Disk {d['disk']:.0f}%"]
        if d.get('gpu') is not None:parts.append(f"GPU {d['gpu']:.0f}%")
        if d.get('battery') is not None:parts.append(f"Battery {d['battery']:.0f}%")
        return "System status: "+" · ".join(parts)
