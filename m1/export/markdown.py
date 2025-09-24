"""Markdown export utilities."""
from __future__ import annotations

from typing import Dict, Iterable, List


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
        lines.append(f"## {key.title()}")
        if isinstance(value, dict):
            for inner_key, inner_value in value.items():
                lines.append(f"- **{inner_key}**: {inner_value}")
        elif isinstance(value, list):
            for item in value:
                lines.append(f"- {item}")
        else:
            lines.append(str(value))
    return "\n".join(lines)
