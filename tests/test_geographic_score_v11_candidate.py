from radar_delictual.geographic_score_v11 import (
    _population_reliability,
    _temporal_anomaly_score,
    build_cead_geographic_score_v11_candidate,
    load_candidate_config,
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


def test_population_reliability_shrinks_small_denominators():
    config = load_candidate_config()
    small = _population_reliability(5000, config)
    medium = _population_reliability(50000, config)
    large = _population_reliability(500000, config)
    assert 0 < small < medium < large < 1


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
    assert by["13101"]["methodological_coverage"] < 100.0


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


def test_small_population_gets_less_rate_weight_than_large_population():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, "Delitos asociados a drogas", 20),
            row("13102", year, "Delitos asociados a drogas", 20),
            row("13103", year, "Delitos asociados a drogas", 20),
        ]

    population = {"13101": 5000, "13102": 50000, "13103": 500000}
    scores = build_cead_geographic_score_v11_candidate(master, population)
    by = {r["commune_code"]: r for r in scores}
    small = by["13101"]["layers"]["predicate_direct"]["components"][0]
    large = by["13103"]["layers"]["predicate_direct"]["components"][0]

    assert small["effective_rate_weight"] < large["effective_rate_weight"]
    assert small["effective_volume_weight"] > large["effective_volume_weight"]
    assert by["13101"]["confidence_components"]["denominator_reliability"] < by["13103"]["confidence_components"]["denominator_reliability"]


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


def test_sparse_temporal_anomaly_is_shrunk_toward_neutral():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024):
        master += [
            row("13101", year, "Delitos asociados a drogas", 0),
            row("13102", year, "Delitos asociados a drogas", 0),
        ]
    master += [
        row("13101", 2025, "Delitos asociados a drogas", 1),
        row("13102", 2025, "Delitos asociados a drogas", 0),
    ]

    scores = build_cead_geographic_score_v11_candidate(
        master, {"13101": 5000, "13102": 5000}
    )
    by = {r["commune_code"]: r for r in scores}
    comp = by["13101"]["layers"]["predicate_direct"]["components"][0]

    assert comp["temporal_anomaly_raw"] > 50.0
    assert 50.0 < comp["temporal_anomaly"] < comp["temporal_anomaly_raw"]
    assert comp["temporal_anomaly_reliability"] < 10.0
    assert comp["temporal_anomaly_support"] == 1.0


def test_temporal_anomaly_retains_signal_when_event_support_is_substantial():
    master = []
    for year, value in zip((2020, 2021, 2022, 2023, 2024), (30, 31, 29, 30, 30)):
        master += [
            row("13101", year, "Delitos asociados a drogas", value),
            row("13102", year, "Delitos asociados a drogas", 10),
        ]
    master += [
        row("13101", 2025, "Delitos asociados a drogas", 60),
        row("13102", 2025, "Delitos asociados a drogas", 10),
    ]

    scores = build_cead_geographic_score_v11_candidate(
        master, {"13101": 100000, "13102": 100000}
    )
    by = {r["commune_code"]: r for r in scores}
    comp = by["13101"]["layers"]["predicate_direct"]["components"][0]

    assert comp["temporal_anomaly_raw"] > 50.0
    assert comp["temporal_anomaly"] > 50.0
    assert comp["temporal_anomaly_reliability"] > 90.0
    assert abs(comp["temporal_anomaly"] - comp["temporal_anomaly_raw"]) < 6.0
