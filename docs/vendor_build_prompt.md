# MinuteOne (M1) — Vendor Build Order (Missing Pieces & What To Create)

**Operate like a top-tier health-AI org.** Privacy-first, offline-first, deterministic by default. Success is measured by **minutes saved per encounter** and **I-PASS completeness**—not by model size.

---

## 0) Artifacts you must use

Download and integrate this bundle (place contents in the repository root):

**➡️ `M1-missing-files.zip`** — available at `sandbox:/mnt/data/M1-missing-files.zip`

Contents (new modules):

* `m1/asr/service.py` – faster-whisper small (int8) ASR wrapper + simple VAD
* `m1/extractor/llm.py` – llama-cpp integration for **Llama-3.2-3B-Instruct (Q4)** → strict VisitJSON
* `m1/evidence/sqlite_cache.py` – SQLite FHIR cache (FTS5) + EvidenceChips/deltas
* `m1/export/exporter.py` – Markdown save + PDF/RTF exporters
* `m1/guards/service.py` – guard checks (allergy, bleed, pregnancy, renal, anticoag)
* `m1/fhir/reader.py` – simple FHIR bundle/NDJSON loader
* `m1/ui/app.py` – minimal PyQt side-panel (Note/Handoff/Discharge tabs, chips rail)
* `tests/test_chips_bands.py` – confidence→band unit test
* `MISSING_FILES_MANIFEST.json` – file manifest

---

## 1) Build targets

### A. FastAPI endpoints (wire the modules)

Implement or complete these local endpoints:

```
POST /asr/segment        -> feed audio chunks to ASR; return {text, ts_start, ts_end}
POST /extract/visit      -> use rules + LLM (llama-cpp) to return VisitJSON (+ slot_scores)
GET  /facts/context      -> read from SQLite cache; return recent labs/vitals/notes (≤72h)
POST /compose/note       -> Jinja2 → SOAP/MDM markdown + citations
POST /compose/handoff    -> I-PASS JSON with timers for pending items
POST /compose/discharge  -> Markdown (EN + chosen 2nd language) from templates
POST /suggest/planpack   -> apply YAML pathway + guards; return suggestions/guard_flags
POST /chips/resolve      -> persist chip resolution events in local audit log
```

**Acceptance:**

* VisitJSON is schema-validated
* Every non-subjective sentence has citation IDs from `EvidenceChips`
* Extract+Compose refresh ≤ **800 ms**

### B. ASR streaming

* Use `m1/asr/service.py` with **faster-whisper small (int8)** + VAD.
* Add a lightweight doctor/patient diarization heuristic.
* Provide both `transcribe_file()` (tests) and `/asr/segment` (streaming chunks).

**Acceptance:** segment finalize ≤ **3 s**; validate on 10 sample clips.

### C. Tiny LLM extraction

* Use `m1/extractor/llm.py` with **llama-cpp-python** and **Llama-3.2-3B-Instruct Q4**.
* Function-calling prompt → **strict VisitJSON** validated by Pydantic.
* No free prose; ambiguous slots → null/[]; return per-slot confidence.

**Acceptance:** 100% valid JSON on golden set; average call **≤150 ms** for short spans.

### D. SQLite FHIR cache + EvidenceChips

* Replace in-memory cache with `m1/evidence/sqlite_cache.py`.
* Implement init, ingest (FHIR bundle or NDJSON), and delta computation.
* `/facts/context?window=72h` returns chips such as:

```json
{"kind":"lab","name":"Troponin I","value":"0.04 ng/mL","delta":"↔","time":"...","source_id":"obs/123"}
```

**Acceptance:** ingest demo bundle; produce deltas (↔/±X) for ≥3 lab names.

### E. Chips engine + UI rail

* Apply scoring `c = 0.35*rule_hit + 0.25*p_llm + 0.15*c_asr + 0.10*s_ont + 0.15*s_ctx`.
* Bands: A≥0.90 Auto ✅, B 0.70–0.89 gray ●, C 0.45–0.69 yellow ▲, D<0.45 or guard-unknown red ■.
* Implement batch accept for ≥3 similar B chips; keyboard controls (Enter/1/2/3/E).

**Acceptance:** Single transcript yields at least one B, one C, one D chip with working keyboard flow.

### F. Plan Packs + Guards

* Enforce guards from `m1/guards/service.py` (allergy, bleed, pregnancy, renal, anticoag).
* Guard unresolved/failed → D red chip; override requires reason; log overrides.
* Ship 3 pathways: chest pain, seizure, sepsis.

**Acceptance:** Blocked suggestions require override reason; reasons logged.

### G. Exports

* Integrate `m1/export/exporter.py` for MD/PDF/RTF exports from Note view.
* Add Copy buttons for Note/Handoff/Discharge outputs.

**Acceptance:** Generate three files; openable/legible; filenames include timestamp.

### H. Consent & audit

* Consent banner before ASR; record choice in audit log.
* Log chip resolutions (before/after, evidence IDs), model versions, timestamps.

**Acceptance:** Local log JSON lines show `consent`, `compose`, and `chip_resolved` events.

---

## 2) Environment & dependencies

Target hardware: Intel Core i7-1165G7, 16 GB RAM, SSD (MX350 optional).

Add to `requirements.txt`:

* `faster-whisper`
* `llama-cpp-python`
* `pydantic>=2`
* `reportlab`
* `PyQt5`
* `uvicorn`
* `fastapi`
* `numpy`
* `python-multipart`

Model paths (local storage):

* ASR: faster-whisper small (int8)
* LLM: `models/llm/llama-3.2-3b-instruct-q4_ks.gguf`

---

## 3) Non-functional & safety guardrails

* Offline by default; no PHI egress.
* Performance targets: ASR ≤3 s/segment; Extract+Compose ≤800 ms.
* Accessibility: WCAG AA, keyboard-first, chip color + shape cues.
* Never auto-order; suggestions only.
* Every non-subjective sentence must have a citation.

---

## 4) Sprint deliverables (end of Sprint 2)

1. Running local app (FastAPI + PyQt) showing:
   * Transcript → Note/Handoff/Discharge with citations
   * Chips rail (B/C/D) with batch accept & keyboard flow
   * Plan packs with guards (blocked items require override + reason)
   * Exports to MD/PDF/RTF
2. Source code + `requirements.txt` + example `config.yaml`
3. Demo datasets + ingest script
4. Passing tests:
   * `tests/test_chips_bands.py`
   * Golden-file pipeline test (transcript → VisitJSON → Note markdown)
   * EvidenceChips delta test (≥3 labs)
5. Short pilot guide (1–2 pages) covering runbook, measurement, feedback capture

---

## 5) Timeline & definition of done

* **Sprint 1 (2 weeks):** ASR streaming; LLM extraction; SQLite cache; Compose Note/Handoff/Discharge; citations; guards.
* **Sprint 2 (2 weeks):** Chips rail polish; exports; consent & audit; tests; packaging.

**DoD (pilot-ready):**

* Median ≥5 min saved per encounter across 20-encounter dry run (timer + keystrokes)
* WER ≤12% on 10-clip sample
* I-PASS completeness ≥95%
* All outputs cited; no PHI egress; crash-safe autosave

---

Share this prompt directly with the vendor to align scope, missing files, build tasks, and acceptance criteria.
