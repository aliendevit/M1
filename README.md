





---


## README.md (drop into repo root)
```md
# MinuteOne (M1) — Offline‑first bedside side‑panel (MVP)


**Goal:** Save clinicians **≥5–10 minutes/encounter** and reduce handoff omissions by turning a bedside conversation into a **SOAP/MDM note**, **I‑PASS handoff**, and **bilingual discharge**, with **rule‑based plan suggestions**. **Deterministic‑first**, offline‑by‑default. A tiny local LLM (≈3B, 4‑bit) is used **only** to fill ambiguous JSON slots.


---


## ✨ Features (MVP)
- **ASR service**: faster‑whisper *small‑int8* + VAD; timestamped segments; lightweight diarization heuristic.
- **Extractor**: regex/rules for doses, frequencies, durations, negations; ontology maps (ASA→aspirin, “trops”→troponin). Tiny LLM fills **VisitJSON** strictly.
- **Chart cache + Evidence**: SQLite FHIR subset; builds **EvidenceChips** with deltas.
- **Composers**: Jinja2 templates for **Note (SOAP/MDM)**, **I‑PASS**, **Discharge** (EN + ES), each with citations.
- **Chips engine**: confidence score + bands A/B/C/D; batch‑accept hook.
- **Side‑panel UI**: PyQt tabs (**Note | Handoff | Discharge | Sources**), transcript pane, chips rail, keyboard‑first.
- **Audit & metrics**: local JSONL; session timers/keystrokes (stubs present).


---


## 🧱 Architecture
- **Backend**: FastAPI (local‑only), Pydantic v2 schemas, Jinja2 composers, SQLite (FTS5).
- **Models**: faster‑whisper small‑int8, Llama‑3.2‑3B‑Instruct Q4_K_S (llama.cpp).
- **UI**: PyQt side‑panel; chips rail; keyboard‑first controls.


---


## ⚙️ Requirements
- **OS**: Windows 10/11 (tested). macOS workable with minor tweaks.
- **Hardware**: Core i7‑1165G7 (16GB RAM, SSD). Optional GeForce MX350 (≈2GB VRAM) for `n_gpu_layers`.
- **Python**: 3.10+
- **Audio**: system microphone permissions enabled. `ffmpeg` accessible on PATH.


---


## 🔐 Privacy / Security (MVP)
- Offline by default; no PHI egress.
- Local SQLite cache (72h window) and JSONL logs under `data/`.
- (Planned) Auto‑lock on idle; signed builds; SBOM.


---


## 📦 Setup
1. **Clone & venv**
```bash
py -3.10 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
