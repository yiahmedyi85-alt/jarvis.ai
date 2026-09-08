from __future__ import annotations

import os
import platform
import subprocess
import time
from pathlib import Path

import pyautogui


def _win_hide() -> dict:
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if platform.system() == "Windows" else {}


def lock_computer() -> str:
    if platform.system() == "Windows":
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], **_win_hide())
    elif platform.system() == "Darwin":
        subprocess.Popen(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"])
    else:
        subprocess.Popen(["loginctl", "lock-session"])
    return "Computer locked."


def sleep_computer() -> str:
    if platform.system() == "Windows":
        # Hybrid sleep is not available on every device; suspend is the reliable fallback.
        subprocess.Popen(["powershell", "-NoProfile", "-Command", "Start-Sleep -Milliseconds 300; Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"], **_win_hide())
    elif platform.system() == "Darwin":
        subprocess.Popen(["pmset", "sleepnow"])
    else:
        subprocess.Popen(["systemctl", "suspend"])
    return "Putting the computer to sleep."


def shutdown_computer(delay_seconds: int = 5) -> str:
    delay_seconds = max(0, min(int(delay_seconds), 60))
    if platform.system() == "Windows":
        subprocess.Popen(["shutdown", "/s", "/t", str(delay_seconds)], **_win_hide())
    elif platform.system() == "Darwin":
        subprocess.Popen(["sudo", "shutdown", "-h", f"+{max(1, delay_seconds // 60)}"])
    else:
        subprocess.Popen(["systemctl", "poweroff"])
    return f"Shutdown scheduled in {delay_seconds} seconds."


def cancel_shutdown() -> str:
    if platform.system() == "Windows":
        subprocess.Popen(["shutdown", "/a"], **_win_hide())
    else:
        return "Shutdown cancellation is only implemented for Windows."
    return "Pending shutdown cancelled."


def mouse_move(x: int, y: int, duration: float = 0.15) -> str:
    pyautogui.moveTo(int(x), int(y), duration=max(0.0, min(float(duration), 2.0)))
    return f"Mouse moved to {int(x)}, {int(y)}."


def mouse_click(button: str = "left", clicks: int = 1) -> str:
    button = button.lower().strip()
    if button not in {"left", "right", "middle"}:
        raise ValueError("button must be left, right, or middle")
    pyautogui.click(button=button, clicks=max(1, min(int(clicks), 3)), interval=0.08)
    return f"Mouse {button} click executed."


def keyboard_press(key: str) -> str:
    allowed = {
        "enter", "esc", "escape", "tab", "space", "backspace", "delete",
        "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
        "ctrl", "shift", "alt", "win", "f1", "f2", "f3", "f4", "f5", "f6",
        "f7", "f8", "f9", "f10", "f11", "f12"
    }
    k = key.lower().strip()
    if len(k) == 1 or k in allowed:
        pyautogui.press(k)
        return f"Pressed {key}."
    raise ValueError("Unsupported keyboard key")


def keyboard_hotkey(*keys: str) -> str:
    if not keys or len(keys) > 4:
        raise ValueError("A hotkey must contain 1-4 keys")
    pyautogui.hotkey(*(str(k).lower().strip() for k in keys))
    return "Hotkey executed."


def keyboard_type(text: str, interval: float = 0.01) -> str:
    text = str(text)
    if len(text) > 1000:
        raise ValueError("Typed text is limited to 1000 characters")
    pyautogui.write(text, interval=max(0.0, min(float(interval), 0.05)))
    return "Text typed."
