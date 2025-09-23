# MinuteOne (M1)

MinuteOne (M1) is an offline-first clinical assistant that turns bedside conversations into structured documentation: SOAP/MDM notes, I-PASS handoffs, bilingual discharge instructions, and conservative plan pack suggestions. The project targets Python 3.12 and runs entirely on local hardware so protected health information never leaves the device.

## Quickstart

```bash
python -m venv .venv
. .venv/Scripts/activate  # On Windows; use `source .venv/bin/activate` on Unix
pip install -r requirements.txt
python -m m1.scripts.ingest demo/patient_bundle.json
uvicorn m1.api.main:app --reload --port 8000
```

Launch the desktop UI in a second terminal:

```bash
python -m m1.ui.app
```

Run the full test suite:

```bash
pytest -q
```

## Features

- **Offline by default**: llama.cpp and faster-whisper load local models only; no external requests.
- **Deterministic composition**: Jinja2 templates combine structured extraction with cached evidence.
- **Evidence-aware chips**: Confidence bands (A–D) ensure clinicians stay in control.
- **Safety guards**: Renal, bleeding, pregnancy, allergy, and anticoagulant checks gate plan suggestions.
- **Audit ready**: Chip resolutions append to a JSONL audit log.
- **Export tools**: Markdown, PDF, and RTF exports for every composed artefact.

## Repository Layout

- `m1/api/main.py` – FastAPI service exposing extraction, composition, plan packs, metrics, and audit endpoints.
- `m1/extractor/llm.py` – Rule-first extractor with optional llama.cpp refinement returning strict Pydantic models.
- `m1/evidence/sqlite_cache.py` – SQLite cache with lab delta computation and evidence chip helpers.
- `m1/chips/service.py` – Confidence math and banding utilities.
- `m1/guards/service.py` – Safety guard evaluations.
- `m1/templates/` – Jinja2 templates for note, handoff, and discharge artefacts.
- `m1/ui/app.py` – PyQt5 desktop UI with keyboard-focused chips rail.
- `m1/export/exporter.py` – Markdown, PDF, and RTF export helpers.
- `m1/scripts/ingest.py` – Demo data ingestion into the local cache.
- `demo/` – Synthetic FHIR-like bundle for tutorials and tests.
- `tests/` – Deterministic pytest suite covering chips, extraction, composition, and evidence deltas.

## Roadmap

- Expand guard coverage with configurable thresholds and override UX.
- Integrate local ASR pipeline when hardware allows faster-whisper initialization.
- Add end-to-end perf harness for CPU-only clinics.

See `docs/` for the runbook, safety policies, model guidance, and change log.
