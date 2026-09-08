from __future__ import annotations
import os, platform, subprocess, time, webbrowser
from pathlib import Path
from urllib.parse import quote_plus
from .storage import log
from .system_control import lock_computer,sleep_computer,shutdown_computer,cancel_shutdown,mouse_move,mouse_click,keyboard_press,keyboard_hotkey,keyboard_type
from .scheduler import add_task as schedule_add,list_tasks as schedule_list,cancel_task as schedule_cancel

CONFIRM_REQUIRED={"file.delete","system.command","settings.change","message.send","purchase","system.shutdown","system.sleep","file.move","keyboard.type","mouse.click"}
def _win_flags(): return {"creationflags":getattr(subprocess,"CREATE_NO_WINDOW",0)} if platform.system()=="Windows" else {}

def _windows_search_launch(target:str):
    """Launch a desktop app through the normal Windows Start/Search UI."""
    import pyautogui
    name=target.strip()
    if not name: raise ValueError("Application name is empty")
    pyautogui.press("win")
    time.sleep(0.25)
    pyautogui.write(name, interval=0.02)
    time.sleep(0.6)
    pyautogui.press("enter")
    return f"Opened {name} through Windows Search."

def open_target(target:str):
    target=target.strip()
    if not target: raise ValueError("Target is empty")
    low=target.lower()
    if low in {"chrome","google chrome"}:
        if platform.system()=="Windows": subprocess.Popen(["cmd","/c","start","","chrome"],**_win_flags())
        else: webbrowser.open("https://google.com")
        return "Chrome launch requested."
    if low=="spotify":
        if platform.system()=="Windows": subprocess.Popen(["cmd","/c","start","","spotify:"],**_win_flags())
        else: webbrowser.open("https://open.spotify.com")
        return "Spotify launch requested."
    p=Path(target).expanduser()
    if p.exists():
        if platform.system()=="Windows": os.startfile(str(p))
        elif platform.system()=="Darwin": subprocess.Popen(["open",str(p)])
        else: subprocess.Popen(["xdg-open",str(p)])
        return f"Opened {p}"
    if platform.system()=="Windows":
        return _windows_search_launch(target)
    webbrowser.open(target if "://" in target else "https://"+target)
    return f"Launch requested: {target}"

def open_downloads(): return open_target(str(Path.home()/"Downloads"))
def open_url(url:str):
    if not url.startswith(("http://","https://")): url="https://"+url
    webbrowser.open(url); return f"Opened {url}"
def web_search(query:str):
    if not query.strip(): raise ValueError("Search query is empty")
    webbrowser.open("https://www.google.com/search?q="+quote_plus(query)); return f"Opened web search for: {query}"
def create_folder(path:str): p=Path(path).expanduser(); p.mkdir(parents=True,exist_ok=False); return f"Created folder {p}"
def create_file(path:str,content:str=""):
    p=Path(path).expanduser(); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding="utf-8"); return f"Created file {p}"
def delete_file(path:str):
    p=Path(path).expanduser()
    if not p.exists(): raise FileNotFoundError(str(p))
    if p.is_dir(): raise IsADirectoryError("Directory deletion is not enabled")
    p.unlink(); return f"Deleted file {p}"
def list_files(path:str|None=None):
    p=Path(path or Path.home()/"Downloads").expanduser()
    if not p.exists(): raise FileNotFoundError(str(p))
    return [{"name":x.name,"type":"folder" if x.is_dir() else "file","path":str(x)} for x in sorted(p.iterdir(),key=lambda x:(not x.is_dir(),x.name.lower()))[:200]]
def search_files(query:str,root:str|None=None):
    q=query.lower().strip(); base=Path(root or Path.home()).expanduser()
    if not q: raise ValueError("File search query is empty")
    out=[]
    for p in base.rglob("*"):
        if q in p.name.lower(): out.append(str(p))
        if len(out)>=100: break
    return out
def move_file(source:str,destination:str):
    import shutil
    src=Path(source).expanduser(); dst=Path(destination).expanduser()
    if not src.exists(): raise FileNotFoundError(str(src))
    dst.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(src),str(dst)); return f"Moved {src} to {dst}"
def system_command(command:str): raise PermissionError("Arbitrary terminal commands are disabled. Use an explicit system tool.")
def execute(tool:str,args:dict,confirmed:bool=False):
    if tool in CONFIRM_REQUIRED and not confirmed: return {"state":"confirmation_required","tool":tool,"args":args,"message":"This action requires confirmation."}
    fn={"app.open":open_target,"folder.open":open_target,"folder.downloads":lambda **_:open_downloads(),"web.search":web_search,"browser.open":open_url,"file.create_folder":create_folder,"file.create":create_file,"file.delete":delete_file,"file.list":list_files,"file.search":search_files,"file.move":move_file,"system.lock":lambda **_:lock_computer(),"system.sleep":lambda **_:sleep_computer(),"system.shutdown":shutdown_computer,"system.cancel_shutdown":lambda **_:cancel_shutdown(),"mouse.move":mouse_move,"mouse.click":mouse_click,"keyboard.press":keyboard_press,"keyboard.hotkey":keyboard_hotkey,"keyboard.type":keyboard_type,"schedule.add":schedule_add,"schedule.list":lambda **_:schedule_list(),"schedule.cancel":schedule_cancel,"system.command":system_command}.get(tool)
    if fn is None: raise ValueError(f"Unknown tool: {tool}")
    result=fn(**args); log(tool,tool,str(result),"success"); return {"state":"completed","tool":tool,"message":result}