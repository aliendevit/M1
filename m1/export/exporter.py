from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

RTF_HEADER = "{\\rtf1\\ansi\\deff0\\pard "
RTF_FOOTER = "}"


def save_markdown(text: str, path: str | Path) -> Path:
    target = Path(path)
    target.write_text(text, encoding="utf-8")
    return target


def save_pdf(text: str, path: str | Path) -> Path:
    target = Path(path)
    c = canvas.Canvas(str(target), pagesize=letter)
    width, height = letter
    y = height - 72
    for line in text.splitlines() or [""]:
        if y < 72:
            c.showPage()
            y = height - 72
        c.drawString(72, y, line)
        y -= 14
    c.save()
    return target


def _escape_rtf(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\par ")
    )


def save_rtf(text: str, path: str | Path) -> Path:
    target = Path(path)
    escaped = _escape_rtf(text)
    target.write_text(f"{RTF_HEADER}{escaped}{RTF_FOOTER}", encoding="utf-8")
    return target
