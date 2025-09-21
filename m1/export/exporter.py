"""Markdown/PDF/RTF exporters for composed artifacts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List

try:  # pragma: no cover - optional dependency
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:  # pragma: no cover - optional dependency
    canvas = None  # type: ignore
    letter = (612, 792)  # type: ignore


class Exporter:
    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self, prefix: str, note: str, handoff: str, discharge: str) -> List[Path]:
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        base = f"{prefix}-{timestamp}"
        md_path = self.output_dir / f"{base}.md"
        pdf_path = self.output_dir / f"{base}.pdf"
        rtf_path = self.output_dir / f"{base}.rtf"
        self._write_markdown(md_path, note, handoff, discharge)
        self._write_pdf(pdf_path, note, handoff, discharge)
        self._write_rtf(rtf_path, note, handoff, discharge)
        return [md_path, pdf_path, rtf_path]

    def _write_markdown(self, path: Path, note: str, handoff: str, discharge: str) -> None:
        content = [
            "# MinuteOne Encounter Export",
            "",
            "## SOAP/MDM Note",
            note,
            "",
            "## I-PASS",
            handoff,
            "",
            "## Discharge",
            discharge,
        ]
        path.write_text("\n".join(content), encoding="utf-8")

    def _write_pdf(self, path: Path, note: str, handoff: str, discharge: str) -> None:
        if canvas is None:  # pragma: no cover - optional dependency
            path.write_text("MinuteOne Export (install reportlab for rich PDF)", encoding="utf-8")
            return
        pdf = canvas.Canvas(str(path), pagesize=letter)
        width, height = letter
        text_obj = pdf.beginText(40, height - 40)
        for line in self._iter_lines(note, handoff, discharge):
            text_obj.textLine(line)
            if text_obj.getY() < 40:
                pdf.drawText(text_obj)
                pdf.showPage()
                text_obj = pdf.beginText(40, height - 40)
        pdf.drawText(text_obj)
        pdf.save()

    def _write_rtf(self, path: Path, note: str, handoff: str, discharge: str) -> None:
        lines = [
            "{\\rtf1\\ansi",
            "{\\b MinuteOne Encounter Export}\\line",
            "{\\b SOAP/MDM}\\line",
            note.replace("\n", "\\line "),
            "\\line {\\b I-PASS}\\line",
            handoff.replace("\n", "\\line "),
            "\\line {\\b Discharge}\\line",
            discharge.replace("\n", "\\line "),
            "}",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")

    def _iter_lines(self, note: str, handoff: str, discharge: str) -> Iterable[str]:
        yield "MinuteOne Encounter Export"
        yield ""
        yield "SOAP/MDM"
        yield from note.splitlines()
        yield ""
        yield "I-PASS"
        yield from handoff.splitlines()
        yield ""
        yield "Discharge"
        yield from discharge.splitlines()
