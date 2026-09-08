from __future__ import annotations
import os, sys, threading, time
from pathlib import Path

BASE=Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE/".env", override=True)
except Exception:
    pass
HOST="127.0.0.1"
PORT=int(os.getenv("JARVIS_PORT","8765"))


def main():
    import uvicorn
    from jarvis_local.api import create_app
    server=threading.Thread(target=lambda:uvicorn.run(create_app(),host=HOST,port=PORT,log_level="warning"),daemon=True)
    server.start()

    from PyQt6.QtCore import QUrl, QObject, pyqtSignal, QTimer, Qt, QPoint
    from PyQt6.QtGui import QPainter, QBrush, QPen, QFont, QIcon, QAction
    from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget, QLabel, QHBoxLayout
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePermission

    class HotkeyBridge(QObject):
        toggle=pyqtSignal()

    class Notch(QWidget):
        def __init__(self):
            super().__init__(None)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.Tool|Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.resize(420,86)
            self.state="idle"
            self.label=QLabel("JARVIS",self); self.label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.label.setStyleSheet("color:#dffaff;font-size:14px;font-weight:600;letter-spacing:3px;")
            self.layout=QHBoxLayout(self); self.layout.setContentsMargins(18,12,18,12); self.layout.addWidget(self.label)
            self.phase=0; self.timer=QTimer(self); self.timer.timeout.connect(self.update); self.timer.start(70); self.hide()
        def set_state(self,state): self.state=str(state or "idle").lower(); self.label.setText({"listening":"LISTENING","user_speaking":"LISTENING","speaking":"JARVIS","error":"ERROR"}.get(self.state,"JARVIS"))
        def paintEvent(self,e):
            p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r=self.rect().adjusted(1,1,-1,-1); p.setBrush(QBrush(0x071923)); p.setPen(QPen(0x19bce8,2)); p.drawRoundedRect(r,38,38)
            cx=self.width()//2; base=self.height()//2+1; p.setPen(QPen(0x22dfff,3))
            for i in range(19):
                x=cx-90+i*10; wave=4
                if self.state in {"listening","user_speaking","speaking"}: wave=8+int(13*(1+__import__('math').sin(self.phase*0.25+i*0.8))/2)
                p.drawLine(x,base-wave,x,base+wave)
            self.phase+=1

    class MainWindow(QWebEngineView):
        def __init__(self, notch): self.notch=notch; super().__init__()
        def closeEvent(self,event): event.ignore(); self.hide(); self.notch.show_notch();

    app=QApplication(sys.argv); app.setApplicationName("JARVIS"); app.setQuitOnLastWindowClosed(False)
    view=None
    notch=Notch()
    def center_notch():
        screen=app.primaryScreen().availableGeometry(); notch.move(screen.x()+(screen.width()-notch.width())//2, screen.y()+8)
    def show_notch(): center_notch(); notch.show(); notch.raise_(); notch.activateWindow()
    def hide_notch(): notch.hide()
    notch.show_notch=show_notch

    view=MainWindow(notch)
    try:
        page=view.page()
        def permission_requested(permission):
            try:
                if permission.permissionType()==QWebEnginePermission.PermissionType.MediaAudioCapture: permission.grant()
            except Exception: pass
        page.permissionRequested.connect(permission_requested)
    except Exception:
        pass

    view.setWindowTitle("JARVIS — Local AI Assistant"); view.resize(1540,930); view.setMinimumSize(900,650); view.load(QUrl(f"http://{HOST}:{PORT}/")); view.show()

    icon=QIcon(str(BASE/"jarvis.ico")) if (BASE/"jarvis.ico").exists() else QIcon()
    tray=QSystemTrayIcon(icon,app); tray.setToolTip("JARVIS")
    menu=QMenu(); open_action=QAction("Open JARVIS",menu); notch_action=QAction("Show JARVIS",menu); exit_action=QAction("Exit",menu)
    menu.addAction(open_action); menu.addAction(notch_action); menu.addSeparator(); menu.addAction(exit_action); tray.setContextMenu(menu); tray.show()
    open_action.triggered.connect(lambda: (view.showNormal(),view.raise_(),view.activateWindow()))
    notch_action.triggered.connect(show_notch)
    def quit_all(): tray.hide(); app.quit()
    exit_action.triggered.connect(quit_all)

    bridge=HotkeyBridge(); bridge.toggle.connect(lambda: (show_notch(), view.page().runJavaScript("document.getElementById('mic')?.click();")))
    def hotkey_loop():
        if sys.platform!="win32": return
        import ctypes
        last=False
        while True:
            ctrl=bool(ctypes.windll.user32.GetAsyncKeyState(0x11)&0x8000)
            space=bool(ctypes.windll.user32.GetAsyncKeyState(0x20)&0x8000)
            down=ctrl and space
            if down and not last: bridge.toggle.emit()
            last=down; time.sleep(0.06)
    threading.Thread(target=hotkey_loop,daemon=True).start()

    def poll_state():
        try:
            from jarvis_local.desktop_events import get_state
            s=get_state(); notch.set_state(s.get("voice","idle"))
        except Exception: pass
    state_timer=QTimer(); state_timer.timeout.connect(poll_state); state_timer.start(120)
    sys.exit(app.exec())

if __name__=="__main__": main()
