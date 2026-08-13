from radar_delictual.territory import canonical_commune_code, commune_territory_id
from scripts.build_territory_interop import adapt


def test_commune_key_uses_official_code():
    assert canonical_commune_code("13101") == "13101"
    assert commune_territory_id("13101") == "CL-COM-13101"


def test_interop_view_replaces_legacy_key():
    row = adapt({"commune_code":"13101","territory_id":"CL-13101","year":2024})
    assert row["territory_id"] == "CL-COM-13101"
    assert row["territory_mapping_method"] == "CODE_EXACT"
    assert row["territory_mapping_confidence"] == 1.0


def test_missing_code_stays_unresolved():
    row = adapt({"commune_name":"Sin código"})
    assert row["territory_id"] is None
    assert row["territory_mapping_method"] == "UNRESOLVED"
