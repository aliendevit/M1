from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

try:  # pragma: no cover - optional dependency during tests
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover - optional dependency during tests
    WhisperModel = None  # type: ignore

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ASRConfig:
    model_path: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    vad_threshold: float = 0.005


class ASRService:
    """Thin wrapper around faster-whisper with energy VAD."""

    def __init__(self, config: ASRConfig):
        self.config = config
        self._model = self._load_model()

    def _load_model(self):  # pragma: no cover - heavy dependency
        if WhisperModel is None:
            LOGGER.warning("faster-whisper unavailable; ASR disabled")
            return None
        return WhisperModel(
            self.config.model_path,
            device=self.config.device,
            compute_type=self.config.compute_type,
        )

    def is_ready(self) -> bool:
        return self._model is not None

    def transcribe_file(self, path: str | Path) -> str:
        if not self.is_ready():
            return ""
        path = Path(path)
        segments, _ = self._model.transcribe(str(path))  # pragma: no cover
        return " ".join(seg.text.strip() for seg in segments)

    def transcribe_chunks(self, chunks: Iterable[bytes]) -> str:
        if not self.is_ready():
            return ""
        audio = b"".join(chunks)
        if not audio:
            return ""
        waveform = np.frombuffer(audio, dtype=np.int16)
        if not self._passes_vad(waveform):
            return ""
        buffer = io.BytesIO(audio)
        segments, _ = self._model.transcribe(buffer)  # pragma: no cover
        return " ".join(seg.text.strip() for seg in segments)

    def _passes_vad(self, waveform: np.ndarray) -> bool:
        if waveform.size == 0:
            return False
        energy = float(np.mean(np.square(waveform.astype(np.float32))))
        return energy >= self.config.vad_threshold


def init_asr(config: ASRConfig | None = None) -> ASRService | None:
    config = config or ASRConfig()
    service = ASRService(config)
    if not service.is_ready():
        return None
    return service
