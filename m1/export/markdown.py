"""Markdown export utilities."""
from __future__ import annotations

from typing import Dict, List


def render_markdown(bundle: Dict[str, object]) -> str:
    sections = bundle.get("sections") if isinstance(bundle, dict) else {}
    lines: List[str] = ["# MinuteOne Note"]

    subjective = sections.get("subjective") if isinstance(sections, dict) else {}
    transcript = subjective.get("transcript") if isinstance(subjective, dict) else ""
    if transcript:
        lines.append("## Subjective")
        lines.append(transcript)

    structured = sections.get("structured") if isinstance(sections, dict) else {}
    for key, value in structured.items():
        lines.append(f"## {_format_header(key)}")
        if isinstance(value, dict):
            for inner_key, inner_value in value.items():
                label = _format_header(inner_key)
                lines.append(f"- **{label}**: {inner_value}")
        elif isinstance(value, list):
            for item in value:
                lines.append(f"- {_format_bullet(item)}")
        else:
            lines.append(str(value))
    return "\n".join(lines)


def _format_header(raw: str) -> str:
    return raw.replace("_", " ").title()


def _format_bullet(value: object) -> str:
    if isinstance(value, str) and value and value == value.lower() and value.replace(" ", "").isalpha():
        return value.capitalize()
    return str(value)
