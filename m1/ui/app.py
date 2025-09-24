"""Minimal PyQt5 shell for the desktop client."""
from __future__ import annotations

from pathlib import Path

from PyQt5 import QtWidgets

from ..config import Config


class MinuteOneWindow(QtWidgets.QMainWindow):
    """Very small main window placeholder."""

    def __init__(self, config: Config, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("MinuteOne")
        self.resize(900, 600)
        self._setup_ui()

    def _setup_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)
        label = QtWidgets.QLabel(
            "MinuteOne UI placeholder\n\nConsent required before export. Use the Export menu to generate PDF/RTF outputs.",
            central,
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        export_button = QtWidgets.QPushButton("Export Note", central)
        export_button.setToolTip("Triggers Export flow once patient consent is recorded.")
        layout.addWidget(export_button)
        consent_checkbox = QtWidgets.QCheckBox("Consent obtained", central)
        layout.addWidget(consent_checkbox)
        self.setCentralWidget(central)


def run() -> None:
    import sys

    app = QtWidgets.QApplication(sys.argv)
    config = Config.load()
    window = MinuteOneWindow(config)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":  # pragma: no cover
    run()
