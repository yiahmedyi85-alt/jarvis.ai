from __future__ import annotations

from datetime import datetime
from threading import RLock

_LOCK = RLock()
_STATE = {
    "voice": "idle",
    "message": "",
    "call": None,
    "updated": datetime.now().isoformat(timespec="seconds"),
}


def get_state() -> dict:
    with _LOCK:
        return dict(_STATE)


def set_state(**kwargs) -> dict:
    with _LOCK:
        _STATE.update(kwargs)
        _STATE["updated"] = datetime.now().isoformat(timespec="seconds")
        return dict(_STATE)


def clear_call() -> dict:
    return set_state(call=None)
