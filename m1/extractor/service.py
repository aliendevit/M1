"""Public extraction helpers used by FastAPI and tests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..config import get_cached_config
from .llm import ExtractionResult, VisitJSONExtractor


@dataclass
class ExtractorFacade:
    """Wrap the VisitJSONExtractor with cached configuration."""

    def extract(self, transcript: str, chart_facts: Iterable[str] | None = None) -> ExtractionResult:
        config = get_cached_config()
        extractor = VisitJSONExtractor(config.llm, enable_llm=False)
        return extractor.extract(transcript, chart_facts)


def extract_visit(transcript: str, chart_facts: Iterable[str] | None = None) -> ExtractionResult:
    facade = ExtractorFacade()
    return facade.extract(transcript, chart_facts)
