from jinja2 import Environment, FileSystemLoader


def test_note_template_renders_subjective(tmp_path):
    env = Environment(loader=FileSystemLoader("m1/templates"))
    template = env.get_template("note.j2")
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

    content = template.render(bundle=bundle)

    assert "Patient feels better." in content
    assert "Discharge tomorrow" in content
