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

    from PyQt6.QtCore import QUrl, QObject, pyqtSignal, QTimer, Qt, QRectF
    from PyQt6.QtGui import QPainter, QBrush, QPen, QIcon, QAction, QColor
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
            self.setFixedSize(500,92)
            self.state="idle"
            self.label=QLabel("JARVIS",self)
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label.setStyleSheet("color:#dffaff;font-size:13px;font-weight:600;letter-spacing:4px;background:transparent;")
            self.layout=QHBoxLayout(self)
            self.layout.setContentsMargins(32,20,32,20)
            self.layout.addWidget(self.label)
            self.phase=0
            self.timer=QTimer(self)
            self.timer.timeout.connect(self.update)
            self.timer.start(45)
            self.hide()

        def set_state(self,state):
            self.state=str(state or "idle").lower()
            names={"listening":"LISTENING","user_speaking":"LISTENING","speaking":"JARVIS","error":"ERROR"}
            self.label.setText(names.get(self.state,"JARVIS"))
            self.update()

        def paintEvent(self,e):
            p=QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            outer=self.rect().adjusted(2,2,-2,-2)
            p.setBrush(QBrush(QColor(4,14,24,245)))
            p.setPen(QPen(QColor(35,224,255,220),2))
            p.drawRoundedRect(QRectF(outer),44,44)
            glow=QColor(0,202,255,35)
            p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(self.width()/2-28,self.height()/2-28,56,56))
            base=self.height()/2+1; cx=self.width()/2
            active=self.state in {"listening","user_speaking","speaking"}
            for i in range(25):
                x=cx-120+i*10
                amp=3
                if active:
                    import math
                    amp=7+int(15*(1+math.sin(self.phase*.30+i*.7))/2)
                p.setPen(QPen(QColor(50,231,255,230),2))
                p.drawLine(int(x),int(base-amp),int(x),int(base+amp))
            self.phase+=1

    class MainWindow(QWebEngineView):
        def __init__(self, notch):
            self.notch=notch
            super().__init__()
        def closeEvent(self,event):
            event.ignore(); self.hide(); self.notch.show_notch()

    app=QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setQuitOnLastWindowClosed(False)
    notch=Notch()

    def center_notch():
        screen=app.primaryScreen().availableGeometry()
        notch.move(screen.x()+(screen.width()-notch.width())//2,screen.y()+6)

    def show_notch():
        center_notch(); notch.show(); notch.raise_(); notch.activateWindow()

    def hide_notch(): notch.hide()
    notch.show_notch=show_notch

    view=MainWindow(notch)
    try:
        page=view.page()
        def permission_requested(permission):
            try:
                if permission.permissionType()==QWebEnginePermission.PermissionType.MediaAudioCapture:
                    permission.grant()
            except Exception:
                pass
        page.permissionRequested.connect(permission_requested)
    except Exception:
        pass

    view.setWindowTitle("JARVIS — Local AI Assistant")
    view.resize(1540,930)
    view.setMinimumSize(900,650)
    view.load(QUrl(f"http://{HOST}:{PORT}/"))
    view.show()

    icon=QIcon(str(BASE/"jarvis.ico")) if (BASE/"jarvis.ico").exists() else QIcon()
    tray=QSystemTrayIcon(icon,app)
    tray.setToolTip("JARVIS")
    menu=QMenu()
    open_action=QAction("Open JARVIS",menu)
    notch_action=QAction("Show JARVIS",menu)
    exit_action=QAction("Exit",menu)
    menu.addAction(open_action); menu.addAction(notch_action); menu.addSeparator(); menu.addAction(exit_action)
    tray.setContextMenu(menu); tray.show()
    open_action.triggered.connect(lambda:(view.showNormal(),view.raise_(),view.activateWindow()))
    notch_action.triggered.connect(show_notch)
    exit_action.triggered.connect(lambda:(tray.hide(),app.quit()))

    bridge=HotkeyBridge()
    bridge.toggle.connect(lambda: (
        show_notch(),
        view.page().runJavaScript("window.JARVIS_WAKE ? window.JARVIS_WAKE() : document.getElementById('mic')?.click();")
    ))

    def hotkey_loop():
        if sys.platform!="win32": return
        import ctypes
        last_ctrl=False
        press_time=0.0
        other_key_seen=False
        VK_LCTRL=0xA2; VK_RCTRL=0xA3
        def other_key_down():
            ranges=[(0x30,0x5A),(0xBA,0xDF),(0x70,0x7B),(0x25,0x28),(0x20,0x20)]
            for a,b in ranges:
                for vk in range(a,b+1):
                    if vk in (VK_LCTRL,VK_RCTRL,0x10,0x11): continue
                    if ctypes.windll.user32.GetAsyncKeyState(vk)&0x8000: return True
            return False
        while True:
            ctrl=bool(ctypes.windll.user32.GetAsyncKeyState(VK_LCTRL)&0x8000 or ctypes.windll.user32.GetAsyncKeyState(VK_RCTRL)&0x8000)
            if ctrl and not last_ctrl:
                press_time=time.monotonic(); other_key_seen=False
            if ctrl and other_key_down(): other_key_seen=True
            if not ctrl and last_ctrl:
                duration=time.monotonic()-press_time
                if duration<0.8 and not other_key_seen:
                    bridge.toggle.emit()
            last_ctrl=ctrl
            time.sleep(0.02)
    threading.Thread(target=hotkey_loop,daemon=True).start()

    def poll_state():
        try:
            from jarvis_local.desktop_events import get_state
            s=get_state(); voice=s.get("voice","idle")
            if voice!="idle": show_notch()
            notch.set_state(voice)
        except Exception: pass
    state_timer=QTimer(); state_timer.timeout.connect(poll_state); state_timer.start(100)
    sys.exit(app.exec())

if __name__=="__main__": main()
