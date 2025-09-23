# MinuteOne Runbook

## 1. Environment

- Python 3.12 (64-bit)
- CPU-only execution by default; adjust `config.yaml` if GPU layers are available.
- No outbound network access; models must be present locally.

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows
pip install -r requirements.txt
```

## 2. Seed the Evidence Cache

Load the synthetic demo bundle into the local SQLite cache:

```bash
python -m m1.scripts.ingest demo/patient_bundle.json
```

The script respects `cache.db` from `config.yaml` (default `data/m1_cache.sqlite`).

## 3. Launch Services

### API

```bash
uvicorn m1.api.main:app --reload --port 8000
```

Key endpoints:
- `GET /health` – service heartbeat
- `GET /facts/context` – evidence chips with lab deltas
- `POST /extract/visit` – VisitJSON extraction
- `POST /compose/*` – composition endpoints for note, handoff, discharge
- `POST /suggest/planpack` – guarded plan pack suggestions
- `POST /chips/resolve` – append chip audit log (JSONL at `audit.log`)
- `GET /metrics/session` – session metrics and thresholds

### Desktop UI

```bash
python -m m1.ui.app
```

Paste a transcript, tick consent, and compose artefacts. Use the export button to save Markdown, PDF, or RTF output. Keyboard shortcut `Ctrl+E` triggers extraction.

## 4. Models

- Place `llama-3.2-3b-instruct-q4_ks.gguf` at `models/` or update `config.yaml`.
- Optional faster-whisper model is configured as `faster-whisper-small`.

## 5. Maintenance

- Audit logs accumulate at `logs/chip_audit.jsonl`; rotate as needed.
- To reset demo data, delete the SQLite file and rerun the ingest script.
- Configurable weights and thresholds live under the `confidence` section of `config.yaml`.

## 6. Testing

Run automated tests before release:

```bash
pytest -q
```

Tests cover chip banding, VisitJSON validation, note citation rendering, and evidence delta computation.
