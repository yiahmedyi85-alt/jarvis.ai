from __future__ import annotations

import re
import threading
import time
from datetime import datetime
from typing import Callable

from .storage import load, save, log

_LOCK = threading.RLock()
_STOP = threading.Event()
_THREAD: threading.Thread | None = None
_EXECUTOR: Callable[[str, dict, bool], object] | None = None


def _tasks():
    return load("scheduled_tasks.json", [])


def _save(tasks):
    save("scheduled_tasks.json", tasks[-500:])


def add_task(run_at: str, action: str, args: dict | None = None) -> dict:
    try:
        dt = datetime.fromisoformat(run_at)
    except ValueError as exc:
        raise ValueError("run_at must be ISO format, for example 2026-09-08T20:30:00") from exc
    if dt <= datetime.now():
        raise ValueError("Scheduled time must be in the future")
    item = {
        "id": f"task-{time.time_ns()}",
        "run_at": dt.isoformat(timespec="seconds"),
        "action": str(action),
        "args": args or {},
        "done": False,
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    with _LOCK:
        tasks = _tasks(); tasks.append(item); _save(tasks)
    return item


def list_tasks() -> list[dict]:
    return [x for x in _tasks() if not x.get("done")]


def cancel_task(task_id: str) -> bool:
    with _LOCK:
        tasks = _tasks(); changed = False
        for x in tasks:
            if x.get("id") == task_id and not x.get("done"):
                x["done"] = True; x["cancelled"] = True; changed = True
        _save(tasks)
    return changed


def start(executor: Callable[[str, dict, bool], object]) -> None:
    global _THREAD, _EXECUTOR
    _EXECUTOR = executor
    if _THREAD and _THREAD.is_alive(): return
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, name="JARVIS-Scheduler", daemon=True)
    _THREAD.start()


def stop() -> None:
    _STOP.set()


def _loop() -> None:
    while not _STOP.wait(1.0):
        now = datetime.now()
        with _LOCK:
            tasks = _tasks()
            dirty = False
            for item in tasks:
                if item.get("done"): continue
                try: run_at = datetime.fromisoformat(item["run_at"])
                except Exception:
                    item["done"] = True; dirty = True; continue
                if run_at > now: continue
                item["done"] = True; item["ran_at"] = now.isoformat(timespec="seconds"); dirty = True
                try:
                    if _EXECUTOR:
                        result = _EXECUTOR(item["action"], item.get("args") or {}, True)
                        log(f"Scheduled: {item['action']}", "scheduler", str(result), "success")
                    else:
                        log(f"Scheduled: {item['action']}", "scheduler", "No executor", "failed")
                except Exception as exc:
                    log(f"Scheduled: {item['action']}", "scheduler", str(exc), "failed")
            if dirty: _save(tasks)


def parse_time_phrase(text: str) -> datetime | None:
    now = datetime.now()
    m = re.search(r"\bin\s+(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)\b", text, re.I)
    if m:
        n = int(m.group(1)); unit = m.group(2).lower()
        seconds = n * (3600 if unit.startswith("hour") or unit.startswith("hr") else 60)
        return now.fromtimestamp(now.timestamp() + seconds)
    m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text, re.I)
    if not m: return None
    hour = int(m.group(1)); minute = int(m.group(2) or 0); ampm = (m.group(3) or "").lower()
    if ampm:
        if hour == 12: hour = 0
        if ampm == "pm": hour += 12
    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if dt <= now: dt = dt.replace(day=dt.day) + __import__('datetime').timedelta(days=1)
    return dt
