"""Minimal PyQt launcher for the MinuteOne side panel.

The README instructs integrators to run ``python -m m1.ui.app``.  The
module therefore provides a small CLI wrapper that loads the project
configuration and spins up a placeholder PyQt window when the optional
GUI dependencies are available.  When PyQt is missing (for example in
CI or headless validation) the script fails fast with a helpful
message.  A ``--headless`` flag allows automated checks to validate the
configuration without importing PyQt.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from m1.config import load_config


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        prog="python -m m1.ui.app",
        description="Launch the MinuteOne side-panel UI.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to the YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Load configuration only; skip importing PyQt (useful for CI)",
    )
    return parser


def _load_pyqt():  # pragma: no cover - exercised only when PyQt is installed
    """Import PyQt lazily supporting either PyQt6 or PyQt5."""

    try:
        from PyQt6.QtWidgets import (  # type: ignore[attr-defined]
            QApplication,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QTabWidget,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        try:
            from PyQt5.QtWidgets import (  # type: ignore[attr-defined]
                QApplication,
                QLabel,
                QListWidget,
                QListWidgetItem,
                QMainWindow,
                QTabWidget,
                QVBoxLayout,
                QWidget,
            )
        except ImportError as exc:  # pragma: no cover - import guard only
            raise RuntimeError(
                "PyQt is not installed. Install requirements-optional.txt to "
                "launch the UI."
            ) from exc

    return {
        "QApplication": QApplication,
        "QMainWindow": QMainWindow,
        "QTabWidget": QTabWidget,
        "QWidget": QWidget,
        "QVBoxLayout": QVBoxLayout,
        "QLabel": QLabel,
        "QListWidget": QListWidget,
        "QListWidgetItem": QListWidgetItem,
    }


def launch_ui(config_path: Path) -> int:
    """Launch the PyQt window using the provided configuration."""

    widgets = _load_pyqt()
    QApplication = widgets["QApplication"]
    QMainWindow = widgets["QMainWindow"]
    QTabWidget = widgets["QTabWidget"]
    QWidget = widgets["QWidget"]
    QVBoxLayout = widgets["QVBoxLayout"]
    QLabel = widgets["QLabel"]
    QListWidget = widgets["QListWidget"]
    QListWidgetItem = widgets["QListWidgetItem"]

    config = load_config(config_path)

    app = QApplication(sys.argv)

    class MinuteOneWindow(QMainWindow):  # pragma: no cover - GUI behaviour
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("MinuteOne Side Panel")
            self.resize(960, 640)

            tabs = QTabWidget(self)
            tabs.addTab(
                _build_note_tab(config, QWidget, QVBoxLayout, QLabel),
                "Note",
            )
            tabs.addTab(
                _build_handoff_tab(config, QWidget, QVBoxLayout, QLabel),
                "Handoff",
            )
            tabs.addTab(
                _build_discharge_tab(config, QWidget, QVBoxLayout, QLabel),
                "Discharge",
            )
            tabs.addTab(
                _build_sources_tab(
                    config, QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
                ),
                "Sources",
            )

            self.setCentralWidget(tabs)

    window = MinuteOneWindow()
    window.show()
    return app.exec()


def _build_note_tab(config, QWidget, QVBoxLayout, QLabel):  # pragma: no cover
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Structured SOAP/MDM note with inline citations."))
    layout.addWidget(
        QLabel(
            "Citations auto-populate from EvidenceChips. "
            "Edit controls will ship in a future iteration."
        )
    )
    layout.addWidget(QLabel("Use Ctrl+C to copy or the Export button for MD/PDF/RTF."))
    return widget


def _build_handoff_tab(config, QWidget, QVBoxLayout, QLabel):  # pragma: no cover
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("I-PASS summary preview (Illness, Summary, Action, Pending, Contingency, Synthesis)."))
    layout.addWidget(
        QLabel(
            "Banded chips (Auto/Soft/Must/Blocked) appear in the rail to the right."
        )
    )
    layout.addWidget(QLabel("Keyboard: Enter=accept, 2=edit, 3=override, E=evidence."))
    return widget


def _build_discharge_tab(config, QWidget, QVBoxLayout, QLabel):  # pragma: no cover
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(
        QLabel(
            "Bilingual discharge instructions ("
            + ", ".join(config.localization.discharge_languages)
            + ")"
        )
    )
    return widget


def _build_sources_tab(
    config,
    QWidget,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
):  # pragma: no cover
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Evidence sources preview"))
    sources = QListWidget(widget)
    for enabled in config.pathways.enabled or []:
        QListWidgetItem(f"Plan pack enabled: {enabled}", sources)
    QListWidgetItem("Consent required before ASR starts (press Space)", sources)
    layout.addWidget(sources)
    return widget


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point used by ``python -m m1.ui.app`` and unit tests."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = load_config(args.config)
    except Exception as exc:  # pragma: no cover - config errors tested elsewhere
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return 1

    if args.headless:
        print(
            "Loaded config for localization languages: "
            + ", ".join(config.localization.discharge_languages)
        )
        return 0

    try:
        return launch_ui(args.config)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
