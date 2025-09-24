"""Offline speech-to-text shim."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    start: float
    end: float


class Transcriber:
    """Placeholder transcription service that echoes scripted text."""

    def __init__(self, model: str = "faster-whisper-small-int8") -> None:
        self.model = model

    @classmethod
    def from_config(cls, config: dict | None) -> "Transcriber":
        if not config:
            return cls()
        return cls(model=str(config.get("model", "faster-whisper-small-int8")))

    def transcribe(self, audio_path: str | Path) -> List[TranscriptSegment]:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(path)
        return [TranscriptSegment(text=f"<placeholder transcript from {path.name}>", start=0.0, end=0.0)]
