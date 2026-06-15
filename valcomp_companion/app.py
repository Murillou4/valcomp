from __future__ import annotations

import sys
from importlib.resources import files
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QIntValidator, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
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
        self._syncing_code = False

        self.setWindowTitle("Valcomp Companion")
        self.setMinimumSize(560, 660)
        self.resize(620, 700)
        self.setObjectName("RootWindow")

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)

        form = QFrame()
        form.setObjectName("FormPanel")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(34, 28, 34, 28)
        form_layout.setSpacing(10)
        page.addWidget(form)

        label = QLabel("Valcomp Companion")
        label.setObjectName("Eyebrow")
        form_layout.addWidget(label)

        self.logo = QLabel()
        self.logo.setPixmap(
            load_asset_pixmap("logo.png").scaledToWidth(
                92, Qt.TransformationMode.SmoothTransformation
            )
        )
        form_layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignLeft)

        title = QLabel("Vincular sua conta Riot")
        title.setObjectName("PanelTitle")
        form_layout.addWidget(title)

        description = QLabel(
            "Use esta janela uma vez no computador onde voce ja joga VALORANT. "
            "Ela conecta sua sessao Riot ao app Valcomp do celular."
        )
        description.setObjectName("Body")
        description.setWordWrap(True)
        form_layout.addWidget(description)

        form_layout.addWidget(
            instruction_card(
                [
                    "1. Abra o Riot Client ou VALORANT e deixe sua conta logada.",
                    "2. No celular, abra o Valcomp e toque em Vincular.",
                    "3. Gere o codigo de 6 numeros e digite aqui.",
                ]
            )
        )

        self.status = QLabel("Detectando sessao Riot...")
        self.status.setObjectName("StatusNeutral")
        self.status.setWordWrap(True)
        form_layout.addWidget(self.status)

        self.code_input = QLineEdit()
        self.code_input.setObjectName("CodeInput")
        self.code_input.setMaxLength(6)
        self.code_input.setValidator(QIntValidator(0, 999999, self))
        self.code_input.setFixedHeight(64)
        self.code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_input.setPlaceholderText("000000")
        code_font = QFont("Segoe UI", 25)
        code_font.setBold(True)
        self.code_input.setFont(code_font)
        self.code_input.textChanged.connect(self._sanitize_code)
        self.code_input.textChanged.connect(self._sync_buttons)
        form_layout.addWidget(
            field_block(
                "DIGITE O CODIGO AQUI",
                self.code_input,
                "No celular: aba Vincular > Gerar codigo de vinculo.",
            )
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.detect_button = QPushButton("Detectar Riot")
        self.detect_button.setObjectName("SecondaryButton")
        self.detect_button.clicked.connect(self.detect_session)
        buttons.addWidget(self.detect_button)

        self.link_button = QPushButton("Vincular minha conta")
        self.link_button.setObjectName("PrimaryButton")
        self.link_button.clicked.connect(self.link_account)
        buttons.addWidget(self.link_button)
        form_layout.addLayout(buttons)

        self.advanced_button = QPushButton("Mostrar configuracao avancada")
        self.advanced_button.setObjectName("LinkButton")
        self.advanced_button.clicked.connect(self._toggle_advanced)
        form_layout.addWidget(self.advanced_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.backend_input = QLineEdit(DEFAULT_BACKEND_URL)
        self.backend_input.setObjectName("Input")
        self.backend_input.setFixedHeight(48)
        self.backend_input.setPlaceholderText("https://valcomp-api-cda2.fly.dev")
        self.backend_wrapper = field_block(
            "Servidor Valcomp",
            self.backend_input,
            "Nao altere este campo, a menos que esteja testando uma versao propria.",
        )
        self.backend_wrapper.hide()
        form_layout.addWidget(self.backend_wrapper)

        hint = QLabel(
            "Seguro: nenhum token, cookie ou senha Riot aparece na tela ou fica salvo neste app."
        )
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        form_layout.addWidget(hint)

        self.setStyleSheet(STYLESHEET)
        self._sync_buttons()
        QTimer.singleShot(250, self.detect_session)

    def detect_session(self) -> None:
        if self._detect_thread and self._detect_thread.isRunning():
            return
        self._riot_payload = None
        self.status.setText("Procurando Riot Client aberto neste PC...")
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
        suffix = "pronta para vincular" if has_ssid else "detectada, mas pode pedir novo login"
        self.status.setText(
            f"Conta Riot encontrada: {mask_puuid(puuid)} | {region}/{shard}. "
            f"Sessao {suffix}."
        )
        self.status.setObjectName("StatusSuccess" if has_ssid else "StatusWarning")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self._sync_buttons()

    def _on_detect_failed(self, message: str) -> None:
        self.status.setText(
            "Nao encontrei sua sessao Riot. Abra o Riot Client ou VALORANT, confirme "
            "que esta logado e clique em Detectar Riot novamente."
        )
        self.status.setToolTip(message)
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
            self.status.setText("Digite os 6 numeros que apareceram no app Valcomp do celular.")
            self.status.setObjectName("StatusWarning")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            return
        self.link_button.setEnabled(False)
        self.detect_button.setEnabled(False)
        self.status.setText("Conectando sua conta Riot ao Valcomp...")
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
        self.status.setText(
            "Nao foi possivel vincular. Gere um novo codigo no app e tente de novo. "
            "Se continuar, confira sua internet."
        )
        self.status.setToolTip(message)
        self.status.setObjectName("StatusWarning")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _sync_buttons(self) -> None:
        code_ready = len(self.code_input.text().strip()) == 6
        self.link_button.setEnabled(bool(self._riot_payload) and code_ready)
        if not (self._detect_thread and self._detect_thread.isRunning()):
            self.detect_button.setEnabled(True)

    def _sanitize_code(self, value: str) -> None:
        if self._syncing_code:
            return
        clean = "".join(ch for ch in value if ch.isdigit())[:6]
        if clean == value:
            return
        self._syncing_code = True
        self.code_input.setText(clean)
        self._syncing_code = False

    def _toggle_advanced(self) -> None:
        visible = not self.backend_wrapper.isVisible()
        self.backend_wrapper.setVisible(visible)
        self.advanced_button.setText(
            "Ocultar configuracao avancada"
            if visible
            else "Mostrar configuracao avancada"
        )


def instruction_card(lines: list[str]) -> QWidget:
    frame = QFrame()
    frame.setObjectName("InstructionsPanel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(7)
    for line in lines:
        label = QLabel(line)
        label.setObjectName("InstructionLine")
        label.setWordWrap(True)
        layout.addWidget(label)
    return frame


def field_block(title: str, widget: QWidget, helper: str = "") -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    label = QLabel(title)
    label.setObjectName("FieldLabel")
    layout.addWidget(label)
    layout.addWidget(widget)
    if helper:
        helper_label = QLabel(helper)
        helper_label.setObjectName("FieldHelper")
        helper_label.setWordWrap(True)
        layout.addWidget(helper_label)
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
    background: #171221;
    color: #F8F1FF;
    font-family: "Segoe UI", "Arial";
}
QFrame#FormPanel {
    background: #171221;
    border: 0;
    border-radius: 0;
}
QFrame#InstructionsPanel {
    background: #100D18;
    border: 1px solid #2F2142;
    border-radius: 16px;
}
QLabel#InstructionLine {
    color: #F8F1FF;
    font-size: 14px;
    font-weight: 700;
}
QLabel#Body, QLabel#Hint, QLabel#FieldHelper {
    color: #B8A9C8;
    font-size: 13px;
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
    border-radius: 14px;
    padding: 10px 12px;
    font-weight: 700;
    font-size: 13px;
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
    border-radius: 14px;
    padding: 0 14px;
    selection-background-color: #FF4655;
}
QLineEdit#Input:focus, QLineEdit#CodeInput:focus {
    border: 1px solid #FF4655;
}
QLineEdit#CodeInput {
    background: #090711;
    border: 2px solid #FF4655;
    border-radius: 18px;
    padding: 0 22px;
}
QPushButton#PrimaryButton, QPushButton#SecondaryButton, QPushButton#LinkButton {
    border: 0;
    border-radius: 14px;
    min-height: 46px;
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
QPushButton#LinkButton {
    background: transparent;
    color: #B8A9C8;
    min-height: 28px;
    padding: 0;
    text-align: left;
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
