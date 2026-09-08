from __future__ import annotations
import os, sys, threading
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
    server=threading.Thread(
        target=lambda:uvicorn.run(create_app(),host=HOST,port=PORT,log_level="warning"),
        daemon=True,
    )
    server.start()

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QUrl
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    app=QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    view=QWebEngineView()

    # Qt WebEngine does not automatically grant microphone access to embedded pages.
    # Grant audio capture for our local JARVIS page so the Voice button can use getUserMedia().
    page=view.page()
    try:
        from PyQt6.QtWebEngineCore import QWebEnginePermission

        def _permission_requested(permission):
            try:
                if permission.permissionType() == QWebEnginePermission.PermissionType.MediaAudioCapture:
                    permission.grant()
            except Exception:
                pass

        page.permissionRequested.connect(_permission_requested)
    except (ImportError, AttributeError):
        # Compatibility with older Qt 6 versions.
        try:
            from PyQt6.QtWebEngineCore import QWebEnginePage

            def _legacy_permission(origin, feature):
                if feature == QWebEnginePage.Feature.MediaAudioCapture:
                    page.setFeaturePermission(
                        origin,
                        feature,
                        QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
                    )

            page.featurePermissionRequested.connect(_legacy_permission)
        except (ImportError, AttributeError):
            pass

    view.setWindowTitle("JARVIS — Local AI Assistant")
    view.resize(1540,930)
    view.setMinimumSize(900,650)
    view.load(QUrl(f"http://{HOST}:{PORT}/"))
    view.show()
    sys.exit(app.exec())


if __name__=="__main__":
    main()
