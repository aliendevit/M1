# Safety & Guard Catalogue

MinuteOne suggestions are assistive only. The following guardrails enforce conservative defaults and log overrides for audit.

## Guard Checks

| Guard | Purpose | Trigger |
| --- | --- | --- |
| `require_absent` | Blocks pathway when a listed risk is present in VisitJSON (e.g., `active bleed`). | Intersection between visit risks and prohibited list. |
| `check_allergy` | Prevents medication suggestions if patient has matching allergy. | Allergies pulled from chart cache (not populated in demo). |
| `check_renal` | Flags dosing suggestions when latest creatinine > 2.0 mg/dL. | Creatinine delta computed in SQLite cache. |
| `check_pregnancy` | Requires clinician confirmation before exposing teratogenic plans. | Visit risk list contains `pregnancy`. |
| `check_anticoag` | Blocks procedures/meds that conflict with anticoagulant therapy. | Planned anticoagulant intent overlaps guard list. |

## Override Policy

- Blocked guards surface as **D-band** chips and cannot be accepted without an override reason.
- `/chips/resolve` must include `reason` when `action == "override_blocked"`; the audit log persists `{chip_id, before, after, reason}`.
- Reasons should be descriptive (e.g., "Discussed with cardiology – ASA given despite low-grade bleed").

## Logging Expectations

| Event | Payload |
| --- | --- |
| `consent` | `{timestamp, user, granted: bool}` |
| `compose` | `{timestamp, visit_id, artifacts: [note, handoff, discharge], citations: [...]}` |
| `chip_resolved` | `{timestamp, chip_id, action, value, reason?}` |

Logs are written to `data/audit.log.jsonl`. Retention defaults to 30 days and can be adjusted in `config.yaml`.

## Clinical Review

- Guard catalogue reviewed quarterly with clinical leadership.
- Any override trend >10% triggers review of pathway definitions and plan pack content.
- Near misses are captured via the audit log and summarised for the pilot retrospective.
