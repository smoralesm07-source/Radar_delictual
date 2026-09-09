from radar_delictual.geographic_score_v11 import (
    build_cead_geographic_score_v11_candidate,
    load_candidate_config,
)


def row(commune, year, value, source_tier="mirror_of_primary"):
    return {
        "territory_id": f"CL-{commune}",
        "commune_code": commune,
        "commune_name": f"C{commune}",
        "region_code": "13",
        "region_name": "Metropolitana",
        "year": year,
        "crime_category": "Delitos asociados a drogas",
        "metric": "casos_policiales",
        "value": value,
        "quality_status": "usable",
        "source_tier": source_tier,
    }


def test_rc1_freezes_score_formula_and_removes_denominator_from_confidence():
    cfg = load_candidate_config()
    assert cfg["version"] == "1.1.0-rc.1"
    assert cfg["status"] == "release_candidate"
    assert cfg["rc1_policy"]["score_formula_frozen"] is True
    assert cfg["presentation_policy"]["primary_outputs"] == ["score", "national_percentile"]
    assert cfg["presentation_policy"]["band_role"] == "secondary_context"
    assert cfg["feature_weights"] == {
        "intensity": 0.4,
        "persistence": 0.25,
        "trend": 0.2,
        "temporal_anomaly": 0.15,
    }
    assert cfg["intensity_mix"]["volume_percentile"] == 0.6
    assert cfg["intensity_mix"]["rate_per_100k_percentile"] == 0.4
    assert cfg["temporal_anomaly_reliability"]["support_scale"] == 20

    cw = cfg["confidence_weights"]
    assert round(sum(float(v) for v in cw.values()), 8) == 1.0
    assert cw["denominator_reliability"] == 0.0
    assert cw["stability"] == 0.6


def test_rc1_confidence_does_not_reward_population_size_by_itself():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, 10),
            row("13102", year, 10),
            row("13103", year, 10),
        ]

    scores = build_cead_geographic_score_v11_candidate(
        master,
        {"13101": 5000, "13102": 100000, "13103": 500000},
    )
    by = {r["commune_code"]: r for r in scores}

    assert (
        by["13101"]["confidence_components"]["denominator_reliability"]
        < by["13103"]["confidence_components"]["denominator_reliability"]
    )
    # Con series idénticas y estables, el tamaño poblacional no debe elevar por sí
    # solo la confianza. La confiabilidad del denominador sigue visible como
    # diagnóstico, pero tiene peso 0 en el compuesto RC1.
    assert by["13101"]["confidence"] == by["13102"]["confidence"]
    assert by["13102"]["confidence"] == by["13103"]["confidence"]


def test_rc1_confidence_still_responds_to_source_quality():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, 10, "primary_direct"),
            row("13102", year, 10, "mirror_of_primary"),
        ]

    scores = build_cead_geographic_score_v11_candidate(
        master,
        {"13101": 100000, "13102": 100000},
    )
    by = {r["commune_code"]: r for r in scores}
    assert by["13101"]["confidence"] > by["13102"]["confidence"]


def test_rc1_exposes_national_rank_and_percentile_as_primary_context():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, 100),
            row("13102", year, 30),
            row("13103", year, 5),
        ]

    scores = build_cead_geographic_score_v11_candidate(
        master,
        {"13101": 100000, "13102": 100000, "13103": 100000},
    )
    ordered = sorted(scores, key=lambda item: float(item["score"]), reverse=True)

    assert ordered[0]["national_rank"] == 1
    assert ordered[0]["national_percentile"] == 100.0
    assert ordered[-1]["national_percentile"] == 0.0
    assert all(0.0 <= float(item["national_percentile"]) <= 100.0 for item in scores)
    assert all(item["primary_reading"] == "score_plus_national_percentile" for item in scores)
