from m1.extractor.service import extract_visit


def test_extract_visitjson_produces_valid_schema():
    transcript = (
        "Chief complaint: chest pain. Symptoms started yesterday evening. "
        "Patient describes it as pressure. Worse with exertion. "
        "Associated with diaphoresis. Denies GI red flags. "
        "Labs: troponin q3h x3."
    )
    result = extract_visit(transcript)
    visit = result.visit

    assert visit.chief_complaint.lower() == "chest pain"
    assert visit.hpi.onset == "yesterday evening"
    assert visit.hpi.quality == "pressure"
    assert "exertion" in visit.hpi.modifiers[0]
    assert "diaphoresis" in visit.hpi.associated_symptoms[0]
    assert visit.hpi.red_flags
    assert visit.plan_intents
    assert visit.plan_intents[0].type.value == "lab_series"
    assert visit.plan_intents[0].schedule == ["troponin q3h x3"]
    assert "chief_complaint" in result.slot_scores
    assert result.slot_scores["chief_complaint"].rule_hit == 1.0
