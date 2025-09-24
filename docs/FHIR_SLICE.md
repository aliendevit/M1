# FHIR Slice Contract

MinuteOne projects FHIR R4 bundles into lightweight row structures to streamline ingestion into the evidence cache.

## Functions
- `slice_patient(resource)` ? `{id, name}`
- `slice_encounter(resource)` ? `{id, patient_id, start, klass}`
- `slice_observation(resource)` ? `{id, patient_id, code, name, value_num, unit, ts}`
- `slice_document_reference(resource)` ? `{id, text}`
- `bundle_to_rows(bundle)` ? dictionary with `patients`, `encounters`, `observations`, `documents` lists.

Each helper accepts a FHIR R4 resource dictionary. Unknown fields are ignored and missing identifiers short-circuit to `None` so upstream callers can skip invalid resources safely.

## Versioning
- Target FHIR version: **R4**
- Reference parsing: only the final segment of `subject.reference` / `Patient/{id}` is used.
- Quantity handling: `valueQuantity.value` is cast to float; `unit` falls back to `valueQuantity.code`.

## Testing
`tests/test_fhir_slice_contract.py` enforces the row shapes using representative bundle fragments. Add new regression cases there when extending the slicer.
