from radar_delictual.geographic_score import build_cead_geographic_score


def row(commune, year, category, value):
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
    }


def test_score_uses_55_35_10_and_preserves_missing_as_missing():
    master = []
    for year in (2023, 2024, 2025):
        master += [
            row("13101", year, "Tráfico de sustancias", 10 + (year - 2023) * 5),
            row("13102", year, "Tráfico de sustancias", 2),
            row("13101", year, "Receptación", 8 + (year - 2023) * 2),
            row("13102", year, "Receptación", 1),
            row("13101", year, "Comercio ilegal", 6),
            row("13102", year, "Comercio ilegal", 1),
            row("13101", year, "Robos con violencia o intimidación", 7),
            row("13102", year, "Robos con violencia o intimidación", 2),
        ]

    scores = build_cead_geographic_score(master)
    by = {r["commune_code"]: r for r in scores}
    high = by["13101"]
    low = by["13102"]

    assert high["layer_weights"] == {
        "predicate_direct": 0.55,
        "criminal_economy": 0.35,
        "criminogenic_context": 0.10,
    }
    assert high["score"] > low["score"]
    assert high["layers"]["predicate_direct"]["score"] is not None
    assert high["layers"]["criminal_economy"]["score"] is not None
    assert high["layers"]["criminogenic_context"]["score"] is not None
    assert high["confidence"] < 100.0  # faltan varios componentes y se informa cobertura


def test_absence_is_not_materialized_as_zero():
    master = [row("13101", 2025, "Tráfico de sustancias", 5)]
    scores = build_cead_geographic_score(master)
    score = scores[0]
    assert score["layers"]["criminal_economy"]["score"] is None
    assert score["layers"]["criminogenic_context"]["score"] is None
    assert score["score"] is not None
    assert score["confidence"] < 60.0
