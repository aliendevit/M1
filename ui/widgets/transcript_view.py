# path: ui/widgets/transcript_view.py
from __future__ import annotations

from typing import List, Dict

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel


class TranscriptView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(QLabel("Transcript (last 20s segments):"))
        self.list = QListWidget(self)
        self.list.setWordWrap(True)
        self.list.setSelectionMode(self.list.SingleSelection)
        lay.addWidget(self.list)

    def set_segments(self, segments: List[Dict]):
        self.list.clear()
        for s in segments:
            t = f"[{s.get('start_ms',0)//1000:02d}-{s.get('end_ms',0)//1000:02d}s] {s.get('text','')}"
            item = QListWidgetItem(t)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(self.list.count()-1)
