# MinuteOne (M1)

MinuteOne (M1) is an offline, edge-first clinical assistant designed to help inpatient clinicians convert bedside conversations into structured documentation. M1 assembles SOAP/MDM notes, I-PASS handoffs, bilingual discharge instructions, and guard-railed plan suggestions while keeping PHI on-device.

## Feature Highlights
- Offline-first pipeline with rule-centric extraction backed by a local llama-cpp fallback model.
- Deterministic composition using Jinja2 templates for notes, I-PASS, and discharge summaries.
- Evidence cache backed by SQLite with lab deltas and reusable chips.
- Safety guards that demand explicit overrides on uncertainty or risk detection.
- PyQt5 desktop client with keyboard-first chip confirmation and export to Markdown/PDF/RTF.
- Synthetic demo data and ingest utilities for evaluation.

## Quickstart

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
python -m m1.scripts.ingest demo/patient_bundle.json
uvicorn m1.api.main:app --reload
```

Launch the desktop UI when the API is running or in standalone mode:

```bash
python -m m1.ui.app
```

Run the demo bundle ingest first so that context chips and deltas are available in the cache.

### Testing

```bash
pytest -q
```

## Repository Structure
- `m1/api/main.py` - FastAPI service surface, singletons, and template helpers.
- `m1/extractor/llm.py` - Rule-driven visit extraction with llama-cpp fallback.
- `m1/evidence/sqlite_cache.py` - SQLite cache with FTS support and delta computation.
- `m1/chips/service.py` - Confidence scoring and chip banding logic.
- `m1/guards/service.py` - Guard policies enforcing conservative clinical behavior.
- `m1/ui/app.py` - PyQt5 application for note composition and export.
- `m1/templates/` - Deterministic Jinja2 templates for note, handoff, and discharge.
- `m1/asr/service.py` - faster-whisper transcription service.
- `m1/export/exporter.py` - PDF/RTF exporter shell.
- `m1/fhir/reader.py` - FHIR bundle reader helpers.
- `m1/config.py` - Layered configuration loader.
- `m1/defaults/config.yaml` - Packaged baseline configuration.
- `m1/fhir/slice.py` - FHIR R4 slicing helpers for bundle ingestion.
- `m1/planpacks/` - YAML plan packs curated for chest pain, seizure, and sepsis pathways.
- `demo/patient_bundle.json` - Synthetic bundle demonstrating troponin deltas.
- `tests/` - Unit tests covering chips, extraction, composition, and evidence deltas.

## Documentation
- `docs/RUNBOOK.md` - Operational runbook with command examples.
- `docs/SAFETY.md` - Guard policies and override expectations.
- `docs/MODEL.md` - LLM and ASR implementation notes.
- `docs/FHIR_SLICE.md` - FHIR slicing contract.
- `docs/CHANGELOG.md` - Release history.

## Safety and Privacy
MinuteOne never places orders automatically and never transmits PHI. Guards block high-risk actions until a clinician documents context and an override reason, with all interactions captured in the local audit log (see `logging.audit_log` in `config.yaml`). See `docs/SAFETY.md` for deeper guidance.

## Contributions & Extensibility
Plan packs, templates, and guard policies are declarative so that clinical teams can adjust workflows without modifying core code. Additional languages can be enabled by adding templates and updating `config.yaml`.
## Configuration

MinuteOne applies layered configuration so deployments inherit sane defaults while still allowing local overrides. Precedence from lowest -> highest is:

1. Bundled defaults `m1/defaults/config.yaml`
2. System config (`/etc/m1/config.yaml` or `%PROGRAMDATA%\m1\config.yaml`)
3. User config (`~/.config/m1/config.yaml` or `%APPDATA%\m1\config.yaml`)
4. Project config `./config.yaml`
5. File specified by `M1_CONFIG`
6. Environment variables prefixed with `M1_` (e.g. `M1_CACHE_DB`, `M1_LLM_THREADS`)

Use `M1_CACHE_DB` or `M1_LLM_THREADS` to override individual settings without editing files.
## API Routes
- `GET /health` - readiness probe.
- `POST /ingest` - transcribes and persists visit bundle.
- `POST /extract/visit` - returns structured VisitJSON.
- `GET /facts/context` - fetches cached clinical snippets.
- `POST /compose/note` - renders SOAP note template.
- `POST /compose/handoff` - renders I-PASS handoff template.
- `POST /compose/discharge` - renders discharge instructions (locale aware).
- `POST /suggest/planpack` - returns plan pack guidance.
- `POST /chips/resolve` - scores chips.
- `GET /evidence/{patient_id}` - retrieves structured evidence.
- `POST /export` - emits PDF/RTF artifacts.
- `GET /metrics/session` - lightweight telemetry stub.
