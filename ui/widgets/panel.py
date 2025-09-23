# path: ui/widgets/panel.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit,
    QSplitter, QSizePolicy, QFrame, QMessageBox
)

from .transcript_view import TranscriptView
from .chips_rail import ChipsRail, ChipModel
from .evidence_popover import EvidencePopover


@dataclass
class _State:
    visitjson: Dict
    facts: List[Dict]
    ipass: Dict
    discharge_lang: str = "en"


class Panel(QWidget):
    evidenceRequested = pyqtSignal(list)  # source_ids

    def __init__(self, allow_online: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("M1 — Side Panel")
        self.setMinimumWidth(420)
        self.allow_online = allow_online

        self._state = _State(
            visitjson={
                "chief_complaint": "chest pain",
                "hpi": {"onset": "since 2 hours", "quality": "pressure", "modifiers": [], "associated_symptoms": ["nausea"], "red_flags": []},
                "exam_bits": {"cv": "regular rate and rhythm", "lungs": "clear to auscultation"},
                "risks": [],
                "plan_intents": [
                    {"type": "lab_series", "name": "Troponin series", "dose": None, "schedule": ["now", "q3h ×2"]},
                    {"type": "test", "name": "ECG", "dose": None, "schedule": ["now"]},
                ],
                "language_pref": "en",
            },
            facts=[
                {"id":"obs/123","kind":"lab","name":"Troponin I","value":"0.04 ng/mL","time":"2025-09-21T07:45","source_id":"obs/123"},
                {"id":"obs/124","kind":"lab","name":"Troponin I","value":"0.06 ng/mL","time":"2025-09-21T10:45","source_id":"obs/124"},
            ],
            ipass={"I":{"severity":"stable"},"P":{"summary":"Chest pain"},"A":{"action_list":[]},"S":{"situation_awareness":[]},"S2":{"synthesis_by_receiver":""}},
            discharge_lang="en",
        )

        self._build_ui()
        self._wire_hotkeys()
        self._load_stub_content()

    # ---------- UI ----------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.North)

        # Note tab
        self.note_view = QTextEdit(self)
        self.note_view.setReadOnly(True)
        note_wrap = QVBoxLayout()
        note_top = QHBoxLayout()
        self.btn_refresh_note = QPushButton("Refresh Note")
        note_top.addWidget(self.btn_refresh_note)
        note_top.addStretch(1)
        note_panel = QWidget()
        note_panel.setLayout(note_wrap)
        note_wrap.addLayout(note_top)
        note_wrap.addWidget(self.note_view)
        self.tabs.addTab(note_panel, "Note")

        # Handoff tab
        self.handoff_view = QTextEdit(self)
        self.handoff_view.setReadOnly(True)
        handoff_top = QHBoxLayout()
        self.lbl_ipass_pct = QLabel("Completeness: —")
        handoff_top.addWidget(self.lbl_ipass_pct)
        handoff_top.addStretch(1)
        hand_panel = QWidget()
        hand_lay = QVBoxLayout(hand_panel)
        hand_lay.addLayout(handoff_top)
        hand_lay.addWidget(self.handoff_view)
        self.tabs.addTab(hand_panel, "Handoff")

        # Discharge tab
        self.discharge_view = QTextEdit(self)
        self.discharge_view.setReadOnly(True)
        dis_top = QHBoxLayout()
        self.btn_lang_en = QPushButton("EN")
        self.btn_lang_es = QPushButton("ES")
        dis_top.addWidget(QLabel("Language:"))
        dis_top.addWidget(self.btn_lang_en)
        dis_top.addWidget(self.btn_lang_es)
        dis_top.addStretch(1)
        dis_panel = QWidget()
        dis_lay = QVBoxLayout(dis_panel)
        dis_lay.addLayout(dis_top)
        dis_lay.addWidget(self.discharge_view)
        self.tabs.addTab(dis_panel, "Discharge")

        # Sources + Chips tab
        split = QSplitter(self)
        split.setOrientation(Qt.Horizontal)

        self.transcript = TranscriptView(self)
        self.rail = ChipsRail(self)

        split.addWidget(self.transcript)
        split.addWidget(self.rail)
        split.setSizes([200, 220])

        sources_panel = QWidget()
        sp_lay = QVBoxLayout(sources_panel)
        sp_lay.addWidget(split)
        self.tabs.addTab(sources_panel, "Sources + Chips")

        layout.addWidget(self.tabs)

        # Evidence popover dialog (lazy per request)
        self.evidenceRequested.connect(self._show_evidence)

        # Signals
        self.btn_refresh_note.clicked.connect(self._refresh_note)
        self.btn_lang_en.clicked.connect(lambda: self._set_lang("en"))
        self.btn_lang_es.clicked.connect(lambda: self._set_lang("es"))
        self.rail.evidenceRequested.connect(self.evidenceRequested)
        self.rail.batchAcceptTriggered.connect(self._batch_accept)

    def _wire_hotkeys(self):
        # Keyboard-first: forward keys to rail globally when on Sources+Chips tab
        self.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and self.tabs.currentIndex() == 3:
            self.rail.handle_keypress(ev)
            return True
        return super().eventFilter(obj, ev)

    # ---------- Content ----------
    def _load_stub_content(self):
        # Load stub transcript
        self.transcript.set_segments([
            {"start_ms":0,"end_ms":12000,"text":"Patient reports chest pain for 2 hours, pressure-like, with nausea."},
            {"start_ms":12000,"end_ms":20000,"text":"Denies shortness of breath. Exam normal, ECG pending."},
        ])
        # Load stub chips
        chips = [
            ChipModel(chip_id="cp-1", slot="troponin_series", type="value", band="B", label="Troponin cadence",
                      options=["q3h ×2","q3h ×3","custom"], proposed="q3h ×2", confidence=0.78, risk="medium",
                      evidence=["obs/123","obs/124"], actions=["accept","evidence"]),
            ChipModel(chip_id="cp-2", slot="asa_now", type="guard", band="D", label="Aspirin 325 mg now",
                      options=[], proposed="325 mg PO ×1", confidence=0.42, risk="high",
                      evidence=[], actions=["override_blocked","evidence"]),
            ChipModel(chip_id="cp-3", slot="ecg_now", type="value", band="B", label="ECG now",
                      options=["now"], proposed="now", confidence=0.80, risk="high", evidence=[], actions=["accept","evidence"]),
            ChipModel(chip_id="cp-4", slot="cta_contrast", type="value", band="B", label="CTA chest with contrast",
                      options=["now","defer"], proposed="defer", confidence=0.73, risk="medium", evidence=[], actions=["accept","evidence"]),
            ChipModel(chip_id="cp-5", slot="education_acs", type="value", band="C", label="Education: ACS return precautions",
                      options=["teach-back"], proposed="teach-back", confidence=0.65, risk="low", evidence=[], actions=["accept","evidence"]),
        ]
        self.rail.set_chips(chips)
        self._refresh_note()
        self._refresh_handoff()
        self._refresh_discharge()

    # ---------- Actions ----------
    def _refresh_note(self):
        # Minimal inline template rendering (placeholder; backend composer will replace)
        V = self._state.visitjson
        note = [
            "# NOTE (preview)",
            f"Chief Complaint: {V['chief_complaint']}",
            f"HPI: onset={V['hpi'].get('onset')}, quality={V['hpi'].get('quality')}",
            f"Exam: CV={V['exam_bits'].get('cv')}, Lungs={V['exam_bits'].get('lungs')}",
            "Plan:",
        ]
        for p in V.get("plan_intents", []):
            line = f" - ({p['type']}) {p['name']}"
            if p.get("dose"): line += f" — {p['dose']}"
            if p.get("schedule"): line += f" — {', '.join(p['schedule'])}"
            note.append(line)
        self.note_view.setPlainText("\n".join(note))

    def _refresh_handoff(self):
        ipass = self._state.ipass
        # Basic completeness
        required = [("I","severity"),("P","summary"),("A","action_list"),("S","situation_awareness"),("S2","synthesis_by_receiver")]
        present = sum(1 for sec,key in required if ipass.get(sec,{}).get(key) not in (None,"",[],{}))
        pct = int(round(100 * present / len(required)))
        self.lbl_ipass_pct.setText(f"Completeness: {pct}%")
        self.handoff_view.setPlainText(json.dumps(ipass, indent=2))

    def _set_lang(self, lang: str):
        self._state.discharge_lang = lang
        self._refresh_discharge()

    def _refresh_discharge(self):
        V = self._state.visitjson
        if self._state.discharge_lang == "es":
            text = (
                "# Instrucciones de Alta\n\n"
                f"Motivo: {V['chief_complaint']}\n\n"
                "Qué encontramos: Evaluamos su condición.\n\n"
                "Cuándo buscar ayuda: dolor empeorando, dificultad para respirar, fiebre alta, desmayo.\n"
            )
        else:
            text = (
                "# Discharge Instructions\n\n"
                f"Reason: {V['chief_complaint']}\n\n"
                "What we found: We evaluated your condition.\n\n"
                "When to seek help: worsening pain, trouble breathing, high fever, fainting.\n"
            )
        self.discharge_view.setPlainText(text)

    def _batch_accept(self, chip_ids: List[str]):
        count = self.rail.batch_accept(chip_ids)
        QMessageBox.information(self, "Batch accept", f"Accepted {count} chip(s).")

    def _show_evidence(self, source_ids: List[str]):
        dlg = EvidencePopover(source_ids, parent=self)
        dlg.exec_()
