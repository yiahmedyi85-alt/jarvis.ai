from __future__ import annotations

import ctypes
import platform
import threading
import time
from typing import Callable

CALL_WORDS = (
    "incoming call", "incoming audio call", "incoming video call", "is calling",
    "calling you", "ringing", "incoming", "call from", "video call",
)
APP_WORDS = ("whatsapp", "telegram", "discord", "teams", "zoom", "skype", "meet")


def active_window_title() -> str:
    if platform.system() != "Windows":
        return ""
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(max(1, n + 1))
    user32.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value


class CallWatcher:
    def __init__(self, on_call: Callable[[str], None], interval: float = 1.0):
        self.on_call = on_call
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last = ""

    def start(self):
        if platform.system() != "Windows" or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="JARVIS-CallWatcher", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(self.interval):
            title = active_window_title()
            low = title.lower()
            if not title or title == self._last:
                continue
            self._last = title
            if any(w in low for w in CALL_WORDS) and any(a in low for a in APP_WORDS):
                try:
                    self.on_call(title)
                except Exception:
                    pass
