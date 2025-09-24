from m1.chips.service import ChipService


def test_chip_service_generates_labels():
    service = ChipService()
    bundle = {
        "sections": {
            "structured": {
                "problems": ["chest pain"],
                "plan": ["Admit to telemetry"],
                "vitals": {"heart_rate": "120"},
            }
        }
    }
    extraction = {
        "problems": ["chest pain"],
        "plan": ["Admit to telemetry"],
        "vitals": {"heart_rate": "120"},
        "medications": [],
    }

    chips = service.generate(bundle, extraction)

    assert any("Problem" in chip["label"] for chip in chips)
    assert any(chip["value"] == "120" for chip in chips)
