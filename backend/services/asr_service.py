# path: backend/services/asr_service.py
from __future__ import annotations

import base64
import io
import tempfile
import threading
from datetime import datetime
from typing import Dict, List, Optional

def _load_config() -> Dict:
    try:
        import yaml, os
        with open(os.path.join("config", "config.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        # Defaults per brief
        return {
            "asr": {"model_dir": "models/asr/faster-whisper-small-int8", "vad": "silero", "segment_ms": 20000},
        }

class ASRService:
    """
    Offline ASR pipeline:
      - (optional) VAD pre-trim (Silero .jit, fallback to webrtcvad)
      - faster-whisper small (int8) via CTranslate2
    Returns: {"text": str, "spans":[{"start_ms":int,"end_ms":int,"text_start":int,"text_end":int}]}
    """
    _instance: Optional["ASRService"] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ASRService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self.cfg = _load_config()
        self._stub = False
        self._model = None
        self._vad = None
        # VAD
        try:
            from .vad_silero import VAD
            self._vad = VAD.from_config(self.cfg.get("asr", {}))
        except Exception:
            self._vad = None
        # faster-whisper
        try:
            from faster_whisper import WhisperModel
            mdir = self.cfg.get("asr", {}).get("model_dir", "models/asr/faster-whisper-small-int8")
            self._model = WhisperModel(
                mdir,
                device="cpu",
                compute_type="int8",
                cpu_threads=8,
                num_workers=1,
            )
        except Exception:
            # Deterministic stub mode
            self._stub = True

    def decode_segment(self, audio_bytes: bytes) -> Dict:
        if self._stub or self._model is None:
            text = "[ASR STUB] " + datetime.utcnow().strftime("%Y%m%dT%H%M%S")
            return {"text": text, "spans": [{"start_ms": 0, "end_ms": 20000, "text_start": 0, "text_end": len(text)}]}

        # Write bytes to a temporary file; faster-whisper accepts file path.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tf:
            tf.write(audio_bytes)
            tf.flush()
            # VAD: we still rely on faster-whisper internal vad_filter if available; external VAD is optional hint.
            try:
                segments, info = self._model.transcribe(
                    tf.name,
                    beam_size=1,
                    best_of=1,
                    vad_filter=True,
                    temperature=0.0,
                    language=None,  # autodetect
                )
            except Exception:
                # If decoding fails, return stub
                text = "[ASR STUB-DECODE] " + datetime.utcnow().strftime("%H%M%S")
                return {"text": text, "spans": [{"start_ms": 0, "end_ms": 20000, "text_start": 0, "text_end": len(text)}]}

        # Collect text and spans with char offsets
        pieces: List[str] = []
        spans: List[Dict] = []
        cursor = 0
        for seg in segments:
            seg_text = (seg.text or "").strip()
            if not seg_text:
                continue
            pieces.append(seg_text)
            start_ms = int(max(0.0, seg.start) * 1000)
            end_ms = int(max(0.0, seg.end) * 1000)
            text_start = cursor + (1 if cursor > 0 else 0)  # account for space join
            if cursor == 0:
                text_start = 0
            # compute end after we know total string
            spans.append({"start_ms": start_ms, "end_ms": end_ms, "text_start": text_start, "text_end": None})
            cursor = text_start + len(seg_text)
        text = " ".join(pieces).strip()
        # fix end offsets now that we know text assembly
        fix_cursor = 0
        for i, seg in enumerate(segments):
            seg_text = (seg.text or "").strip()
            if not seg_text:
                continue
            text_start = 0 if fix_cursor == 0 else fix_cursor + 1
            text_end = text_start + len(seg_text)
            spans[i]["text_start"] = text_start
            spans[i]["text_end"] = text_end
            fix_cursor = text_end
        if not text:
            text = "[ASR EMPTY]"
            spans = [{"start_ms": 0, "end_ms": self.cfg["asr"].get("segment_ms", 20000), "text_start": 0, "text_end": len(text)}]
        return {"text": text, "spans": spans}
