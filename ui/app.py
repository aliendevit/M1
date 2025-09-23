# path: ui/app.py
from __future__ import annotations

import os
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from .widgets.consent_gate import ConsentGate
from .widgets.panel import Panel
from .widgets.lock_screen import IdleLock

APP_NAME = "MinuteOne (M1)"


def main():
    # High-DPI friendly
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # Consent gate (offline notice; optional online toggle is unchecked by default)
    gate = ConsentGate()
    if gate.exec_() != gate.Accepted:
        sys.exit(0)

    # Main side-panel
    win = Panel(allow_online=gate.allow_online())
    win.show()

    # Idle lock (5 min)
    locker = IdleLock(parent=win, idle_minutes=5)
    locker.install_on(app)
    # ui/app.py (inside main())
    with open("ui/assets/styles.qss", "r", encoding="utf-8") as f:
     app.setStyleSheet(f.read())
   
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()