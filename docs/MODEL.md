# Model Notes

MinuteOne is designed to run with small, local models so clinics can deploy on edge hardware without connectivity.

## LLM Extraction

- **Engine**: `llama-cpp-python`
- **Model**: `llama-3.2-3b-instruct-q4_ks.gguf`
- **Context**: 2048 tokens
- **Threads**: configurable (default 4)
- **Temperature**: 0.0 (deterministic)
- **Usage**: Only invoked when rule-based heuristics cannot fully populate the VisitJSON schema.
- **Fallback**: If the GGUF file is missing or llama.cpp fails, the extractor returns a minimal valid VisitJSON built from deterministic rules. Warning logs note the degraded mode.

## ASR (Optional)

- **Engine**: `faster-whisper` small model (int8)
- **VAD**: simple energy-based gate (mean squared amplitude)
- **Status**: The UI works without ASR; initialization is optional and logged.

## Evidence Cache

- SQLite database with FTS5-backed notes table.
- Deltas computed on ingest by comparing sequential lab results per code.
- Designed to ingest FHIR-like bundles for pilots without demanding a full EHR interface.

## Evaluation Hooks

- Template outputs are deterministic from the VisitJSON input and evidence chips.
- Tests enforce schema conformance and citation rendering (see `tests/`).
- Performance profiling can reuse the deterministic pytest suite and the ingest script for repeatable benchmarks.

## Deployment Considerations

- Runbook assumes CPU-only; GPU acceleration is optional if llama.cpp detects CUDA/Metal.
- Model paths are configurable via `config.yaml` so installers can bundle quantized files alongside the app.
- Keep models within institutional approved storage; do not mount network drives that sync PHI outside the site.
