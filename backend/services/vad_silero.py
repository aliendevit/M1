# path: backend/services/vad_silero.py
from __future__ import annotations

import os
import struct
import threading
from typing import List, Tuple, Optional

class _SileroWrapper:
    def __init__(self, jit_path: str):
        import torch  # CPU build
        self.torch = torch
        self.model = torch.jit.load(jit_path, map_location="cpu")
        self.model.eval()

    def is_speech(self, pcm16: bytes, sample_rate: int = 16000) -> bool:
        # Minimal gate: run frame-wise and return majority vote (placeholder).
        # Real implementation would resample and chunk; we keep it simple.
        try:
            import numpy as np
            arr = np.frombuffer(pcm16, dtype=np.int16).astype("float32") / 32768.0
            # Model expects [batch, time]; details vary per silero export.
            with self.torch.no_grad():
                out = self.model(self.torch.tensor(arr).unsqueeze(0))
            p = float(out.squeeze().mean().item())
            return p > 0.5
        except Exception:
            return True

class _WebRTCVADWrapper:
    def __init__(self, aggressiveness: int = 2):
        import webrtcvad
        self.vad = webrtcvad.Vad(aggressiveness)

    def is_speech(self, pcm16: bytes, sample_rate: int = 16000) -> bool:
        # Evaluate on the first 30ms chunk if available; otherwise default True
        frame_dur_ms = 30
        nbytes = int(sample_rate * frame_dur_ms / 1000) * 2
        if len(pcm16) >= nbytes:
            return self.vad.is_speech(pcm16[:nbytes], sample_rate)
        return True

class VAD:
    """
    Unified VAD facade. Prefers Silero .jit from config, otherwise webrtcvad.
    This MVP exposes only a boolean `is_speech` gate used sparingly.
    """
    _instance: Optional["VAD"] = None
    _lock = threading.Lock()

    def __init__(self, impl):
        self._impl = impl

    @classmethod
    def from_config(cls, asr_cfg: dict) -> "VAD":
        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            jit_path = asr_cfg.get("vad_jit_path") or os.path.join("models", "asr", "silero_vad.jit")
            impl = None
            try:
                if os.path.exists(jit_path):
                    impl = _SileroWrapper(jit_path)
            except Exception:
                impl = None
            if impl is None:
                impl = _WebRTCVADWrapper(aggressiveness=2)
            cls._instance = VAD(impl)
            return cls._instance

    def is_speech(self, pcm16: bytes, sample_rate: int = 16000) -> bool:
        try:
            return bool(self._impl.is_speech(pcm16, sample_rate))
        except Exception:
            return True
