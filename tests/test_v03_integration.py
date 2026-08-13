from radar_delictual.integration import build_integration_contract

def test_homicide_is_absent_from_aml_contract():
    region=[{'year':2025,'region_code':'13','pressure_score':60}]
    commune=[{'territory_id':'CL-13-santiago','period':'2024','region_code':'13','commune_code':None,'commune_name_norm':'santiago','cead_aml_priority_score':80,'article27_relation':'direct_family_ley_20000'}]
    rows=build_integration_contract(region,commune)
    assert all('homicid' not in ' '.join(r['source_families']).lower() for r in rows)
    assert all(r['excludes_homicide_weight'] is True for r in rows)
    assert rows[1]['aml_relevance']=='direct_predicate_family'
