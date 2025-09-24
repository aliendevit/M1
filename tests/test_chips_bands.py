from m1.chips.service import ChipService


def test_chip_service_assigns_confidence_bands():
    service = ChipService()
    bundle = {
        "sections": {
            "structured": {
                "problems": ["sepsis"],
                "plan": ["Begin fluids"],
                "vitals": {"heart_rate": "105"},
            }
        }
    }
    extraction = {
        "problems": ["sepsis"],
        "plan": ["Begin fluids"],
        "vitals": {"heart_rate": "105"},
        "medications": [],
        "labs": [],
    }

    chips = service.generate(bundle, extraction)

    assert any("Problem" in chip["label"] for chip in chips)
    assert all(0 <= chip["confidence"] <= 1 for chip in chips)
