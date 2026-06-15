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
        self.setMinimumSize(480, 620)
        self.resize(520, 680)
        self.setObjectName("RootWindow")

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        page = QVBoxLayout(root)
        page.setContentsMargins(18, 18, 18, 18)
        page.setSpacing(0)

        form = QFrame()
        form.setObjectName("FormPanel")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(26, 24, 26, 24)
        form_layout.setSpacing(14)

        label = QLabel("Valcomp Companion")
        label.setObjectName("Eyebrow")
        form_layout.addWidget(label)

        self.logo = QLabel()
        self.logo.setPixmap(
            load_asset_pixmap("logo.png").scaledToWidth(
                142, Qt.TransformationMode.SmoothTransformation
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

        steps = QFrame()
        steps.setObjectName("StepsPanel")
        steps_layout = QVBoxLayout(steps)
        steps_layout.setContentsMargins(14, 14, 14, 14)
        steps_layout.setSpacing(10)
        steps_layout.addWidget(
            step_row(
                "1",
                "Abra o Riot Client ou o VALORANT",
                "Entre na sua conta Riot neste PC e deixe o cliente aberto.",
            )
        )
        steps_layout.addWidget(
            step_row(
                "2",
                "No celular, toque em Vincular",
                "Gere um codigo de 6 numeros no app Valcomp.",
            )
        )
        steps_layout.addWidget(
            step_row(
                "3",
                "Cole o codigo aqui",
                "Clique em vincular e espere a confirmacao.",
            )
        )
        form_layout.addWidget(steps)

        self.status = QLabel("Detectando sessao Riot...")
        self.status.setObjectName("StatusNeutral")
        self.status.setWordWrap(True)
        form_layout.addWidget(self.status)

        self.code_input = QLineEdit()
        self.code_input.setObjectName("CodeInput")
        self.code_input.setMaxLength(6)
        self.code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_input.setPlaceholderText("123456")
        self.code_input.textChanged.connect(self._sanitize_code)
        self.code_input.textChanged.connect(self._sync_buttons)
        form_layout.addWidget(
            field_block(
                "Codigo que apareceu no app",
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
        page.addWidget(form)

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


def step_row(number: str, title: str, body: str) -> QWidget:
    wrapper = QWidget()
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    badge = QLabel(number)
    badge.setObjectName("StepBadge")
    badge.setFixedSize(28, 28)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

    text = QWidget()
    text_layout = QVBoxLayout(text)
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("StepTitle")
    body_label = QLabel(body)
    body_label.setObjectName("StepBody")
    body_label.setWordWrap(True)
    text_layout.addWidget(title_label)
    text_layout.addWidget(body_label)
    layout.addWidget(text, 1)
    return wrapper


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
    background: #0B0911;
    color: #F8F1FF;
    font-family: "Segoe UI", "Arial";
}
QFrame#FormPanel {
    background: #171221;
    border: 1px solid #38264D;
    border-radius: 28px;
}
QFrame#StepsPanel {
    background: #100D18;
    border: 1px solid #2F2142;
    border-radius: 18px;
}
QLabel#Body, QLabel#Hint, QLabel#FieldHelper, QLabel#StepBody {
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
    font-size: 29px;
    font-weight: 800;
}
QLabel#FieldLabel {
    color: #F8F1FF;
    font-size: 13px;
    font-weight: 700;
}
QLabel#StepBadge {
    color: #0B0911;
    background: #FF4655;
    border-radius: 14px;
    font-size: 13px;
    font-weight: 900;
}
QLabel#StepTitle {
    color: #F8F1FF;
    font-size: 14px;
    font-weight: 800;
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
    font-size: 28px;
    font-weight: 900;
    letter-spacing: 8px;
}
QPushButton#PrimaryButton, QPushButton#SecondaryButton, QPushButton#LinkButton {
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
