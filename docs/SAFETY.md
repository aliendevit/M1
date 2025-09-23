# Safety Policy

MinuteOne enforces conservative guardrails so clinicians remain in control.

## Guard Catalogue

- **Allergy** – blocks plan elements requiring agents with documented allergies. Unknown status defaults to blocked.
- **Active Bleed** – prevents actions that could worsen hemorrhage risk when bleeding is noted or cannot be ruled out.
- **Pregnancy** – requires explicit override when pregnancy status is uncertain and the intervention carries fetal risk.
- **Renal** – uses eGFR thresholds (<30 ml/min high risk, <60 caution) and blocks contrast-requiring steps when status unknown.
- **Anticoagulation** – highlights active anticoagulant therapy before suggesting invasive or high bleed-risk actions.

Each guard returns a band (A–D). Bands C/D require verbal confirmation; band D entries can only proceed with an override reason recorded via `/chips/resolve`.

## Override Workflow

1. Clinician reviews the flagged chip (band D).
2. If override is necessary, the UI requires entry of a textual justification.
3. The action, reason, and timestamp are appended to `logs/chip_audit.jsonl`.
4. Downstream automation never executes orders: the tool surfaces guidance only.

## Logging

- Every compose event requires a consent toggle.
- Chip resolutions are recorded as JSON lines with `{ts, chip_id, action, value, reason}`.
- Audit files stay on local disk; rotate or archive via institutional policy.

## Fallback Behaviour

If structured data is missing (e.g., eGFR absent), guards default to "unknown" (band D), forcing clinician review. The system does not guess or infer missing safety data.
