from m1.export.markdown import render_markdown


def test_render_markdown_includes_sections():
    bundle = {
        "sections": {
            "subjective": {"transcript": "Patient feels better."},
            "structured": {
                "problems": ["fatigue"],
                "plan": ["Discharge tomorrow"],
                "vitals": {"blood_pressure": "120/70"},
            },
        }
    }

    output = render_markdown(bundle)

    assert "Patient feels better." in output
    assert "Fatigue" in output
    assert "Discharge tomorrow" in output
