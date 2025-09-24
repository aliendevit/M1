"""Slicing helpers that project FHIR bundle resources into tabular rows."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TypedDict

FHIR_VERSION = "R4"


class PatientRow(TypedDict):
    id: str
    name: str


class EncounterRow(TypedDict):
    id: str
    patient_id: str
    start: Optional[str]
    klass: Optional[str]


class ObservationRow(TypedDict):
    id: str
    patient_id: str
    code: Optional[str]
    name: Optional[str]
    value_num: Optional[float]
    unit: Optional[str]
    ts: Optional[str]


class DocumentRow(TypedDict):
    id: str
    text: str


def slice_patient(resource: Dict[str, object]) -> Optional[PatientRow]:
    if resource.get("resourceType") != "Patient":
        return None
    patient_id = _ensure_id(resource)
    if not patient_id:
        return None
    display = _resolve_patient_name(resource)
    return PatientRow(id=patient_id, name=display or patient_id)


def slice_encounter(resource: Dict[str, object]) -> Optional[EncounterRow]:
    if resource.get("resourceType") != "Encounter":
        return None
    encounter_id = _ensure_id(resource)
    patient_ref = _get_nested(resource, ["subject", "reference"])
    patient_id = _reference_to_id(patient_ref)
    if not encounter_id or not patient_id:
        return None
    klass = _resolve_encounter_class(resource)
    start = _get_nested(resource, ["period", "start"])
    return EncounterRow(id=encounter_id, patient_id=patient_id, start=start, klass=klass)


def slice_observation(resource: Dict[str, object]) -> Optional[ObservationRow]:
    if resource.get("resourceType") != "Observation":
        return None
    observation_id = _ensure_id(resource)
    patient_ref = _get_nested(resource, ["subject", "reference"])
    patient_id = _reference_to_id(patient_ref)
    if not observation_id or not patient_id:
        return None
    code = _resolve_code(resource)
    name = _resolve_display(resource)
    value_num, unit = _resolve_value_quantity(resource)
    timestamp = resource.get("effectiveDateTime") or resource.get("issued")
    return ObservationRow(
        id=observation_id,
        patient_id=patient_id,
        code=code,
        name=name,
        value_num=value_num,
        unit=unit,
        ts=timestamp,
    )


def slice_document_reference(resource: Dict[str, object]) -> Optional[DocumentRow]:
    if resource.get("resourceType") != "DocumentReference":
        return None
    document_id = _ensure_id(resource)
    if not document_id:
        return None
    text = resource.get("description") or _resolve_document_text(resource) or ""
    return DocumentRow(id=document_id, text=text)


def bundle_to_rows(bundle: Dict[str, object]) -> Dict[str, List[Dict[str, object]]]:
    rows = {
        "patients": [],
        "encounters": [],
        "observations": [],
        "documents": [],
    }
    if bundle.get("resourceType") != "Bundle":
        return rows
    for entry in bundle.get("entry", []) or []:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if not isinstance(resource, dict):
            continue
        patient = slice_patient(resource)
        if patient:
            rows["patients"].append(patient)
        encounter = slice_encounter(resource)
        if encounter:
            rows["encounters"].append(encounter)
        observation = slice_observation(resource)
        if observation:
            rows["observations"].append(observation)
        document = slice_document_reference(resource)
        if document:
            rows["documents"].append(document)
    return rows


def _ensure_id(resource: Dict[str, object]) -> Optional[str]:
    identifier = resource.get("id")
    if isinstance(identifier, str) and identifier:
        return identifier
    return None


def _resolve_patient_name(resource: Dict[str, object]) -> str:
    names = resource.get("name")
    if not isinstance(names, list) or not names:
        return ""
    primary = names[0] if isinstance(names[0], dict) else {}
    given = primary.get("given") if isinstance(primary.get("given"), list) else []
    family = primary.get("family") if isinstance(primary.get("family"), str) else ""
    parts = [part for part in given if isinstance(part, str)]
    if family:
        parts.append(family)
    return " ".join(part.strip() for part in parts if part).strip()


def _resolve_encounter_class(resource: Dict[str, object]) -> Optional[str]:
    klass = resource.get("class")
    if isinstance(klass, dict):
        if isinstance(klass.get("code"), str):
            return klass["code"]
        if isinstance(klass.get("display"), str):
            return klass["display"]
    if isinstance(klass, list) and klass:
        first = klass[0]
        if isinstance(first, dict):
            return first.get("code") or first.get("display")
    return None


def _resolve_code(resource: Dict[str, object]) -> Optional[str]:
    code = resource.get("code")
    if isinstance(code, dict):
        coding = code.get("coding")
        if isinstance(coding, list) and coding:
            first = coding[0]
            if isinstance(first, dict):
                if isinstance(first.get("code"), str):
                    return first["code"]
                if isinstance(first.get("display"), str):
                    return first["display"]
        if isinstance(code.get("text"), str):
            return code["text"]
    return None


def _resolve_display(resource: Dict[str, object]) -> Optional[str]:
    code = resource.get("code")
    if isinstance(code, dict):
        if isinstance(code.get("text"), str):
            return code["text"]
        coding = code.get("coding")
        if isinstance(coding, list) and coding:
            first = coding[0]
            if isinstance(first, dict) and isinstance(first.get("display"), str):
                return first["display"]
    return None


def _resolve_value_quantity(resource: Dict[str, object]) -> Tuple[Optional[float], Optional[str]]:
    quantity = resource.get("valueQuantity")
    if not isinstance(quantity, dict):
        return None, None
    value = quantity.get("value")
    unit = quantity.get("unit") if isinstance(quantity.get("unit"), str) else quantity.get("code")
    try:
        number = float(value) if value is not None else None
    except (TypeError, ValueError):
        number = None
    unit_value = unit if isinstance(unit, str) else None
    return number, unit_value


def _resolve_document_text(resource: Dict[str, object]) -> str:
    content = resource.get("content")
    if not isinstance(content, list) or not content:
        return ""
    first = content[0]
    if not isinstance(first, dict):
        return ""
    attachment = first.get("attachment")
    if not isinstance(attachment, dict):
        return ""
    for key in ("title", "text", "data"):
        value = attachment.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _reference_to_id(reference: Optional[str]) -> Optional[str]:
    if not reference or not isinstance(reference, str):
        return None
    if "/" in reference:
        return reference.split("/")[-1]
    return reference


def _get_nested(resource: Dict[str, object], path: List[str]) -> Optional[str]:
    current: Any = resource
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, str) else None
