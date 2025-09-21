# MinuteOne (M1) — Offline-first bedside side-panel (MVP)

**Goal:** Save clinicians **≥5–10 minutes per encounter** and reduce handoff omissions by turning a bedside conversation into a **SOAP/MDM note**, **I-PASS handoff**, and **bilingual discharge** with **rule-based plan suggestions**. The system is **deterministic-first** and **offline by default**. A tiny local LLM (~3B, 4-bit) is used **only** to fill ambiguous VisitJSON slots.

---

## ✨ Features (MVP)
- **ASR service**: faster-whisper *small-int8* + VAD; timestamped segments; lightweight diarization heuristic.
- **Extractor**: regex/rules for doses, frequencies, durations, negations; ontology maps (ASA→aspirin, “trops”→troponin). Tiny LLM fills **VisitJSON** strictly when rules cannot.
- **Chart cache + Evidence**: SQLite FHIR subset; generates **EvidenceChips** with deltas, timestamps, and source IDs.
- **Composers**: Jinja2 templates for **Note (SOAP/MDM)**, **I-PASS**, **Discharge** (EN + ES), each with inline citations.
- **Chips engine**: confidence score + bands A/B/C/D; batch-accept hook for soft confirmations.
- **Side-panel UI**: PyQt tabs (**Note | Handoff | Discharge | Sources**), transcript pane, chips rail, keyboard-first interactions.
- **Audit & metrics**: local JSONL logs; session timers/keystrokes (stubs provided).

---

## 🧱 Architecture
- **Backend**: FastAPI (local-only), Pydantic v2 schemas, Jinja2 composers, SQLite (FTS5) cache.
- **Models**: faster-whisper small-int8 for ASR; Llama-3.2-3B-Instruct Q4_K_S via llama.cpp for ambiguous slot filling.
- **UI**: PyQt side-panel integrating transcript, chips rail, and export controls.

---

## ⚙️ Requirements
- **OS**: Windows 10/11 (primary). macOS supported with minor tweaks.
- **Hardware**: Intel Core i7-1165G7 (16 GB RAM, SSD). Optional GeForce MX350 (~2 GB VRAM) for partial GPU offload.
- **Python**: 3.10+
- **Audio**: Microphone permissions enabled; `ffmpeg` available on PATH.

---

## 🔐 Privacy & Security (MVP)
- Offline by default; no PHI egress without explicit toggle.
- Local SQLite cache (72 h window) and JSONL logs stored under `data/`.
- Planned hardening: auto-lock on idle, signed builds, SBOM distribution.

---

## 📦 Setup
1. **Clone & create a virtual environment**
   ```bash
   git clone https://github.com/minuteone/m1.git
   cd m1
   py -3.10 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt  # add requirements-optional.txt for the full local stack
   ```

   _macOS/Linux_
   ```bash
   python3.10 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt  # add requirements-optional.txt for the full local stack
   ```

2. **Download runtime models**
   - Place the quantized **faster-whisper small-int8** model under `models/asr/` (or update `config.yaml`).
   - Place the **Llama-3.2-3B-Instruct Q4_K_S** GGUF file under `models/`.

3. **Configure the app**
   - Edit `config.yaml` to point to local model paths and data directories.
   - Adjust ASR, LLM, pathway, and privacy settings to match the deployment target.

4. **Launch the backend**
   ```bash
   uvicorn m1.api.main:app --reload --host 127.0.0.1 --port 8000
   ```
   - Exposes local FastAPI endpoints (`/asr/segment`, `/extract/visit`, etc.).

5. **Launch the side-panel UI**
   ```bash
   python -m m1.ui.app --config config.yaml
   ```
   - Opens the PyQt panel with tabs (**Note | Handoff | Discharge | Sources**) and the chips rail.

6. **(Optional) Run smoke tests**
   ```bash
   pytest
   ```
   - Validates regex extractors, schema guards, and composer templates once implemented.

---

## 🗂 Project Layout
- `m1/api/main.py` — FastAPI app exposing `/asr`, `/extract`, `/compose`, `/suggest`, and `/metrics` endpoints.
- `m1/extractor/service.py` — deterministic extractor turning transcripts into VisitJSON.
- `m1/composer/service.py` — Jinja2-based composers for note, handoff, and discharge artifacts.
- `m1/planpacks/` — YAML rule packs (chest pain, seizure, sepsis) with guard evaluation helpers.
- `m1/chips/service.py` — confidence computation and chip scaffolding.
- `m1/evidence/cache.py` — lightweight chart cache + EvidenceChip helpers.
- `tests/` — unit coverage for config validation, extraction, templates, and plan packs.

All modules prefer deterministic rules and surface uncertainty as chips, matching the MVP constraints.

---

## 🛠 Development Notes
- **Data folders**: `data/` contains the SQLite cache and log output; ensure disk encryption.
- **Templates & plan packs**: stored under `templates/` and `planpacks/`; version via Git tagging.
- **Model paths**: configurable per site; distribute via offline installers.
- **Optional dependencies**: install `requirements-optional.txt` when running the full ASR/LLM stack locally.

## 📚 Additional Documentation
- `docs/RFP.md` — full Software Requirements & RFP pack ready to share with vendors.

---

## 📄 Licensing & Compliance
- Ship with HIPAA/GDPR-ready documentation (BAA/DPA templates).
- Provide SBOM, signed binaries, and vulnerability disclosure policy.
