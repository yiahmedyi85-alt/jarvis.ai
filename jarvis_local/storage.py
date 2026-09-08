from __future__ import annotations
import json, os, threading
from pathlib import Path
from datetime import datetime

BASE = Path(os.getenv("JARVIS_DATA_DIR", str(Path.home() / ".jarvis")))
BASE.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()

def _path(name: str) -> Path:
    return BASE / name

def load(name: str, default):
    with LOCK:
        try:
            return json.loads(_path(name).read_text(encoding="utf-8"))
        except Exception:
            return default

def save(name: str, value) -> None:
    with LOCK:
        p = _path(name)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)

def log(action: str, tool: str, result: str, status: str) -> None:
    rows = load("activity.json", [])
    rows.append({"time": datetime.now().isoformat(timespec="seconds"), "action": action, "tool": tool, "result": result, "status": status})
    save("activity.json", rows[-500:])
