# path: ui/widgets/consent_gate.py
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, QHBoxLayout


class ConsentGate(QDialog):
    """
    Shows offline default notice and optional 'Enable online features' toggle (unchecked).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._allow_online = False
        self.setWindowTitle("M1 — Offline by default")
        lay = QVBoxLayout(self)
        msg = QLabel(
            "MinuteOne (M1) runs offline by default.\n"
            "• No telemetry.\n"
            "• No PHI egress.\n\n"
            "You may enable *optional online features* (loopback/local only unless explicitly configured). "
            "This is OFF by default."
        )
        msg.setWordWrap(True)
        lay.addWidget(msg)

        self.chk = QCheckBox("Enable online features (not recommended)")
        self.chk.setChecked(False)
        lay.addWidget(self.chk)

        lay.addWidget(QLabel("Press Continue to proceed."))

        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("Continue")
        ok.clicked.connect(self._accept)
        cancel = QPushButton("Exit")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.resize(460, 260)

    def _accept(self):
        self._allow_online = bool(self.chk.isChecked())
        self.accept()

    def allow_online(self) -> bool:
        return self._allow_online
