from __future__ import annotations
import re, os, webbrowser, subprocess, platform
from pathlib import Path
from .providers import GeminiProvider

class JarvisAgent:
    def __init__(self): self.llm=GeminiProvider()
    def handle(self,text):
        t=text.strip()
        try:
            m=re.match(r"^(?:jarvis[, ]*)?(?:open|launch|start) (.+)$",t,re.I)
            if m:
                name=m.group(1).strip()
                if platform.system()=="Windows": subprocess.Popen(["cmd","/c","start","",name],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                else: webbrowser.open(name)
                return {"state":"completed","message":f"Launch requested: {name}","tool":"app.open"}
            if re.search(r"open (my )?downloads( folder)?",t,re.I):
                p=Path.home()/"Downloads"
                if platform.system()=="Windows": os.startfile(str(p))
                elif platform.system()=="Darwin": subprocess.Popen(["open",str(p)])
                else: subprocess.Popen(["xdg-open",str(p)])
                return {"state":"completed","message":f"Opened {p}","tool":"folder.open"}
            if re.search(r"(what|whats|what is).*most cpu|system status|cpu|ram",t,re.I):
                from .system_monitor import Monitor
                return {"state":"completed","result":{"ok":True,"data":Monitor().snapshot()},"tool":"system.status"}
            m=re.match(r"^(?:jarvis[, ]*)search (?:the web )?(?:for )?(.+)$",t,re.I)
            if m:
                q=m.group(1).strip(); url="https://www.google.com/search?q="+q.replace(" ","+"); webbrowser.open(url)
                return {"state":"completed","message":f"Opened web search for: {q}","tool":"web.search"}
            reply=self.llm.chat(t)
            return {"state":"speaking","message":reply}
        except Exception as exc:
            return {"state":"failed","message":str(exc)}
