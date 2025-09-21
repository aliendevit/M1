# MinuteOne (M1) — Request for Proposal & Full Requirements

## 0) Executive Summary

- **Objective:** Deliver a lightweight, edge-first AI side-panel that saves doctors 5–20 minutes per encounter by turning a single bedside conversation into a structured **SOAP/MDM note**, **I-PASS handoff**, and **bilingual discharge**, with safe, rule-based **plan suggestions**—all **offline by default**.
- **Approach:** Deterministic first (regex/rules/templates); a **tiny local LLM (~3B, 4-bit)** only for slot-filling & disambiguation into strict JSON. Every non-subjective sentence must have a **citation** to chart data ("evidence chips").
- **Primary setting:** Hospital medicine & ED; extensible to outpatient/telehealth.
- **Outcome:** Reduce documentation/coordination time, improve handoff completeness, and cut "pajama time."

---

## 1) Scope & Goals

### 1.1 In-scope MVP (pilot-ready)

- **Ambient capture** (with consent) → **Note (SOAP/MDM)**, **I-PASS handoff**, **Discharge** (EN + 1 other language).
- **Plan Packs** (rules; suggestions only) for **Chest pain**, **Seizure**, **Sepsis**.
- **Evidence chips** for vitals/labs/imaging/notes; inline citations in outputs.
- **Confidence-based chips** (Auto/Soft/Must/Blocked) to resolve uncertainty quickly.

### 1.2 Success criteria (must be proven in pilot)

- **Time saved:** median ≥ **5–10 minutes/encounter** (timer + keystroke delta).
- **ASR quality:** WER ≤ **12%** on ward noise with medical lexicon boost.
- **Safety/completeness:** checklist coverage ≥ **95%** on target pathways.
- **Handoff quality:** I-PASS completeness ≥ **95%**.
- **Trust:** Every factual sentence has an evidence link; edit burden acceptable (NPS ≥ +30).

### 1.3 Out of scope (MVP)

- Auto-placing orders; autonomous clinical decisioning; research-only models; cloud-only dependence.

---

## 2) Users & Personas

- **Primary:** Physicians (hospitalists/ED/urgent care/outpatient), NPs/PAs/Residents.
- **Team:** Nurses/MAs (timed task clarity), Pharmacists (guard checks), Lab/Imaging techs (timers), Schedulers (follow-ups), Coding/Compliance (MDM tally), QA/Safety (handoff metrics), IT/EHR analysts (interop).

---

## 3) System Overview (must deliver these modules)

1. **ASR Service (Edge)** — faster-whisper small (int8), VAD, light diarization.
2. **Extractor** — regex/rules + tiny local LLM (3B q4) → **VisitJSON** (strict schema).
3. **Ontology Mapper** — SNOMED/RxNorm synonym tables + fuzzy typo catcher.
4. **Chart Cache** — SQLite FHIR subset (last 48–72h) + FTS5 full-text.
5. **Evidence Engine** — deltas & timestamps → **EvidenceChips**.
6. **Composer** — Jinja2 templates → **SOAP/MDM**, **I-PASS**, **Discharge**.
7. **Plan Packs** — YAML rules for suggestions; guard-checked; never auto-order.
8. **Chips Engine** — confidence bands, chip UI/UX with keyboard flow.
9. **UI Side-Panel** — PyQt/Flutter; keyboard-first; sits next to the EHR.
10. **Consent/Privacy** — ambient banner; offline default; PHI redaction toggle.
11. **Audit & Metrics** — local logs (events, versions), time/quality dashboards.

---

## 4) Functional Requirements

### 4.1 ASR (on device)

- **Model:** faster-whisper **small (int8)**; Silero VAD; punctuation & basic medical lexicon boost.
- **Output:** timestamped text; basic speaker turns (doctor/patient heuristic).
- **Latency:** segment finalize ≤ **3 s**.

### 4.2 Extraction (hybrid: rules + tiny LLM)

