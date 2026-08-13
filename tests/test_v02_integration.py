from radar_delictual.integration import build_integration_contract

def test_contract_preserves_geographic_join_keys():
    region=[{'region_code':'13','period':'2025-H1','territorial_priority_score':80}]
    commune=[{'territory_id':'CL-13101','region_code':'13','commune_code':'13101','homicide_pressure_score':70}]
    rows=build_integration_contract(region,commune)
    assert rows[0]['join_keys']['region_code']=='13'
    assert rows[1]['join_keys']['commune_code']=='13101'
    assert rows[1]['aml_relevance']=='context_only'
