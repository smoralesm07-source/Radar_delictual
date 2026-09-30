from radar_delictual.mp_experimental import assess_mp_extract, normalize_mp_aggregate


def _rows(with_commune=True):
    rows = []
    for year in (2022, 2023, 2024, 2025):
        row = {
            "year": year,
            "offense_code": "816",
            "offense_name": "Estafas y otras defraudaciones contra particulares",
            "offense_count": 100 + year,
            "fiscal_region": "Metropolitana",
            "local_prosecution_office": "Fiscalia Local X",
        }
        if with_commune:
            row.update({
                "occurrence_commune_code": "13101",
                "occurrence_commune_name": "Santiago",
            })
        rows.append(row)
    return rows


def test_communal_extract_requires_occurrence_commune():
    result = assess_mp_extract(_rows(with_commune=True))
    assert result["communal_ready"] is True
    assert result["igr_eligible"] is False


def test_fiscal_office_is_never_a_commune_proxy():
    result = assess_mp_extract(_rows(with_commune=False))
    assert result["communal_ready"] is False
    assert result["regional_ready"] is True
    assert result["status"] == "regional_only"


def test_normalization_does_not_infer_commune():
    normalized = normalize_mp_aggregate(_rows(with_commune=False))
    assert normalized[0]["occurrence_commune_code"] is None
    assert normalized[0]["occurrence_commune_name"] is None
    assert normalized[0]["quality_status"] == "research_only"