- **Goal:** Fill **VisitJSON** slots. Rules first; LLM only for ambiguous phrases.
- **LLM:** **Llama-3.2-3B-Instruct**, **Q4** GGUF via llama.cpp (CPU; partial GPU offload optional).
- **Contract:** Strict JSON; function-calling style; schema validation mandatory.
- **No free prose**; no facts beyond transcript + chart facts.

**VisitJSON schema (minimum)**

```json
{
  "chief_complaint": "string",
  "hpi": {
    "onset": "string|null",
    "quality": "string|null",
    "modifiers": ["string"],
    "associated_symptoms": ["string"],
    "red_flags": ["string"]
  },
  "exam_bits": {"cv":"string|null","lungs":"string|null"},
  "risks": ["string"],
  "plan_intents": [
    {
      "type": "lab_series|test|med_admin|education",
      "name": "string",
      "dose": "string|null",
      "schedule": ["string"]
    }
  ],
  "language_pref": "string|null"
}
```

### 4.3 Chart Cache & Evidence

- **Data:** Patient, Encounter, Observation (vitals/labs), Condition, Medications, ImagingStudy/Procedure, DocumentReference.
- **Store:** SQLite (FTS5). Window default 72h.
- **EvidenceChip:**

```json
{"kind":"lab|vital|note|image","name":"Troponin I","value":"0.04 ng/mL","delta":"↔","+/-X","time":"2025-09-21T07:45","source_id":"obs/123"}
```

### 4.4 Composer (templates, deterministic)

- **Outputs:**
  - **Note (SOAP/MDM)** with inline citations; “Missing:” chips if required elements absent.
  - **I-PASS handoff** (Illness severity, Summary, Action list, Pending/timers, Contingency, Synthesis).
  - **Discharge**: EN + 1 additional language; plain-language strings; teach-back checklist.
- **Render time:** < **300 ms** per refresh.

### 4.5 Plan Packs (rules; suggestions only)

- **Format:** YAML; guard-checked (allergies/renal/pregnancy/bleeding).
- **Example (Chest pain low/intermediate):**

```yaml
pathway: chest_pain_low_intermediate
guards:
  - require_absent: ["active_bleed"]
  - check_allergy: ["aspirin"]
suggest:
  labs: [{name:"Troponin", schedule:["now","+3h","+6h"]}]
  tests: [{name:"ECG", at:"06:00"}]
  meds: [{drug:"Aspirin", dose:"325 mg", route:"PO", when:"now", guard:"no_allergy"}]
  education: [{topic:"chest_pain_low_risk", language:"{{ patient.language_pref|default('en') }}"}]
```

- **Never auto-orders**; blocked if guards unresolved.

### 4.6 Chips Engine (confidence & UX)

- **Confidence:** `c = 0.35*rule_hit + 0.25*p_llm + 0.15*c_asr + 0.10*s_ont + 0.15*s_ctx`.
- **Bands:** A ≥0.90 Auto, B 0.70–0.89 Soft, C 0.45–0.69 Must, D <0.45/guard-unknown Blocked.
- **Risk bumpers:** +0.05 high-risk, +0.03 medium.
- **Chip types:** Value / Missing / Guard / Ambiguity / Timer / Unit.
- **Keyboard:** Enter accept B, numbers choose options, E evidence, Esc dismiss B.
- **Batch accept:** ≥3 similar B chips → “Accept all (Enter)”.

### 4.7 UI Side-Panel

- **Tabs:** **Note | Handoff | Discharge | Sources**; chips rail on right.
- **Consent gate** before recording.
- **One-screen finalize** view with all 3 artifacts & Export (MD/RTF/PDF).

### 4.8 Export & Interop

- **MVP:** copy/paste + MD/RTF/PDF export.
- **Read-only FHIR** (if available): pull vitals/labs/problems/meds/notes.
- **Future (optional):** SMART on FHIR launch; write-back endpoints via governance.

---

## 5) Non-Functional Requirements

### 5.1 Performance

- ASR finalize ≤ 3 s/segment; Extract+Compose ≤ 800 ms; UI actions < 100 ms; cold start ≤ 20 s.

### 5.2 Reliability & Offline

- Full offline mode; degrade gracefully if cache absent; autosave drafts every 10 s; crash-safe restore.

