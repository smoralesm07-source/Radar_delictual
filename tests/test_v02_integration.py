from radar_delictual.integration import build_integration_contract


def test_contract_v03_preserves_geographic_join_keys_and_excludes_homicides():
    """El contrato v0.2 fue sustituido: homicidios ya no son señal AML integrable."""
    region = [{
        'year': 2025,
        'region_code': '13',
        'pressure_score': 80,
    }]
    commune = [{
        'territory_id': 'CL-13-santiago',
        'period': '2024',
        'region_code': '13',
        'commune_code': '13101',
        'commune_name_norm': 'santiago',
        'cead_aml_priority_score': 70,
        'article27_relation': 'direct_family_ley_20000',
    }]
    rows = build_integration_contract(region, commune)
    assert rows[0]['join_keys']['region_code'] == '13'
    assert rows[1]['join_keys']['commune_code'] == '13101'
    assert rows[1]['aml_relevance'] == 'direct_predicate_family'
    assert all(r['excludes_homicide_weight'] is True for r in rows)
    assert all('homicid' not in ' '.join(r['source_families']).lower() for r in rows)
