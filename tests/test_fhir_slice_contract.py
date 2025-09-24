from m1.fhir.slice import bundle_to_rows, slice_document_reference, slice_encounter, slice_observation, slice_patient


def _bundle_entry(resource_type, resource):
    body = {"resourceType": resource_type, **resource}
    return {"resource": body}


def test_slice_patient_generates_display_name():
    resource = {
        "id": "patient-1",
        "name": [{"given": ["Jane"], "family": "Doe"}],
    }
    result = slice_patient({"resourceType": "Patient", **resource})

    assert result == {"id": "patient-1", "name": "Jane Doe"}


def test_bundle_to_rows_collects_resources():
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            _bundle_entry(
                "Patient",
                {
                    "id": "p1",
                    "name": [{"given": ["Pat"], "family": "Smith"}],
                },
            ),
            _bundle_entry(
                "Encounter",
                {
                    "id": "enc1",
                    "subject": {"reference": "Patient/p1"},
                    "period": {"start": "2024-01-01T00:00:00Z"},
                    "class": {"code": "inpatient"},
                },
            ),
            _bundle_entry(
                "Observation",
                {
                    "id": "obs1",
                    "subject": {"reference": "Patient/p1"},
                    "effectiveDateTime": "2024-01-01T00:00:00Z",
                    "code": {
                        "coding": [{"code": "8867-4", "display": "Heart rate"}],
                        "text": "Heart rate",
                    },
                    "valueQuantity": {"value": 88, "unit": "bpm"},
                },
            ),
            _bundle_entry(
                "DocumentReference",
                {
                    "id": "doc1",
                    "description": "Discharge summary text",
                },
            ),
        ],
    }

    rows = bundle_to_rows(bundle)

    assert rows["patients"] == [{"id": "p1", "name": "Pat Smith"}]
    assert rows["encounters"] == [
        {"id": "enc1", "patient_id": "p1", "start": "2024-01-01T00:00:00Z", "klass": "inpatient"}
    ]
    assert rows["observations"] == [
        {
            "id": "obs1",
            "patient_id": "p1",
            "code": "8867-4",
            "name": "Heart rate",
            "value_num": 88.0,
            "unit": "bpm",
            "ts": "2024-01-01T00:00:00Z",
        }
    ]
    assert rows["documents"] == [{"id": "doc1", "text": "Discharge summary text"}]


def test_slice_functions_ignore_irrelevant_resources():
    assert slice_patient({"resourceType": "Observation"}) is None
    assert slice_encounter({"resourceType": "Patient"}) is None
    assert slice_observation({"resourceType": "Encounter"}) is None
    assert slice_document_reference({"resourceType": "Patient"}) is None
