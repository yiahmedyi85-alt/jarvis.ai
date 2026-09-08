from __future__ import annotations
import os, platform, subprocess, webbrowser
from pathlib import Path
from urllib.parse import quote_plus
from .storage import log

CONFIRM_REQUIRED = {"file.delete", "system.command", "settings.change", "message.send", "purchase"}


def _win_flags():
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if platform.system() == "Windows" else {}


def open_target(target: str):
    target = target.strip()
    if not target: raise ValueError("Target is empty")
    if target.lower() in {"chrome", "google chrome"}:
        if platform.system() == "Windows": subprocess.Popen(["cmd", "/c", "start", "", "chrome"], **_win_flags())
        else: webbrowser.open("https://google.com")
        return "Chrome launch requested."
    if target.lower() in {"spotify"}:
        if platform.system() == "Windows": subprocess.Popen(["cmd", "/c", "start", "", "spotify:"], **_win_flags())
        else: webbrowser.open("https://open.spotify.com")
        return "Spotify launch requested."
    p = Path(target).expanduser()
    if p.exists():
        if platform.system() == "Windows": os.startfile(str(p))
        elif platform.system() == "Darwin": subprocess.Popen(["open", str(p)])
        else: subprocess.Popen(["xdg-open", str(p)])
        return f"Opened {p}"
    if platform.system() == "Windows":
        subprocess.Popen(["cmd", "/c", "start", "", target], **_win_flags())
    else:
        webbrowser.open(target if "://" in target else "https://" + target)
    return f"Launch requested: {target}"


def open_downloads():
    return open_target(str(Path.home() / "Downloads"))


def open_url(url: str):
    if not url.startswith(("http://", "https://")): url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url}"


def web_search(query: str):
    if not query.strip(): raise ValueError("Search query is empty")
    url = "https://www.google.com/search?q=" + quote_plus(query)
    webbrowser.open(url)
    return f"Opened web search for: {query}"


def create_folder(path: str):
    p = Path(path).expanduser(); p.mkdir(parents=True, exist_ok=False)
    return f"Created folder {p}"


def create_file(path: str, content: str = ""):
    p = Path(path).expanduser(); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8", errors="strict")
    return f"Created file {p}"


def delete_file(path: str):
    p = Path(path).expanduser()
    if not p.exists(): raise FileNotFoundError(str(p))
    if p.is_dir(): raise IsADirectoryError("Directory deletion is not enabled by this tool")
    p.unlink()
    return f"Deleted file {p}"


def list_files(path: str | None = None):
    p = Path(path or Path.home() / "Downloads").expanduser()
    if not p.exists(): raise FileNotFoundError(str(p))
    return [{"name": x.name, "type": "folder" if x.is_dir() else "file", "path": str(x)} for x in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:200]]


def search_files(query: str, root: str | None = None):
    q = query.lower().strip()
    base = Path(root or Path.home()).expanduser()
    if not q: raise ValueError("File search query is empty")
    results=[]
    for p in base.rglob("*"):
        if q in p.name.lower():
            results.append(str(p))
            if len(results) >= 100: break
    return results


def system_command(command: str):
    raise PermissionError("Arbitrary terminal commands are disabled. Add an explicit allowlisted command before enabling this tool.")


def execute(tool: str, args: dict, confirmed: bool = False):
    if tool in CONFIRM_REQUIRED and not confirmed:
        return {"state": "confirmation_required", "tool": tool, "args": args, "message": "This action requires confirmation."}
    fn = {"app.open": open_target, "folder.open": open_target, "folder.downloads": lambda **_: open_downloads(),
          "web.search": web_search, "browser.open": open_url, "file.create_folder": create_folder,
          "file.create": create_file, "file.delete": delete_file, "file.list": list_files,
          "file.search": search_files, "system.command": system_command}.get(tool)
    if fn is None: raise ValueError(f"Unknown tool: {tool}")
    result = fn(**args)
    log(tool, tool, str(result), "success")
    return {"state": "completed", "tool": tool, "message": result}
