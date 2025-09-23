# path: ui/widgets/chips_rail.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from collections import Counter

from PyQt5.QtCore import Qt, QSize, pyqtSignal, QEvent
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QListWidget, QListWidgetItem,
    QStyleOptionViewItem, QApplication
)

# Band colors (WCAG-AA mindful), with shape encoding
COLOR_B = QColor("#6B7280")  # gray-500
COLOR_C = QColor("#F59E0B")  # amber-500
COLOR_D = QColor("#EF4444")  # red-500


@dataclass
class ChipModel:
    chip_id: str
    slot: str
    type: str                  # value|missing|guard|ambiguity|timer|unit
    band: str                  # A|B|C|D
    label: str
    options: List[str] = field(default_factory=list)
    proposed: Optional[str] = None
    confidence: float = 0.5
    risk: str = "low"
    evidence: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=lambda: ["accept","evidence"])


class ShapeBadge(QFrame):
    def __init__(self, band: str, parent=None):
        super().__init__(parent)
        self.band = band
        self.setFixedSize(18, 18)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = COLOR_B if self.band == "B" else COLOR_C if self.band == "C" else COLOR_D
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        w, h = self.width(), self.height()
        if self.band == "B":
            # circle ●
            r = min(w, h) - 2
            p.drawEllipse((w - r)//2, (h - r)//2, r, r)
        elif self.band == "C":
            # triangle ▲
            from PyQt5.QtCore import QPoint
            pts = [QPoint(w//2, 2), QPoint(2, h-2), QPoint(w-2, h-2)]
            p.drawPolygon(*pts)
        else:
            # square ■
            p.drawRect(2, 2, w-4, h-4)


class ChipItem(QFrame):
    evidenceRequested = pyqtSignal(list)  # source_ids
    accepted = pyqtSignal(str)            # chip_id
    overridden = pyqtSignal(str)          # chip_id

    def __init__(self, model: ChipModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("chipItem")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)

        top = QHBoxLayout()
        badge = ShapeBadge(self.model.band, self)
        top.addWidget(badge)
        lbl = QLabel(self.model.label)
        lbl.setWordWrap(True)
        lbl.setObjectName("chipLabel")
        top.addWidget(lbl, 1)
        lay.addLayout(top)

        # Options (render up to first 3 with 1/2/3 mapping)
        if self.model.options:
            opt_line = QHBoxLayout()
            for i, opt in enumerate(self.model.options[:3], start=1):
                btn = QPushButton(f"{i}. {opt}")
                btn.setProperty("opt_index", i-1)
                btn.clicked.connect(lambda _, j=i-1: self._choose_option(j))
                opt_line.addWidget(btn)
            opt_line.addStretch(1)
            lay.addLayout(opt_line)

        # Actions
        actions = QHBoxLayout()
        self.btn_accept = QPushButton("Accept (Enter)")
        self.btn_accept.clicked.connect(self._accept)
        actions.addWidget(self.btn_accept)

        self.btn_evid = QPushButton("Evidence (E)")
        self.btn_evid.clicked.connect(lambda: self.evidenceRequested.emit(self.model.evidence))
        actions.addWidget(self.btn_evid)

        if "override_blocked" in self.model.actions:
            self.btn_override = QPushButton("Override (needs reason)")
            self.btn_override.clicked.connect(self._override)
            actions.addWidget(self.btn_override)

        actions.addStretch(1)
        lay.addLayout(actions)

        # Accessibility name
        self.setAccessibleName(f"Chip {self.model.label} band {self.model.band}")

        # Disable accept for D without override
        if self.model.band == "D" and "accept" in self.model.actions:
            self.btn_accept.setEnabled(False)

    # Keyboard helpers
    def handle_keypress(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._accept()
        elif ev.key() == Qt.Key_E:
            self.evidenceRequested.emit(self.model.evidence)
        elif ev.key() in (Qt.Key_1, Qt.Key_2, Qt.Key_3) and self.model.options:
            idx = {Qt.Key_1:0, Qt.Key_2:1, Qt.Key_3:2}[ev.key()]
            if idx < len(self.model.options):
                self._choose_option(idx)

    def _choose_option(self, idx: int):
        self.model.proposed = self.model.options[idx]
        # Visual cue could be added; for MVP just update label tooltip
        self.setToolTip(f"Selected: {self.model.proposed}")

    def _accept(self):
        if self.model.band == "D" and "override_blocked" in self.model.actions:
            # require override instead of accept
            return
        self.accepted.emit(self.model.chip_id)

    def _override(self):
        # Simple inline reason prompt
        from PyQt5.QtWidgets import QInputDialog
        reason, ok = QInputDialog.getText(self, "Override blocked", "Reason:")
        if ok and reason.strip():
            self.overridden.emit(self.model.chip_id)

class ChipsRail(QWidget):
    evidenceRequested = pyqtSignal(list)
    batchAcceptTriggered = pyqtSignal(list)  # chip_ids

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chips: List[ChipModel] = []
        self._items: Dict[str, ChipItem] = {}
        self._focused_idx = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        # Header with batch-accept
        head = QHBoxLayout()
        self.lbl_header = QLabel("Chips")
        head.addWidget(self.lbl_header)
        self.btn_batch = QPushButton("Accept all (Enter)")
        self.btn_batch.setVisible(False)
        self.btn_batch.clicked.connect(self._emit_batch_accept)
        head.addWidget(self.btn_batch)
        head.addStretch(1)
        lay.addLayout(head)

        # Container
        self.container = QVBoxLayout()
        lay.addLayout(self.container)
        lay.addStretch(1)

        # Style
        self.setStyleSheet("""
        #chipItem { border: 1px solid #E5E7EB; border-radius: 8px; }
        QPushButton { padding: 4px 8px; }
        """)

    def set_chips(self, chips: List[ChipModel]):
        # Clear
        while self.container.count():
            item = self.container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._chips = chips
        self._items.clear()

        # Create items (skip A-band; auto-accepted)
        for c in self._chips:
            if c.band == "A":
                continue
            item = ChipItem(c, self)
            self._items[c.chip_id] = item
            self.container.addWidget(item)
            item.evidenceRequested.connect(self.evidenceRequested)
            item.accepted.connect(self._accept_one)
            item.overridden.connect(self._override_one)

        self._update_batch_header()

    # Keyboard routing
    def handle_keypress(self, ev):
        # Route keys to the currently "focused" chip (approximate by first visible)
        first_item = next(iter(self._items.values()), None)
        if first_item:
            first_item.handle_keypress(ev)

        # If Enter and header batch visible, trigger batch
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter) and self.btn_batch.isVisible():
            self._emit_batch_accept()

    # Batch logic
    def _update_batch_header(self):
        # Show when ≥3 B-chips of same type
        types = [c.type for c in self._chips if c.band == "B"]
        show = any(v >= 3 for v in Counter(types).values())
        self.btn_batch.setVisible(show)
        self.lbl_header.setText("Chips — Batch ready" if show else "Chips")

    def _emit_batch_accept(self):
        ids = [c.chip_id for c in self._chips if c.band == "B"]
        if ids:
            self.batchAcceptTriggered.emit(ids)

    def _accept_one(self, chip_id: str):
        # Remove visually
        w = self._items.pop(chip_id, None)
        if w:
            w.setParent(None)
            w.deleteLater()
        self._chips = [c for c in self._chips if c.chip_id != chip_id]
        self._update_batch_header()

    def _override_one(self, chip_id: str):
        # Mark visually as overridden (fade out by disabling)
        w = self._items.get(chip_id)
        if w:
            w.setEnabled(False)
