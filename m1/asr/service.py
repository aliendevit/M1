"""Offline-first ASR façade used by the FastAPI layer.

The production deployment runs the Faster-Whisper ``small`` model with
Silero VAD.  For the repository tests we implement a deterministic
fallback that keeps the same interfaces but works purely with text
snippets.  When Faster-Whisper is available the wrapper will delegate to
it; otherwise we perform lightweight segmentation, pseudo diarisation,
and return timestamps that respect the configured segment length.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

from ..config import ASRConfig

try:  # pragma: no cover - optional dependency
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    WhisperModel = None  # type: ignore
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
    """Wrap either Faster-Whisper or a deterministic text segmenter."""
    def __init__(
        self,
        config: ASRConfig,
        *,
        diarize: bool = True,
    ) -> None:
        self.config = config
        self.segment_length = config.segment_ms / 1000.0
        self._diarize = diarize
        self._model = None
        if WhisperModel is not None:  # pragma: no cover - requires heavyweight dep
            try:
                self._model = WhisperModel(
                    config.model,
                    device="auto",
                    compute_type="int8",
                )
            except Exception:
                # When the model cannot be loaded (e.g. missing files in CI) we
                # fall back to the lightweight implementation.
                self._model = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def transcribe_file(self, audio_path: Path | str) -> ASRResult:
        """Transcribe an audio (or transcript) file."""

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(path)

        if self._model is None:
            text = path.read_text(encoding="utf-8")
            return self._segment_text(text)

        # pragma: no cover - requires the optional dependency and model files
        segments = list(self._model.transcribe(str(path))[0])
        spans = [
            SegmentSpan(
                start=float(segment.start or 0.0),
                end=float(segment.end or 0.0),
                speaker=self._speaker_for_index(index) if self._diarize else "unknown",
                text=segment.text.strip(),
            )
            for index, segment in enumerate(segments)
        ]
        transcript = " ".join(span.text for span in spans)
        return ASRResult(text=transcript, spans=spans)

    def transcribe_segment(self, audio_chunk: bytes | str) -> ASRResult:
        """Transcribe a streaming audio chunk.

        The API accepts either binary audio (base64-encoded in HTTP) or a
        raw transcript snippet.  For offline tests we primarily exercise
        the transcript path which keeps the execution deterministic and
        CPU-friendly.
        """

        if isinstance(audio_chunk, bytes):
            chunk_text = self._decode_bytes(audio_chunk)
        else:
            chunk_text = self._maybe_base64(audio_chunk)

        if self._model is None:
            return self._segment_text(chunk_text)

        # pragma: no cover - requires optional dependency
        segments = list(
            self._model.transcribe(
                audio=chunk_text,
                vad_filter=True,
                vad_parameters={"threshold": 0.5},
            )[0]
        )
        spans = [
            SegmentSpan(
                start=float(segment.start or 0.0),
                end=float(segment.end or 0.0),
                speaker=self._speaker_for_index(index) if self._diarize else "unknown",
                text=segment.text.strip(),
            )
            for index, segment in enumerate(segments)
        ]
        transcript = " ".join(span.text for span in spans)
        return ASRResult(text=transcript, spans=spans)

    def stream_segments(self, chunks: Iterable[bytes | str]) -> Iterator[SegmentSpan]:
        """Yield segments for a stream of chunks."""

        for chunk in chunks:
            result = self.transcribe_segment(chunk)
            for span in result.spans:
                yield span

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _segment_text(self, transcript: str) -> ASRResult:
        text = transcript.strip()
        if not text:
            return ASRResult(text="", spans=[])

        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
        spans: List[SegmentSpan] = []
        cursor = 0.0
        for index, sentence in enumerate(sentences):
            words = max(len(sentence.split()), 1)
            duration = max(self.segment_length, words / 3.0)
            speaker = self._speaker_for_sentence(sentence, index)
            spans.append(
                SegmentSpan(
                    start=round(cursor, 3),
                    end=round(cursor + duration, 3),
                    speaker=speaker,
                    text=sentence,
                )
            )
            cursor += duration
        transcript_text = " ".join(span.text for span in spans)
        return ASRResult(text=transcript_text, spans=spans)

    def _speaker_for_sentence(self, sentence: str, index: int) -> str:
        lowered = sentence.lower()
        if lowered.startswith("patient:") or lowered.startswith("pt:"):
            return "patient"
        if lowered.startswith("doctor:") or lowered.startswith("dr:"):
            return "clinician"
        if "i think" in lowered and index % 2 == 0:
            return "clinician"
        return "patient" if index % 2 else "clinician"

    def _speaker_for_index(self, index: int) -> str:
        return "clinician" if index % 2 == 0 else "patient"

    def _decode_bytes(self, payload: bytes) -> str:
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            # Treat as base64-encoded PCM dumped into bytes.  We cannot
            # decode audio without optional deps; return JSON metadata to
            # keep tests deterministic.
            try:
                decoded = base64.b64decode(payload)
                return decoded.decode("utf-8", errors="ignore")
            except Exception:
                return ""

    def _maybe_base64(self, payload: str) -> str:
        stripped = payload.strip()
        if not stripped:
            return ""
        try:
            decoded = base64.b64decode(stripped, validate=True)
        except Exception:
            return stripped
        text = decoded.decode("utf-8", errors="ignore")
        if text.count("\x00") > len(text) // 4:
            # Looks like raw audio bytes.  We cannot decode without
            # optional deps so return empty string.
            return ""
        return text


def serialise_result(result: ASRResult) -> dict:
    """Utility used by the API layer to convert dataclasses into JSON."""

    return {
        "text": result.text,
        "spans": [
            {
                "start": span.start,
                "end": span.end,
                "speaker": span.speaker,
                "text": span.text,
            }
            for span in result.spans
        ],
    }
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
