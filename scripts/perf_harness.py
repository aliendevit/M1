# path: scripts/perf_harness.py
from __future__ import annotations

import io
import math
import statistics
import time
import wave
from typing import Dict, Tuple

# Budgets
ASR_BUDGET_S = 3.0
EXTRACT_COMPOSE_BUDGET_S = 0.800


def _make_wav_bytes(duration_s: float = 2.0, sr: int = 16000, freq: float = 440.0) -> bytes:
    """Generate a small mono WAV sine burst for testing."""
    n = int(duration_s * sr)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(n):
            v = int(32767 * 0.2 * math.sin(2.0 * math.pi * freq * (i / sr)))
            w.writeframesraw(v.to_bytes(2, "little", signed=True))
    return buf.getvalue()


def _time_asr(runs: int = 3) -> Tuple[float, Dict]:
    from backend.services.asr_service import ASRService
    svc = ASRService.instance()
    wav = _make_wav_bytes()
    times = []
    last = {}
    for _ in range(runs):
        t0 = time.perf_counter()
        last = svc.decode_segment(wav)
        times.append(time.perf_counter() - t0)
    return statistics.median(times), last


def _time_extract_compose(runs: int = 5) -> Tuple[float, Dict]:
    from backend.services.extract_service import ExtractService
    from backend.services.compose_service import ComposeService
    span = {"text": "Patient reports chest pain for 2 hours with nausea. Exam: regular rate and rhythm, lungs clear."}
    facts = [
        {"kind":"lab","name":"Troponin I","value":"0.04 ng/mL","time":"2025-09-21T07:45","source_id":"obs/123"},
        {"kind":"lab","name":"Troponin I","value":"0.06 ng/mL","time":"2025-09-21T10:45","source_id":"obs/124"}
    ]
    times = []
    last = {}
    ext = ExtractService.instance()
    comp = ComposeService.instance()
    for _ in range(runs):
        t0 = time.perf_counter()
        V = ext.extract_visit(span, facts)["VisitJSON"]
        note = comp.compose_note(V, facts)
        times.append(time.perf_counter() - t0)
        last = note
    return statistics.median(times), last


def main():
    asr_med, asr_out = _time_asr()
    ec_med, _ = _time_extract_compose()
    print(f"ASR median finalize: {asr_med*1000:.0f} ms  — {'PASS' if asr_med <= ASR_BUDGET_S else 'FAIL'} (budget {ASR_BUDGET_S*1000:.0f} ms)")
    print(f"Extract+Compose median: {ec_med*1000:.0f} ms — {'PASS' if ec_med <= EXTRACT_COMPOSE_BUDGET_S else 'FAIL'} (budget {EXTRACT_COMPOSE_BUDGET_S*1000:.0f} ms)")
    if asr_out:
        print(f"ASR sample text: {asr_out.get('text','')[:80]}")

if __name__ == "__main__":
    main()