### 5.3 Security & Privacy

- **Offline by default**; no PHI egress without toggle.
- OS disk encryption; secure local storage; redact logs; secure crash dumps.
- Signed updates; SBOM provided; supply-chain scanning policy.

### 5.4 Accessibility

- WCAG AA contrast; color + shape cues; keyboard-first.

---

## 6) Compliance, Governance & Risk

### 6.1 Regulatory

- HIPAA (BAA) & GDPR (DPA). Provide DPIA template and data classification matrix.
- **Clinical decision support boundary:** assistive, not autonomous; no medical device claims in MVP.

### 6.2 Security Architecture

- Threat model (STRIDE) + mitigations.
- SAST/DAST, dependency scan; vulnerability SLAs.
- Secrets in OS keychain; config encryption; audit log tamper-evident.

### 6.3 Identity & Access

- MVP: local roles (Clinician, Pilot Admin).
- Enterprise option: SSO (SAML/OIDC), session timeout, device policy.

### 6.4 Data Governance

- Model/rules/templates versioning; provenance and rollback.
- Code set mappings (LOINC/SNOMED/RxNorm) policy & cadence.
- Optional de-identification for analytics; re-identification controls.

### 6.5 Model Governance

- Evaluation harness, golden datasets, seed & determinism policy.
- Drift checks and re-eval cadence; rollback plan; model cards.

### 6.6 Clinical Safety

- Guard catalogs + override policy (reason required; logged).
- I-PASS completeness scoring & alert thresholds; near-miss capture.
- Human-factors/usability testing protocol.

---

## 7) Technical Environment

### 7.1 Target hardware (reference)

- **Laptop:** Intel **i7-1165G7**, 16 GB RAM, SSD.
- **GPU:** GeForce **MX350** (~2 GB VRAM) optional partial offload; CPU-only acceptable.

### 7.2 Runtime & Models

- **ASR:** faster-whisper small (int8).
- **LLM:** **Llama-3.2-3B-Instruct** Q4 (GGUF, llama.cpp). ctx=2048, threads 6–8, n_gpu_layers 6–12 if available, temp 0.2–0.4.
- **Embeddings (optional):** E5-small int8 for tie-breaks.
- **DB:** SQLite (FTS5).
- **Backend:** FastAPI; **UI:** PyQt or Flutter.

### 7.3 Configuration (example `config.yaml`)

```yaml
asr: {model: faster-whisper-small-int8, vad: silero}
llm: {path: models/llama-3.2-3b-instruct-q4_ks.gguf, threads: 8, ctx: 2048, n_gpu_layers: 8, temperature: 0.2}
cache: {window_hours: 72, db: data/chart.sqlite}
confidence:
  weights: {rule_hit:0.35, p_llm:0.25, asr:0.15, ontology:0.10, context:0.15}
  thresholds: {auto_accept:0.90, soft_confirm:0.70, must_confirm:0.45}
  risk_bumps: {high:0.05, medium:0.03}
localization: {discharge_languages: ["en","es"]}
pathways: {enabled: ["chest_pain","seizure","sepsis"]}
privacy: {offline_only: true, log_retention_days: 30}
```

---

## 8) APIs (local, FastAPI)

```
GET  /health
POST /asr/segment                  {audio_chunk} → {text, spans[]}
POST /extract/visit                {transcript_span, chart_facts[]} → {VisitJSON, slot_scores}
GET  /facts/context?window=72h     → {labs[], vitals[], meds[], notes[]}
POST /compose/note                 {VisitJSON, facts[]} → {markdown, citations[]}
POST /compose/handoff              {VisitJSON, facts[]} → {ipass_json}
POST /compose/discharge            {VisitJSON, facts[], lang} → {markdown}
POST /suggest/planpack             {pathway, VisitJSON, facts[]} → {suggestions[], guard_flags[]}
POST /chips/resolve                {chip_id, action, value?} → {ok}
GET  /metrics/session              → {timers, keystrokes, chip_counts}
```

---

## 9) UX Requirements

