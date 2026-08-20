from radar_delictual.geographic_score_runtime import normalize_quality_status


def test_usable_bridge_is_accepted_without_mutating_master():
    source = [{"quality_status": "usable_bridge", "value": 12}]
    normalized = normalize_quality_status(source)
    assert normalized[0]["quality_status"] == "usable"
    assert source[0]["quality_status"] == "usable_bridge"


def test_other_quality_states_are_preserved():
    source = [
        {"quality_status": "validated"},
        {"quality_status": "quarantined"},
        {"quality_status": None},
    ]
    normalized = normalize_quality_status(source)
    assert [row.get("quality_status") for row in normalized] == ["validated", "quarantined", None]
