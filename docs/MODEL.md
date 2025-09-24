# Model Notes

## Extractor
- Rule-driven heuristics identify problems, medications, vitals, and plan statements.
- Placeholder for llama-cpp model defined in `config.yaml` (`llm.path`).

## ASR
- `m1.asr.transcriber.Transcriber` stubs a faster-whisper integration point.

## Templates
- Deterministic Jinja2 templates produce SOAP, I-PASS, and discharge documents.

## Future Work
- Swap heuristic extractor with on-device llama.cpp runtime.
- Implement structured override logging for guard bypass events.
- Extend multilingual discharge instructions with localized templates.
