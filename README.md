# MinuteOne (M1)

Offline-first clinical side-panel that turns a bedside conversation into a SOAP/MDM note, an I-PASS handoff, and a bilingual discharge summary while surfacing safe, rules-driven plan suggestions. The stack is designed for pilot deployments on commodity laptops with no cloud dependency, favouring deterministic templates and evidence-backed automation.

---

## ✨ Key capabilities
- **Edge ASR service** – wraps Faster-Whisper *small-int8* with simple VAD segmentation and diarisation heuristics so segments finalise under three seconds.
- **Hybrid VisitJSON extractor** – regex/rules drive 90% of slot filling; a local 3B llama.cpp model backfills missing fields only when enabled.
- **SQLite chart cache + EvidenceChips** – ingests FHIR bundles, computes ± deltas for labs/vitals, and tags every factual sentence with a citation.
- **Deterministic composers** – Jinja2 templates for SOAP/MDM notes, I-PASS handoffs, and discharge instructions (English + Spanish) with “Missing:” chip hints.
- **Plan packs & guardrails** – YAML pathways (chest pain, seizure, sepsis) that run through allergy/bleed/pregnancy/renal/anticoag checks before surfacing suggestions.
- **Chips engine** – confidence scoring (bands A–D), batch accept, and keyboard shortcuts so clinicians can clear uncertainty without leaving the keyboard.
- **Side-panel UI** – PyQt scaffold with Note | Handoff | Discharge | Sources tabs, consent banner, chip rail placeholder, and export hooks.
- **Audit & metrics** – local JSONL logging for consent, chip resolution, and compose events plus time-saved/keystroke counters.

---

