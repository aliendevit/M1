"""Edge ASR service wrapper.

The production system would stream audio into faster-whisper.  For the
purposes of the open-source skeleton we expose a synchronous function
that accepts already-decoded text (useful for unit tests and offline
development).  The logic keeps the latency and deterministic nature of
rule-first processing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class SegmentSpan:
    start: float
    end: float
    speaker: str
    text: str


@dataclass
class ASRResult:
    text: str
    spans: List[SegmentSpan]


class ASRService:
    """Simplified ASR façade used by the FastAPI layer."""

    def __init__(self, segment_length: float = 20.0) -> None:
        self.segment_length = segment_length

    def transcribe(self, audio_chunk: str) -> ASRResult:
        """Return a deterministic transcript for the provided chunk.

        We assume ``audio_chunk`` is already text (e.g. pre-recorded
        transcript) which keeps tests hermetic.  The text is chunked into
        sentence-like spans using ``segment_length`` as a coarse timer.
        """

        if not audio_chunk:
            return ASRResult(text="", spans=[])

        words = audio_chunk.strip().split()
        spans: List[SegmentSpan] = []
        cursor = 0.0
        current_words: List[str] = []
        for index, word in enumerate(words, start=1):
            current_words.append(word)
            if index % 12 == 0:  # deterministic pseudo segmentation
                span_text = " ".join(current_words)
                spans.append(
                    SegmentSpan(
                        start=cursor,
                        end=cursor + self.segment_length,
                        speaker="unknown",
                        text=span_text,
                    )
                )
                cursor += self.segment_length
                current_words = []
        if current_words:
            span_text = " ".join(current_words)
            spans.append(
                SegmentSpan(
                    start=cursor,
                    end=cursor + self.segment_length,
                    speaker="unknown",
                    text=span_text,
                )
            )
        return ASRResult(text=" ".join(words), spans=spans)
