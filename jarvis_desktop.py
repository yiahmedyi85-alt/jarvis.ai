from __future__ import annotations
import os, sys, threading
from pathlib import Path

BASE=Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(BASE/".env")
except Exception:
    pass
HOST="127.0.0.1"
PORT=int(os.getenv("JARVIS_PORT","8765"))

def main():
    import uvicorn
    from jarvis_local.api import create_app
    server=threading.Thread(target=lambda:uvicorn.run(create_app(),host=HOST,port=PORT,log_level="warning"),daemon=True)
    server.start()
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    app=QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    view=QWebEngineView(); view.setWindowTitle("JARVIS — Local AI Assistant"); view.resize(1540,930); view.setMinimumSize(900,650)
    view.load(QUrl(f"http://{HOST}:{PORT}/")); view.show()
    sys.exit(app.exec())

if __name__=="__main__": main()
