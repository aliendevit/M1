"""Template-driven composers for note, handoff, and discharge outputs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import get_cached_config
from ..schemas import EvidenceChip, VisitJSON


@dataclass
class RenderedArtifact:
    content: str
    citations: List[str]


class Composer:
    def __init__(self, template_dir: Path | str | None = None) -> None:
        directory = Path(template_dir or Path(__file__).resolve().parent / "../templates").resolve()
        self.environment = Environment(
            loader=FileSystemLoader(directory),
            autoescape=select_autoescape(enabled_extensions=("md", "j2"), default_for_string=True),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.config = get_cached_config()

    def _build_citation_map(self, evidence: Iterable[EvidenceChip]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for index, chip in enumerate(evidence, start=1):
            mapping[chip.source_id] = index
        return mapping

    def _render(self, template_name: str, *, visit: VisitJSON, evidence: Iterable[EvidenceChip], extra: dict | None = None) -> RenderedArtifact:
        template = self.environment.get_template(template_name)
        evidence_list = list(evidence)
        citation_map = self._build_citation_map(evidence_list)

        def cite(source_id: str | None) -> str:
            if not source_id:
                return ""
            idx = citation_map.get(source_id)
            return f"[^{idx}]" if idx else ""

        context = {"visit": visit, "evidence": evidence_list, "cite": cite}
        if extra:
            context.update(extra)
        content = template.render(**context)
        footnotes = []
        for chip in evidence_list:
            idx = citation_map.get(chip.source_id)
            if not idx:
                continue
            footnotes.append(f"[^{idx}]: {chip.name} {chip.value} at {chip.time} ({chip.source_id})")
        if footnotes:
            content = f"{content}\n\n" + "\n".join(footnotes)
        return RenderedArtifact(content=content.strip(), citations=[chip.source_id for chip in evidence_list])

    def render_note(self, visit: VisitJSON, evidence: Iterable[EvidenceChip]) -> RenderedArtifact:
        missing = self._missing_sections(visit)
        return self._render("note.j2", visit=visit, evidence=evidence, extra={"missing": missing})

    def render_handoff(self, visit: VisitJSON, evidence: Iterable[EvidenceChip]) -> RenderedArtifact:
        missing = self._missing_sections(visit)
        return self._render("handoff_ipass.j2", visit=visit, evidence=evidence, extra={"missing": missing})

    def render_discharge(
        self,
        visit: VisitJSON,
        evidence: Iterable[EvidenceChip],
        *,
        language: str | None = None,
    ) -> RenderedArtifact:
        languages = self.config.localization.discharge_languages
        selected = language or self.config.localization.default
        if selected not in languages:
            selected = self.config.localization.default
        templates = [f"discharge_{selected}.j2"]
        if selected == "en" and "es" in languages:
            templates.append("discharge_es.j2")
        elif selected == "es" and "en" in languages:
            templates.insert(0, "discharge_en.j2")
        parts: List[str] = []
        evidence_list = list(evidence)
        for template_name in templates:
            rendered = self._render(template_name, visit=visit, evidence=evidence_list)
            parts.append(rendered.content)
        content = "\n\n".join(parts)
        return RenderedArtifact(content=content, citations=[chip.source_id for chip in evidence_list])

    def _missing_sections(self, visit: VisitJSON) -> List[str]:
        missing: List[str] = []
        if not visit.hpi.onset:
            missing.append("HPI onset")
        if not visit.hpi.quality:
            missing.append("HPI quality")
        if not visit.plan_intents:
            missing.append("Plan intents")
        return missing
