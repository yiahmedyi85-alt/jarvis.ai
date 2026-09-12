from __future__ import annotations

import re
from datetime import datetime
from .providers import GeminiProvider, registry
from .tools import execute
from .storage import log, load, save
from .system_monitor import Monitor
from .scheduler import add_task
from .desktop_events import set_state


class JarvisAgent:
    def __init__(self):
        self.llm = GeminiProvider()

    def _memory_context(self):
        return load("memory.json", [])[-20:]

    def _set_phase(self, phase: str, message: str = ""):
        try:
            set_state(voice=phase, message=message)
        except Exception:
            pass

    def _schedule_command(self, t):
        m = re.match(r"(?:jarvis[, ]*)?(?:at|for)\s+(.+?)\s+(?:open|launch|start)\s+(.+)$", t, re.I)
        if m:
            from .scheduler import parse_time_phrase
            dt = parse_time_phrase("at " + m.group(1))
            if dt:
                return {"state": "completed", "tool": "schedule.add", "data": add_task(dt.isoformat(), "app.open", {"target": m.group(2).strip()}), "message": f"Scheduled {m.group(2).strip()} for {dt.strftime('%I:%M %p')}.", "verified": True}
        return None

    def handle(self, text: str, confirmed: bool = False):
        t = text.strip(); low = t.lower()
        if not t:
            return {"state": "failed", "message": "Empty request", "tool": "orchestrator"}
        self._set_phase("thinking", "Understanding request")
        try:
            scheduled = self._schedule_command(t)
            if scheduled:
                self._set_phase("speaking", scheduled["message"])
                return scheduled
            if re.search(r"\b(cpu|ram|memory|disk|gpu|battery|system status|computer status|most cpu)\b", low):
                d = Monitor().snapshot(); result = {"state": "completed", "tool": "system.status", "data": d, "message": self._system_message(d), "verified": True}
                self._set_phase("speaking", result["message"]); return result
            if re.search(r"\b(lock|lock my computer|lock the computer)\b", low):
                return self._run_tool("system.lock", {}, confirmed)
            if re.search(r"\b(sleep|put (?:the )?computer to sleep)\b", low):
                return self._run_tool("system.sleep", {}, confirmed)
            if re.search(r"\b(cancel shutdown|abort shutdown)\b", low):
                return self._run_tool("system.cancel_shutdown", {}, confirmed)
            if re.search(r"\b(shut down|shutdown)\b", low):
                return self._run_tool("system.shutdown", {}, confirmed)
            m = re.match(r"(?:jarvis[, ]*)?move mouse to (\d+)\s*,\s*(\d+)$", t, re.I)
            if m: return self._run_tool("mouse.move", {"x": int(m.group(1)), "y": int(m.group(2))}, confirmed)
            m = re.match(r"(?:jarvis[, ]*)?(?:press|hit)\s+([a-zA-Z0-9_]+)$", t, re.I)
            if m: return self._run_tool("keyboard.press", {"key": m.group(1)}, confirmed)
            m = re.match(r"(?:jarvis[, ]*)?type\s+(.+)$", t, re.I)
            if m: return self._run_tool("keyboard.type", {"text": m.group(1)}, confirmed)
            if re.search(r"\b(list|show) (my )?(scheduled tasks|schedules|timers)\b", low):
                return {"state": "completed", "tool": "schedule.list", "data": load("scheduled_tasks.json", []), "message": "Here are the scheduled tasks.", "verified": True}
            if "open my downloads" in low: return self._run_tool("folder.downloads", {}, confirmed)
            m = re.match(r"(?:jarvis[, ]*)?(?:open|launch|start) (.+)$", t, re.I)
            if m: return self._run_tool("app.open", {"target": m.group(1).strip()}, confirmed)
            m = re.match(r"(?:jarvis[, ]*)?(?:search|google) (?:the web )?(?:for )?(.+)$", t, re.I)
            if m: return self._run_tool("web.search", {"query": m.group(1).strip()}, confirmed)
            m = re.match(r"(?:jarvis[, ]*)?open (https?://\S+|www\.\S+)$", t, re.I)
            if m: return self._run_tool("browser.open", {"url": m.group(1)}, confirmed)
            if "play some music" in low or "play music" in low: return self._run_tool("app.open", {"target": "Spotify"}, confirmed)
            if "check my calendar" in low or "what's next" in low:
                events = load("calendar.json", []); today = datetime.now().date().isoformat(); todays = [e for e in events if e.get("date") == today]
                return {"state": "completed", "tool": "calendar.local", "data": todays, "message": ("Today: " + ", ".join(e.get("title", "Event") for e in todays)) if todays else "No events are scheduled for today.", "verified": True}
            m = re.match(r"(?:jarvis[, ]*)?(?:create|make) (?:a )?folder(?: called| named)? (.+)$", t, re.I)
            if m: return self._run_tool("file.create_folder", {"path": m.group(1).strip()}, confirmed)
            m = re.match(r"(?:jarvis[, ]*)?(?:delete|remove) (?:file )?(.+)$", t, re.I)
            if m: return self._run_tool("file.delete", {"path": m.group(1).strip()}, confirmed)
            if re.search(r"\b(list|show) (my )?(files|downloads)\b", low): return self._run_tool("file.list", {}, confirmed)
            if re.search(r"\b(search|find) .*files?\b", low):
                q = re.sub(r".*?\b(?:search|find)(?: for)?\s+", "", t, flags=re.I).strip(); return self._run_tool("file.search", {"query": q}, confirmed)
            if re.search(r"\b(remember|save this|remember that)\b", low):
                mem = load("memory.json", []); mem.append({"text": t, "source": "user", "type": "non-sensitive", "saved": datetime.now().isoformat(timespec="seconds")}); save("memory.json", mem[-200:]); log(t, "memory", "Saved local memory", "success")
                return {"state": "completed", "tool": "memory.save", "message": "Saved that as local non-sensitive memory.", "verified": True}
            self._set_phase("thinking", "Generating response")
            reply = self.llm.chat(t, memory=self._memory_context())
            result = {"state": "speaking", "tool": "llm.chat", "message": reply, "verified": True}
            self._set_phase("speaking", reply); return result
        except Exception as exc:
            log(t, "orchestrator", str(exc), "failed"); self._set_phase("error", str(exc))
            return {"state": "failed", "tool": "orchestrator", "message": str(exc), "verified": False}

    def _run_tool(self, name: str, args: dict, confirmed: bool):
        self._set_phase("executing", f"Executing {name}")
        result = execute(name, args, confirmed=confirmed)
        if result.get("state") == "completed":
            result.setdefault("verified", True)
            self._set_phase("speaking", result.get("message", "Task completed"))
        elif result.get("state") == "confirmation_required":
            self._set_phase("waiting_confirmation", result.get("message", "Confirmation required"))
        else:
            result.setdefault("verified", False); self._set_phase("error", result.get("message", "Task failed"))
        return result

    @staticmethod
    def _system_message(d):
        parts = [f"CPU {d['cpu']:.0f}%", f"RAM {d['memory']:.0f}%", f"Disk {d['disk']:.0f}%"]
        if d.get('gpu') is not None: parts.append(f"GPU {d['gpu']:.0f}%")
        if d.get('battery') is not None: parts.append(f"Battery {d['battery']:.0f}%")
        return "System status: " + " · ".join(parts)