## 🏗 Architecture overview
```
Transcript  ──▶  /asr/segment  ──▶  Evidence cache (SQLite + FTS5)
               │                    ▲
               ▼                    │
          /extract/visit        /facts/context
               │                    │
               ▼                    │
          VisitJSON ────────────────┘
               │
               ▼
      /compose/* + /suggest/planpack  ──▶  chips/export/UI
```
- `FastAPI` serves all local endpoints (see [API surface](#-api-surface)).
- `pydantic` schemas enforce deterministic VisitJSON contracts and plan responses.
- `sqlite-utils` powers ingestion & FTS5 indexes for quick evidence lookups.
- `llama-cpp-python` and `faster-whisper` are optional extras: the code falls back to deterministic shims when the heavy models are unavailable (e.g., CI).

---

## 📁 Repository layout
| Path | Purpose |
| ---- | ------- |
| `m1/api/main.py` | FastAPI application exposing ASR, extraction, composition, plan packs, chips, and export endpoints. |
| `m1/asr/service.py` | Faster-Whisper wrapper with deterministic text fallback and diarisation heuristic. |
| `m1/extractor/llm.py` | Rule-first extractor with optional llama.cpp JSON fill. |
| `m1/evidence/sqlite_cache.py` | SQLite-backed FHIR cache + EvidenceChips and delta helpers. |
| `m1/composer/service.py` | Renders note, handoff, and discharge templates with citation metadata. |
| `m1/planpacks/*.yaml` | Chest pain, seizure, and sepsis pathway definitions. |
| `m1/ui/app.py` | PyQt launcher (headless-friendly) for the side-panel scaffold. |
| `m1/scripts/ingest.py` | CLI to initialise the SQLite cache and ingest demo bundles. |
| `tests/` | Unit and golden tests covering chips, extraction, composers, and evidence deltas. |
| `docs/` | RFP, runbook, model notes, safety catalogue, and vendor prompt. |

---

## 🚀 Quick start
1. **Clone & create a virtual environment**
   ```bash
   git clone https://github.com/minuteone/m1.git
   cd m1
   python3 -m venv .venv          # use `py -3.10 -m venv .venv` on Windows
   source .venv/bin/activate      # or `.venv\\Scripts\\activate`
   pip install -r requirements.txt
   ```
   Optional extras (ASR/LLM/UI stack):
   ```bash
   pip install -r requirements-optional.txt
   ```

2. **Download local models**
   - Faster-Whisper *small-int8*: place under `models/asr/` or update `config.yaml`.
   - `llama-3.2-3b-instruct-q4_ks.gguf`: place under `models/llm/`.

3. **Seed the evidence cache** (optional demo data)
   ```bash
   python -m m1.scripts.ingest demo/patient_bundle.json --db data/chart.sqlite
   ```

4. **Run the FastAPI service**
   ```bash
   uvicorn m1.api.main:app --host 127.0.0.1 --port 8000
   ```

5. **Launch the side panel**
   ```bash
   python -m m1.ui.app --config config.yaml        # GUI launch
   python -m m1.ui.app --config config.yaml --headless   # config validation only
   ```

6. **Execute the test suite**
   ```bash
   pytest
   ```

---

## ⚙️ Configuration (`config.yaml`)
Key fields mirror the MVP spec:

- `asr`: Faster-Whisper model ID/path, VAD backend, and segment size.
- `llm`: llama.cpp GGUF path and runtime parameters (threads, ctx, GPU layers, temperature).
- `cache`: SQLite DB path and evidence window (hours).
- `confidence`: weights/thresholds/risk bumps for chip banding.
- `localization`: discharge languages and default locale.
- `pathways`: enabled plan packs.
- `privacy`: offline toggle, log retention days, idle auto-lock.

The schema is validated via `m1.config.AppConfig`; misconfigured fields raise immediately when the API or UI loads.

---

## 🔌 API surface
All endpoints are local-only by default:

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/asr/segment` | Accepts base64 audio or plaintext; returns transcript text + spans. |
| `POST` | `/extract/visit` | Turns transcript snippets into VisitJSON plus slot confidence scores. |
| `GET` | `/facts/context` | Returns recent EvidenceChips from the SQLite cache. |
| `POST` | `/compose/note` | Renders SOAP/MDM markdown with citation metadata. |
| `POST` | `/compose/handoff` | Produces I-PASS markdown + citations. |
| `POST` | `/compose/discharge` | Builds bilingual discharge instructions. |
| `POST` | `/suggest/planpack` | Evaluates a plan pack with guard checks. |
| `POST` | `/chips/resolve` | Logs chip resolution events (action/value/reason). |
| `POST` | `/export` | Saves note/handoff/discharge as Markdown, PDF, and RTF. |

See `docs/RUNBOOK.md` for smoke-test curl commands and operational tips.

---

## 📦 Evidence, chips, and plan packs
- Evidence ingestion supports FHIR bundles/NDJSON; deltas are calculated for ≥3 labs by default (see `tests/test_evidence_deltas.py`).
- Chips use the scoring formula `0.35*rule_hit + 0.25*p_llm + 0.15*c_asr + 0.10*s_ont + 0.15*s_ctx` with risk bumpers described in `docs/SAFETY.md` and verified in `tests/test_chips_bands.py`.
- Guard evaluation lives in `m1/guards/service.py`; blocked suggestions require an override reason which is captured in the audit log.

---

## 📚 Further documentation
- `docs/RFP.md` – vendor-ready requirements pack.
- `docs/RUNBOOK.md` – install/run offline, mic setup, troubleshooting.
- `docs/SAFETY.md` – guard catalogue and override expectations.
- `docs/MODEL.md` – ASR/LLM versions, quantisation notes, evaluation harness.
- `docs/CHANGELOG.md` – template/plan pack/config version history.

For roadmap changes or ADRs, document decisions in `docs/` and keep templates deterministic with updated golden tests.

---

## ✅ Testing philosophy
- `pytest` covers deterministic chips, composers, extraction, and evidence deltas.
- ASR/LLM heavy paths are guarded so tests run without model downloads.
- Integration smoke tests are documented in the runbook; add golden files for new templates or pathways before shipping.

---

MinuteOne aims to save ≥5 minutes per encounter, hit I-PASS ≥95%, and keep every factual line cited—all while staying private-by-default on the edge. Contributions should preserve those guardrails.