- **Consent** banner before ambient capture.
- **Compose** button appears only after consent; live transcript scroll with time markers.
- **Chips rail** (right): B (gray), C (yellow), D (red). Batch-accept, evidence popover with source IDs and timestamps.
- **One-screen finalize** shows Note + Handoff + Discharge with export controls.

---

## 10) Testing & QA

### 10.1 Unit

- Regex extraction (≥95% pass on curated set); schema validator must reject malformed JSON (100%); guard logic blocks correctly.

### 10.2 Integration

- Audio→VisitJSON→Note pipeline correctness (golden files); chip bands vs thresholds; discharge localization QA.

### 10.3 Pilot eval

- 20–50 encounters across ≥2 clinicians; AB comparison to baseline; weekly template reviews to reduce chip volume.

---

## 11) Delivery & Milestones (proposal)

- **M0 | Week 0–2 — Foundation**
  ASR, transcript UI, regex rules & LLM extractor, SQLite cache & evidence chips.

- **M1 | Week 3–4 — Compose & Chips**
  Jinja2 templates (Note, I-PASS, Discharge EN+1), chips engine (B/C/D), plan packs (3 pathways), guard checks, export.

- **M2 | Week 5–6 — Pilot Pack**
  Metrics panel; audit log; installer (Windows/macOS signed); config loader; accessibility pass.

- **M3 | Week 7–10 — Site Pilot**
  20–50 encounters; time/quality metrics; weekly tuning; pilot report.

*(Vendors may propose alternative timelines; must maintain MVP scope and success criteria.)*

---

## 12) Handover & Documentation Deliverables

- Architecture doc & ADRs; threat model; SBOM; model cards; DPIA template.
- Template/rules/plan-packs with versioning; admin guide (change process).
- Installer + update signing process; ops runbooks; incident playbooks.
- Pilot results report (metrics, edits, failure modes, recommendations).

---

## 13) Commercial & Legal (RFP checklist)

- HIPAA BAA & GDPR DPA readiness.
- Data residency & offline guarantee; PHI processing statement.
- IP: customer ownership of clinical templates/plan packs; vendor licenses for runtime components; freedom-to-operate disclosure.
- Support SLAs (P0/P1); security vulnerability SLAs; update cadence.
- Pricing: MVP build, pilot support (8–12 weeks), optional enterprise add-ons (SSO, SMART on FHIR, write-back).

---

## 14) Glossary (clinical)

- **MDM** — Medical Decision Making (E/M).
- **H&P** — Admission/new-patient History & Physical.
- **Progress note** — Daily SOAP update.
- **I-PASS** — Standardized handoff (Illness severity, Patient summary, Action list, Pending/plan, Contingency, Synthesis).

---

## 15) Appendices

### A) Confidence & Chip Spec (excerpt)

- **Bands:** A ≥0.90 (auto), B 0.70–0.89 (soft), C 0.45–0.69 (must), D <0.45/guards (blocked).
- **Icons:** ● (B), ▲ (C), ■ (D); **colors:** gray/yellow/red; WCAG AA compliant.
- **Reopen rule:** escalate on contradictory new data; de-escalate only on user action.

### B) Safety Guards (starter set)

- Allergies (esp. ASA, contrast), active bleeding, pregnancy status when relevant, renal function for contrast/dosing, anticoagulation conflicts.

### C) Plan Packs — Pathways (starter)

- **Chest pain**, **Seizure**, **Sepsis** with YAML examples and guard matrices.

---

## Vendor Response Instructions (what to include)

1. **Architecture & model plan** (confirm edge-first, model sizes, quantization).
2. **Security & compliance** (threat model, SBOM, signed updates, HIPAA/GDPR posture).
3. **Clinical safety plan** (guard rails, override logging, I-PASS scoring).
4. **EHR integration** approach (MVP read-only, future SMART on FHIR).
5. **Pilot methodology** (metrics capture, datasets needed, analysis).
6. **Delivery plan & team** (roles, bios, timelines, risks).
7. **Commercials** (MVP cost, pilot support, options).

---

If you’d like, I can export this as a polished **PDF “RFP Pack”** (with a cover page, contents, and checklists) and include editable **YAML/JSON** starter files for schemas and plan packs.
