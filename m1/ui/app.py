from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

from PyQt5 import QtCore, QtGui, QtWidgets

from m1.api.main import (
    _assessment_from_visit,
    _build_handoff,
    _risk_overrides,
    _score_visit,
    get_config,
    get_extractor,
    get_template_env,
)
from m1.chips.service import build_chips
from m1.export.exporter import save_markdown, save_pdf, save_rtf
from m1.extractor.llm import LLMExtractor
from m1.models import VisitJSON


@dataclass(slots=True)
class RenderState:
    visit: VisitJSON | None = None
    note: str = ""
    handoff: dict[str, Any] | None = None
    handoff_text: str = ""
    discharge: str = ""
    chips: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.chips is None:
            self.chips = []


class MinuteOneWindow(QtWidgets.QMainWindow):
    """PyQt desktop wrapper for MinuteOne flows."""

    def __init__(self, extractor: LLMExtractor) -> None:
        super().__init__()
        self.extractor = extractor
        self.config = get_config()
        self.template_env = get_template_env()
        self.state = RenderState()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("MinuteOne Clinical Assistant")
        self.resize(1100, 700)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self.transcript_edit = QtWidgets.QPlainTextEdit()
        self.transcript_edit.setPlaceholderText("Paste bedside transcript here...")
        layout.addWidget(self.transcript_edit)

        controls = QtWidgets.QHBoxLayout()
        layout.addLayout(controls)

        self.consent_check = QtWidgets.QCheckBox("Clinician consent to compose")
        controls.addWidget(self.consent_check)

        self.extract_button = QtWidgets.QPushButton("Extract (Ctrl+E)")
        self.extract_button.clicked.connect(self.handle_extract)
        controls.addWidget(self.extract_button)

        self.compose_note_button = QtWidgets.QPushButton("Compose Note")
        self.compose_note_button.clicked.connect(self.handle_compose_note)
        controls.addWidget(self.compose_note_button)

        self.compose_handoff_button = QtWidgets.QPushButton("Compose Handoff")
        self.compose_handoff_button.clicked.connect(self.handle_compose_handoff)
        controls.addWidget(self.compose_handoff_button)

        self.compose_discharge_button = QtWidgets.QPushButton("Compose Discharge")
        self.compose_discharge_button.clicked.connect(self.handle_compose_discharge)
        controls.addWidget(self.compose_discharge_button)

        self.export_button = QtWidgets.QPushButton("Export...")
        self.export_button.clicked.connect(self.handle_export)
        controls.addWidget(self.export_button)

        controls.addStretch(1)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self.note_view = QtWidgets.QPlainTextEdit()
        self.note_view.setReadOnly(True)
        self.tabs.addTab(self.note_view, "Note")

        self.handoff_view = QtWidgets.QPlainTextEdit()
        self.handoff_view.setReadOnly(True)
        self.tabs.addTab(self.handoff_view, "Handoff")

        self.discharge_view = QtWidgets.QPlainTextEdit()
        self.discharge_view.setReadOnly(True)
        self.tabs.addTab(self.discharge_view, "Discharge")

        self.sources_view = QtWidgets.QPlainTextEdit()
        self.sources_view.setReadOnly(True)
        self.tabs.addTab(self.sources_view, "Sources")

        self._init_dock()
        self._init_shortcuts()

    def _init_dock(self) -> None:
        self.chip_list = QtWidgets.QListWidget()
        self.chip_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        dock = QtWidgets.QDockWidget("Evidence Chips", self)
        dock.setWidget(self.chip_list)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)

    def _init_shortcuts(self) -> None:
        extract_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+E"), self)
        extract_shortcut.activated.connect(self.handle_extract)

    def handle_extract(self) -> None:
        transcript = self.transcript_edit.toPlainText().strip()
        if not transcript:
            QtWidgets.QMessageBox.warning(self, "MinuteOne", "Transcript cannot be empty.")
            return
        visit = self.extractor.extract(transcript)
        self.state.visit = visit
        slot_scores = _score_visit(visit, self.config)
        chips = build_chips(slot_scores, risk_overrides=_risk_overrides(self.config))
        self.state.chips = [chip.model_dump(mode="json") for chip in chips]
        self._render_chips()
        self.sources_view.setPlainText(json.dumps(visit.model_dump(mode="json"), indent=2))
        QtWidgets.QMessageBox.information(self, "MinuteOne", "Extraction complete.")

    def _render_chips(self) -> None:
        self.chip_list.clear()
        band_colors = {
            "A": QtGui.QColor("#2e7d32"),
            "B": QtGui.QColor("#546e7a"),
            "C": QtGui.QColor("#f9a825"),
            "D": QtGui.QColor("#c62828"),
        }
        for chip in self.state.chips:
            item = QtWidgets.QListWidgetItem(chip["label"])
            band = chip.get("band", "C")
            color = band_colors.get(band, QtGui.QColor("#546e7a"))
            item.setData(QtCore.Qt.UserRole, chip)
            item.setToolTip(f"Band {band} | Confidence {chip.get('confidence')}")
            brush = QtGui.QBrush(color)
            brush.setStyle(QtCore.Qt.SolidPattern)
            item.setForeground(QtGui.QBrush(QtCore.Qt.black))
            item.setBackground(brush)
            self.chip_list.addItem(item)

    def _require_visit(self) -> VisitJSON | None:
        if not self.state.visit:
            QtWidgets.QMessageBox.warning(self, "MinuteOne", "Run extraction first.")
            return None
        if not self.consent_check.isChecked():
            QtWidgets.QMessageBox.warning(self, "MinuteOne", "Consent is required before composing.")
            return None
        return self.state.visit

    def handle_compose_note(self) -> None:
        visit = self._require_visit()
        if not visit:
            return
        template = self.template_env.get_template("note.j2")
        note = template.render(
            visit=visit,
            assessment_summary=_assessment_from_visit(visit),
            citations=self._citations_for_ui(),
        )
        self.state.note = note
        self.note_view.setPlainText(note)

    def handle_compose_handoff(self) -> None:
        visit = self._require_visit()
        if not visit:
            return
        handoff = _build_handoff(visit, {"labs": []})
        self.state.handoff = handoff
        template = self.template_env.get_template("handoff_ipass.j2")
        text = template.render(handoff=handoff)
        self.state.handoff_text = text
        self.handoff_view.setPlainText(text)

    def handle_compose_discharge(self) -> None:
        visit = self._require_visit()
        if not visit:
            return
        template = self.template_env.get_template("discharge_en.j2")
        discharge = template.render(visit=visit, patient_name="Patient", follow_up=[])
        self.state.discharge = discharge
        self.discharge_view.setPlainText(discharge)

    def _citations_for_ui(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "chief",
                "text": "Clinician transcript",
                "ts": QtCore.QDateTime.currentDateTimeUtc().toString(QtCore.Qt.ISODate),
            }
        ]

    def handle_export(self) -> None:
        current = self.tabs.currentWidget()
        if current not in {self.note_view, self.handoff_view, self.discharge_view}:
            QtWidgets.QMessageBox.information(self, "MinuteOne", "Select a narrative tab to export.")
            return
        content = current.toPlainText()
        if not content:
            QtWidgets.QMessageBox.warning(self, "MinuteOne", "Nothing to export yet.")
            return
        dialog = QtWidgets.QFileDialog(self)
        dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dialog.setNameFilters(["Markdown (*.md)", "PDF (*.pdf)", "Rich Text (*.rtf)"])
        if not dialog.exec_():
            return
        path = dialog.selectedFiles()[0]
        selected_filter = dialog.selectedNameFilter()
        if "Markdown" in selected_filter:
            save_markdown(content, path)
        elif "PDF" in selected_filter:
            save_pdf(content, path)
        else:
            save_rtf(content, path)
        QtWidgets.QMessageBox.information(self, "MinuteOne", "Export complete.")


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    extractor = get_extractor()
    window = MinuteOneWindow(extractor)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
