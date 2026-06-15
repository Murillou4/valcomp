from __future__ import annotations

import os
import sys
from importlib.resources import files

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .bridge import AppBridge


def main() -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")
    os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_THEME", "Dark")
    os.environ.setdefault("QT_QUICK_CONTROLS_MATERIAL_ACCENT", "#D56A75")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Ares Console")
    app.setOrganizationName("Ares Console")
    app.setFont(QFont("Segoe UI Variable", 10))

    engine = QQmlApplicationEngine()
    bridge = AppBridge()
    engine.rootContext().setContextProperty("bridge", bridge)

    qml_path = files("ares_console").joinpath("resources/qml/Main.qml")
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        bridge.shutdown()
        return 1

    app.aboutToQuit.connect(bridge.shutdown)
    QTimer.singleShot(350, bridge.refreshSession)
    return app.exec()
