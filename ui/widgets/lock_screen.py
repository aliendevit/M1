# path: ui/widgets/lock_screen.py
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, QTimer, QObject
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QApplication


class LockDialog(QDialog):
    def __init__(self, parent=None, new_passphrase: bool = False):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("M1 — Locked" if not new_passphrase else "M1 — Set Passphrase")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Session is locked due to inactivity." if not new_passphrase else "Set a passphrase to unlock your session."))
        self.ed = QLineEdit(self)
        self.ed.setEchoMode(QLineEdit.Password)
        self.ed.returnPressed.connect(self.accept)
        lay.addWidget(self.ed)
        btns = QHBoxLayout()
        ok = QPushButton("Unlock" if not new_passphrase else "Set")
        ok.clicked.connect(self.accept)
        btns.addStretch(1)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.resize(360, 160)

    def text(self) -> str:
        return self.ed.text().strip()


class IdleLock(QObject):
    """
    Auto-locks the UI after N minutes of inactivity. First lock will prompt to set a passphrase.
    """
    def __init__(self, parent=None, idle_minutes: int = 5):
        super().__init__(parent)
        self._idle_ms = max(1, idle_minutes) * 60 * 1000
        self._timer = QTimer(self)
        self._timer.setInterval(self._idle_ms)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._lock)
        self._passphrase: Optional[str] = None
        self._target = parent

    def install_on(self, app: QApplication):
        app.installEventFilter(self)
        self._timer.start()

    def eventFilter(self, obj, ev):
        # Any key/mouse resets idle timer
        if ev.type() in (ev.MouseMove, ev.MouseButtonPress, ev.KeyPress, ev.Wheel):
            self._timer.start()
        return False

    def _lock(self):
        # First time: set passphrase
        if not self._passphrase:
            dlg = LockDialog(self._target, new_passphrase=True)
            if dlg.exec_() == dlg.Accepted and dlg.text():
                self._passphrase = dlg.text()
            else:
                # require a passphrase to proceed
                return self._lock()
        # Then: lock
        dlg = LockDialog(self._target, new_passphrase=False)
        while True:
            if dlg.exec_() != dlg.Accepted:
                continue
            if dlg.text() == self._passphrase:
                break
        self._timer.start()
