# Safety Overview

MinuteOne keeps protected health information on the local workstation. No cloud calls occur during extraction or note composition.

## Guardrails
- Hard blocks prevent automation when transcripts contain "call code" or "cardiac arrest" terms.
- Soft flags highlight transcripts mentioning seizure, suicide, falls, or sepsis-related concerns.
- Audit log persists inside `data/audit.log` alongside evidence cache.

## Override Policy
Clinicians must document rationale before acting on blocked items. Currently the sandbox emits a 403 response from `/ingest`; override workflows will integrate with the UI in later releases.

## Data Retention
- Evidence cache stored at `data/m1_cache.db`
- Audit events stored at `data/audit.log`
- Remove PHI by deleting the `data/` directory after export.
