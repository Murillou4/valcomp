from __future__ import annotations

import sys
from importlib.resources import files
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ares_backend.companion import DEFAULT_BACKEND_URL, build_riot_payload, submit_link


class DetectThread(QThread):
    detected = Signal(dict)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.detected.emit(build_riot_payload())
        except Exception as exc:
            self.failed.emit(str(exc))


class LinkThread(QThread):
    linked = Signal(dict)
    failed = Signal(str)

    def __init__(self, backend_url: str, link_code: str, riot_payload: dict[str, Any]) -> None:
        super().__init__()
        self.backend_url = backend_url
        self.link_code = link_code
        self.riot_payload = riot_payload

    def run(self) -> None:
        try:
            self.linked.emit(submit_link(self.backend_url, self.link_code, self.riot_payload))
        except Exception as exc:
            self.failed.emit(str(exc))


class ValcompCompanionWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._riot_payload: dict[str, Any] | None = None
        self._detect_thread: DetectThread | None = None
        self._link_thread: LinkThread | None = None

        self.setWindowTitle("Valcomp Companion")
        self.setMinimumSize(760, 520)
        self.setObjectName("RootWindow")

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        page = QHBoxLayout(root)
        page.setContentsMargins(28, 28, 28, 28)
        page.setSpacing(22)

        visual = QFrame()
        visual.setObjectName("VisualPanel")
        visual.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        visual_layout = QVBoxLayout(visual)
        visual_layout.setContentsMargins(28, 28, 28, 28)
        visual_layout.setSpacing(18)

        self.logo = QLabel()
        self.logo.setPixmap(load_asset_pixmap("logo.png").scaledToWidth(150, Qt.TransformationMode.SmoothTransformation))
        visual_layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignLeft)

        visual_layout.addStretch(1)
        gun = QLabel()
        gun.setObjectName("GunPreview")
        gun.setPixmap(load_asset_pixmap("store-gun.png").scaled(360, 128, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
        gun.setMinimumHeight(128)
        gun.setAlignment(Qt.AlignmentFlag.AlignCenter)
        visual_layout.addWidget(gun)

        headline = QLabel("Conecte sua conta Riot ao Valcomp")
        headline.setObjectName("HeroTitle")
        headline.setWordWrap(True)
        visual_layout.addWidget(headline)

        copy = QLabel(
            "O app detecta o Riot Client aberto neste PC, pega a sessao local e envia "
            "para o backend usando o codigo unico do mobile."
        )
        copy.setObjectName("HeroCopy")
        copy.setWordWrap(True)
        visual_layout.addWidget(copy)
        visual_layout.addStretch(1)

        form = QFrame()
        form.setObjectName("FormPanel")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(28, 28, 28, 28)
        form_layout.setSpacing(16)

        label = QLabel("Valcomp Companion")
        label.setObjectName("Eyebrow")
        form_layout.addWidget(label)

        title = QLabel("Vinculo rapido")
        title.setObjectName("PanelTitle")
        form_layout.addWidget(title)

        description = QLabel(
            "Abra o VALORANT/Riot Client, gere o codigo no app mobile e cole aqui. "
            "Depois disso voce pode fechar esta janela."
        )
        description.setObjectName("Body")
        description.setWordWrap(True)
        form_layout.addWidget(description)

        self.status = QLabel("Detectando sessao Riot...")
        self.status.setObjectName("StatusNeutral")
        self.status.setWordWrap(True)
        form_layout.addWidget(self.status)

        self.backend_input = QLineEdit(DEFAULT_BACKEND_URL)
        self.backend_input.setObjectName("Input")
        self.backend_input.setPlaceholderText("https://seu-backend.fly.dev")
        form_layout.addWidget(field_block("Backend", self.backend_input))

        self.code_input = QLineEdit()
        self.code_input.setObjectName("CodeInput")
        self.code_input.setInputMask("999999")
        self.code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_input.setPlaceholderText("000000")
        self.code_input.textChanged.connect(self._sync_buttons)
        form_layout.addWidget(field_block("Codigo do app mobile", self.code_input))

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.detect_button = QPushButton("Detectar de novo")
        self.detect_button.setObjectName("SecondaryButton")
        self.detect_button.clicked.connect(self.detect_session)
        buttons.addWidget(self.detect_button)

        self.link_button = QPushButton("Vincular agora")
        self.link_button.setObjectName("PrimaryButton")
        self.link_button.clicked.connect(self.link_account)
        buttons.addWidget(self.link_button)
        form_layout.addLayout(buttons)

        hint = QLabel("Nenhum token ou cookie e mostrado na tela ou salvo pelo companion.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        form_layout.addWidget(hint)
        form_layout.addStretch(1)

        page.addWidget(visual, 1)
        page.addWidget(form, 1)

        self.setStyleSheet(STYLESHEET)
        self._sync_buttons()
        QTimer.singleShot(250, self.detect_session)

    def detect_session(self) -> None:
        if self._detect_thread and self._detect_thread.isRunning():
            return
        self._riot_payload = None
        self.status.setText("Detectando Riot Client e sessao local...")
        self.status.setObjectName("StatusNeutral")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.detect_button.setEnabled(False)
        self.link_button.setEnabled(False)
        self._detect_thread = DetectThread()
        self._detect_thread.detected.connect(self._on_detected)
        self._detect_thread.failed.connect(self._on_detect_failed)
        self._detect_thread.finished.connect(lambda: self.detect_button.setEnabled(True))
        self._detect_thread.start()

    def _on_detected(self, payload: dict[str, Any]) -> None:
        self._riot_payload = payload
        puuid = str(payload.get("puuid") or "")
        region = str(payload.get("region") or "?").upper()
        shard = str(payload.get("shard") or "?").upper()
        has_ssid = bool(payload.get("ssid"))
        suffix = "SSID ok" if has_ssid else "SSID nao encontrado"
        self.status.setText(f"Sessao detectada: {mask_puuid(puuid)} | {region}/{shard} | {suffix}.")
        self.status.setObjectName("StatusSuccess" if has_ssid else "StatusWarning")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self._sync_buttons()

    def _on_detect_failed(self, message: str) -> None:
        self.status.setText(
            "Nao consegui detectar a sessao. Abra o Riot Client e o VALORANT, "
            f"depois tente de novo. Detalhe: {message}"
        )
        self.status.setObjectName("StatusWarning")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self._sync_buttons()

    def link_account(self) -> None:
        if not self._riot_payload:
            self.detect_session()
            return
        code = self.code_input.text().strip()
        if len(code) != 6:
            self.status.setText("Cole o codigo de 6 digitos que apareceu no app mobile.")
            self.status.setObjectName("StatusWarning")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            return
        self.link_button.setEnabled(False)
        self.detect_button.setEnabled(False)
        self.status.setText("Enviando vinculo para o backend...")
        self.status.setObjectName("StatusNeutral")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self._link_thread = LinkThread(self.backend_input.text().strip(), code, self._riot_payload)
        self._link_thread.linked.connect(self._on_linked)
        self._link_thread.failed.connect(self._on_link_failed)
        self._link_thread.finished.connect(self._sync_buttons)
        self._link_thread.start()

    def _on_linked(self, result: dict[str, Any]) -> None:
        account = result.get("riot_account", {})
        name = account.get("game_name") or "conta Riot"
        tag = account.get("tag_line")
        self.status.setText(f"Vinculo concluido para {name}{('#' + tag) if tag else ''}. Pode fechar.")
        self.status.setObjectName("StatusSuccess")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _on_link_failed(self, message: str) -> None:
        self.status.setText(f"Falha ao vincular: {message}")
        self.status.setObjectName("StatusWarning")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _sync_buttons(self) -> None:
        code_ready = len(self.code_input.text().strip()) == 6
        self.link_button.setEnabled(bool(self._riot_payload) and code_ready)
        if not (self._detect_thread and self._detect_thread.isRunning()):
            self.detect_button.setEnabled(True)


def field_block(title: str, widget: QWidget) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(7)
    label = QLabel(title)
    label.setObjectName("FieldLabel")
    layout.addWidget(label)
    layout.addWidget(widget)
    return wrapper


def load_asset_pixmap(name: str) -> QPixmap:
    path = files("valcomp_companion").joinpath("assets", name)
    return QPixmap(str(path))


def mask_puuid(puuid: str) -> str:
    if len(puuid) < 12:
        return "PUUID detectado" if puuid else "PUUID ausente"
    return f"{puuid[:6]}...{puuid[-4:]}"


STYLESHEET = """
QMainWindow#RootWindow, QWidget#Root {
    background: #0B0911;
    color: #F8F1FF;
    font-family: "Segoe UI", "Arial";
}
QFrame#VisualPanel {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #211338, stop:0.54 #100D1A, stop:1 #321723);
    border: 1px solid #3C2B55;
    border-radius: 30px;
}
QFrame#FormPanel {
    background: #171221;
    border: 1px solid #38264D;
    border-radius: 30px;
}
QLabel#HeroTitle {
    color: #F8F1FF;
    font-size: 34px;
    line-height: 38px;
    font-weight: 800;
}
QLabel#HeroCopy, QLabel#Body, QLabel#Hint {
    color: #B8A9C8;
    font-size: 14px;
    line-height: 20px;
}
QLabel#Eyebrow {
    color: #FF4655;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 1.4px;
    text-transform: uppercase;
}
QLabel#PanelTitle {
    color: #F8F1FF;
    font-size: 30px;
    font-weight: 800;
}
QLabel#FieldLabel {
    color: #F8F1FF;
    font-size: 13px;
    font-weight: 700;
}
QLabel#StatusNeutral, QLabel#StatusSuccess, QLabel#StatusWarning {
    border-radius: 16px;
    padding: 12px 14px;
    font-weight: 700;
}
QLabel#StatusNeutral {
    color: #B8A9C8;
    background: #21182F;
    border: 1px solid #38264D;
}
QLabel#StatusSuccess {
    color: #7DDBA9;
    background: #10251D;
    border: 1px solid #2B7A54;
}
QLabel#StatusWarning {
    color: #D59B4C;
    background: #2B1E12;
    border: 1px solid #79521E;
}
QLineEdit#Input, QLineEdit#CodeInput {
    background: #0F0C17;
    color: #F8F1FF;
    border: 1px solid #38264D;
    border-radius: 16px;
    padding: 12px 14px;
    selection-background-color: #FF4655;
}
QLineEdit#Input:focus, QLineEdit#CodeInput:focus {
    border: 1px solid #FF4655;
}
QLineEdit#CodeInput {
    font-size: 30px;
    font-weight: 900;
    letter-spacing: 10px;
}
QPushButton#PrimaryButton, QPushButton#SecondaryButton {
    border: 0;
    border-radius: 16px;
    min-height: 48px;
    padding: 0 18px;
    font-weight: 800;
}
QPushButton#PrimaryButton {
    background: #FF4655;
    color: #FFFFFF;
}
QPushButton#SecondaryButton {
    background: #251A33;
    color: #F8F1FF;
}
QPushButton#PrimaryButton:pressed, QPushButton#SecondaryButton:pressed {
    padding-top: 2px;
}
QPushButton#PrimaryButton:disabled, QPushButton#SecondaryButton:disabled {
    background: #21182F;
    color: #6F627F;
}
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Valcomp Companion")
    window = ValcompCompanionWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

