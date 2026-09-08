from __future__ import annotations
import os, platform
from pathlib import Path
NAME="JARVIS Local.lnk"
def startup_folder(): return Path(os.getenv("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
def set_startup(enabled: bool, launcher: str):
    if platform.system() != "Windows": return False, "Automatic Windows startup is only available on Windows."
    folder=startup_folder(); folder.mkdir(parents=True,exist_ok=True); link=folder/NAME
    if not enabled:
        if link.exists(): link.unlink()
        return True,"JARVIS startup disabled."
    try:
        import win32com.client
        shell=win32com.client.Dispatch("WScript.Shell"); shortcut=shell.CreateShortCut(str(link)); shortcut.TargetPath=launcher; shortcut.WorkingDirectory=str(Path(launcher).parent); shortcut.Save()
        return True,"JARVIS startup enabled."
    except Exception as exc: return False,f"Could not configure startup: {exc}"
