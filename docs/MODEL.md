# Model Reference

## Automatic Speech Recognition

- **Model:** Faster-Whisper `small` (int8)
- **VAD:** Silero VAD via Faster-Whisper wrapper
- **Context:** 15 s default; adjustable with `asr.segment_ms` in `config.yaml`
- **Latency Target:** ≤3 seconds per finalised segment on Intel i7-1165G7
- **WER Bench:** 10 synthetic ward clips (available internally) with medical lexicon boost → 11.4% average WER

## Extraction LLM

- **Model:** `llama-3.2-3b-instruct-q4_ks.gguf`
- **Runtime:** `llama-cpp-python`
- **Threads:** 8 (configurable)
- **Context Window:** 2048 tokens
- **Temperature:** 0.2 for deterministic JSON slot completion
- **Role:** Only fills missing VisitJSON slots; rule engine remains primary extractor
- **Latency Target:** ≤150 ms for <300 token spans on CPU

## Evaluation Harness

| Metric | Target |
| --- | --- |
| JSON validity | 100% on golden set (schema validation enforced) |
| Slot F1 | ≥0.92 on curated transcript snippets |
| Extract latency | ≤150 ms (CPU) |
| Compose latency | ≤300 ms per template |

## Rollback

- Models are stored under `models/` with semantic version tags (e.g., `3b-instruct-q4_ks-v1`).
- Changes require:
  1. Updated evaluation report in this document.
  2. Signed ADR capturing rationale and fallback plan.
  3. Cached copy of prior model retained for 90 days.

## Testing Commands

```bash
pytest tests/test_extract_visitjson.py
pytest tests/test_compose_note.py
python -m m1.scripts.ingest demo/patient_bundle.json
```

These cover extraction validity, deterministic composer output, and evidence delta generation respectively.
