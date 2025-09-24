"""ASR service backed by faster-whisper."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

try:  # pragma: no cover - optional heavyweight dependency
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover - fallback when not installed
    WhisperModel = None  # type: ignore[misc, assignment]


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    start: float
    end: float


class ASRService:
    """Thin wrapper around faster-whisper with graceful degradation."""

    def __init__(self, model_name: str = "faster-whisper-small-int8", device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self._model = self._load_model()

    @classmethod
    def from_config(cls, cfg: dict | None) -> "ASRService":
        cfg = cfg or {}
        return cls(
            model_name=str(cfg.get("model", "faster-whisper-small-int8")),
            device=str(cfg.get("device", "cpu")),
        )

    def transcribe(self, audio_path: str | Path, *, beam_size: int = 1) -> List[TranscriptSegment]:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(path)
        if self._model is None:
            # Offline demo fallback that returns a synthetic transcript marker.
            return [TranscriptSegment(text=f"<transcript unavailable: {path.name}>", start=0.0, end=0.0)]
        segments, _ = self._model.transcribe(str(path), beam_size=beam_size)
        output: List[TranscriptSegment] = []
        for segment in segments:
            output.append(
                TranscriptSegment(
                    text=segment.text.strip(),
                    start=float(segment.start),
                    end=float(segment.end),
                )
            )
        return output

    def _load_model(self):
        if WhisperModel is None:
            return None
        return WhisperModel(self.model_name, device=self.device)
