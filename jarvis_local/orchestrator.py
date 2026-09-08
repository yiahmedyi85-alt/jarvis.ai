from __future__ import annotations
import re
from .providers import GeminiProvider
from .tools import execute
from .storage import log, load, save
from .system_monitor import Monitor

class JarvisAgent:
    def __init__(self):
        self.llm = GeminiProvider()

    def _memory_context(self):
        return load("memory.json", [])[-20:]

    def handle(self, text: str, confirmed: bool = False):
        t = text.strip()
        if not t: return {"state":"failed", "message":"Empty request", "tool":"orchestrator"}
        low = t.lower()
        try:
            if re.search(r"\b(cpu|ram|memory|disk|gpu|battery|system status|computer status|most cpu)\b", low):
                data = Monitor().snapshot()
                return {"state":"completed", "tool":"system.status", "data":data, "message":self._system_message(data)}
            if re.search(r"open (my )?downloads", low):
                return execute("folder.downloads", {})
            m = re.match(r"(?:jarvis[, ]*)?(?:open|launch|start) (.+)$", t, re.I)
            if m: return execute("app.open", {"target":m.group(1).strip()})
            m = re.match(r"(?:jarvis[, ]*)?(?:search|google) (?:the web )?(?:for )?(.+)$", t, re.I)
            if m: return execute("web.search", {"query":m.group(1).strip()})
            m = re.match(r"(?:jarvis[, ]*)?open (https?://\S+|www\.\S+)$", t, re.I)
            if m: return execute("browser.open", {"url":m.group(1)})
            m = re.match(r"(?:jarvis[, ]*)?(?:create|make) (?:a )?folder(?: called| named)? (.+)$", t, re.I)
            if m: return execute("file.create_folder", {"path":m.group(1).strip()})
            m = re.match(r"(?:jarvis[, ]*)?(?:delete|remove) (?:file )?(.+)$", t, re.I)
            if m: return execute("file.delete", {"path":m.group(1).strip()}, confirmed=confirmed)
            if re.search(r"\b(list|show) (my )?(files|downloads)\b", low):
                return execute("file.list", {})
            if re.search(r"\b(search|find) (for )?.*files?\b", low):
                q = re.sub(r".*?\b(?:search|find)(?: for)?\s+", "", t, flags=re.I).strip()
                return execute("file.search", {"query":q})
            if re.search(r"\b(note|remember)\b", low):
                mem = load("memory.json", [])
                mem.append({"text":t, "source":"user", "type":"non-sensitive"})
                save("memory.json", mem[-200:])
                log(t, "memory", "Saved local memory", "success")
                return {"state":"completed","tool":"memory.save","message":"Saved that as local non-sensitive memory."}
            reply = self.llm.chat(t, memory=self._memory_context())
            return {"state":"speaking", "tool":"llm.chat", "message":reply}
        except Exception as exc:
            log(t, "orchestrator", str(exc), "failed")
            return {"state":"failed", "tool":"orchestrator", "message":str(exc)}

    @staticmethod
    def _system_message(d):
        parts=[f"CPU {d['cpu']:.0f}%", f"RAM {d['memory']:.0f}%", f"Disk {d['disk']:.0f}%"]
        if d.get('gpu') is not None: parts.append(f"GPU {d['gpu']:.0f}%")
        if d.get('battery') is not None: parts.append(f"Battery {d['battery']:.0f}%")
        return "System status: " + " · ".join(parts)
