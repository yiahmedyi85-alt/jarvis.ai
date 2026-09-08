from __future__ import annotations
import os, sys, threading

HOST = "127.0.0.1"
PORT = int(os.getenv("JARVIS_PORT", "8765"))


def main():
    import uvicorn
    from jarvis_local.api import create_app
    threading.Thread(
        target=lambda: uvicorn.run(create_app(), host=HOST, port=PORT, log_level="warning"),
        daemon=True,
    ).start()
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    app = QApplication(sys.argv)
    view = QWebEngineView()
    view.setWindowTitle("JARVIS")
    view.resize(1540, 930)
    view.load(QUrl(f"http://{HOST}:{PORT}/"))
    view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
