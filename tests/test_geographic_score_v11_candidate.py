from radar_delictual.geographic_score_v11 import (
    _temporal_anomaly_score,
    build_cead_geographic_score_v11_candidate,
)


def row(commune, year, category, value, source_tier="mirror_of_primary"):
    return {
        "territory_id": f"CL-{commune}",
        "commune_code": commune,
        "commune_name": f"C{commune}",
        "region_code": "13",
        "region_name": "Metropolitana",
        "year": year,
        "crime_category": category,
        "metric": "casos_policiales",
        "value": value,
        "quality_status": "usable",
        "source_tier": source_tier,
    }


def test_temporal_anomaly_compares_commune_against_its_own_history():
    assert _temporal_anomaly_score([10, 10, 10, 10], 10) == 50.0
    assert _temporal_anomaly_score([10, 10, 10, 10], 30) > 50.0
    assert _temporal_anomaly_score([10, 10, 10, 10], 2) < 50.0


def test_candidate_penalizes_semantic_precision_of_drug_family_fallback():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, "Delitos asociados a drogas", 10 + year - 2020),
            row("13102", year, "Delitos asociados a drogas", 5),
        ]

    population = {"13101": 200000, "13102": 100000}
    scores = build_cead_geographic_score_v11_candidate(master, population)
    by = {r["commune_code"]: r for r in scores}
    layer = by["13101"]["layers"]["predicate_direct"]

    assert layer["score"] is not None
    assert layer["coverage"] == 1.0
    assert layer["thematic_coverage"] == 0.75
    assert by["13101"]["confidence_components"]["thematic_coverage"] < 100.0
    assert by["13101"]["confidence"] is not None


def test_candidate_intensity_combines_volume_and_population_rate_when_available():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, "Delitos asociados a drogas", 100),
            row("13102", year, "Delitos asociados a drogas", 60),
            row("13103", year, "Delitos asociados a drogas", 20),
        ]

    # 13101 tiene mayor volumen, pero una tasa muy inferior a 13102.
    population = {"13101": 1000000, "13102": 50000, "13103": 100000}
    scores = build_cead_geographic_score_v11_candidate(master, population)
    by = {r["commune_code"]: r for r in scores}
    comp1 = by["13101"]["layers"]["predicate_direct"]["components"][0]
    comp2 = by["13102"]["layers"]["predicate_direct"]["components"][0]

    assert comp1["population_available"] is True
    assert comp2["population_available"] is True
    assert comp1["rate_percentile"] is not None
    assert comp2["rate_percentile"] is not None
    assert comp1["intensity"] != comp1["volume_percentile"]
    assert comp2["intensity"] != comp2["volume_percentile"]


def test_candidate_source_quality_is_separate_from_score():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, "Delitos asociados a drogas", 10, "primary_direct"),
            row("13102", year, "Delitos asociados a drogas", 10, "mirror_of_primary"),
        ]

    population = {"13101": 100000, "13102": 100000}
    scores = build_cead_geographic_score_v11_candidate(master, population)
    by = {r["commune_code"]: r for r in scores}

    assert by["13101"]["score"] == by["13102"]["score"]
    assert by["13101"]["confidence_components"]["source_quality"] > by["13102"]["confidence_components"]["source_quality"]
    assert by["13101"]["confidence"] > by["13102"]["confidence"]
