from radar_delictual.cead_communal import parse_annual_2024, parse_latest_2025, load_catalog
from radar_delictual.risk_v3 import build_cead_commune_aml_priority
from radar_delictual.aml import classify_category

ANNUAL_HTML='''<html><body><h6>7.1 Tasas anuales denuncias por familia de delitos</h6><table><tr><th>Nivel territorial</th><th>Delitos Violentos</th><th>Asociados a drogas</th><th>Contra la propiedad no violentos</th><th>Violencia intrafamiliar</th></tr><tr><td>Arica</td><td>2.066,4</td><td>32,7</td><td>1.181,4</td><td>673,1</td></tr><tr><td>Distrito 1</td><td>2.000,0</td><td>33,0</td><td>1.100,0</td><td>600,0</td></tr></table></body></html>'''

LATEST_DUP='''<html><body>
<h6>7.1 Delitos contra la vida o integridad de las personas: Frecuencia y Tasa</h6><table><tr><td>Arica</td><td>575</td><td>424</td><td>257.163</td><td>259.064</td><td>223,6</td><td>160,8</td></tr></table>
<h6>7.2 Violencia Intrafamiliar: Frecuencia y Tasa</h6><table><tr><td>Arica</td><td>575</td><td>424</td><td>257.163</td><td>259.064</td><td>223,6</td><td>160,8</td></tr></table>
<h6>7.3 Delitos asociados a Drogas: Frecuencia y Tasa</h6><table><tr><td>Arica</td><td>575</td><td>424</td><td>257.163</td><td>259.064</td><td>223,6</td><td>160,8</td></tr></table>
</body></html>'''

def test_annual_parser_maps_drugs_to_art27():
    rows=parse_annual_2024(ANNUAL_HTML,1)
    drug=next(r for r in rows if r['cead_family_key']=='delitos_asociados_drogas')
    assert drug['rate_100k']==32.7
    assert drug['article27_relation']=='direct_family_ley_20000'
    assert drug['score_eligible'] is True

def test_arms_aggregate_not_automatically_predicate():
    c=load_catalog()['families']['delitos_asociados_armas']
    assert c['score_eligible'] is False
    assert c['aml_weight']==0.0
    assert c['article27_relation'].startswith('partial')

def test_homicide_has_zero_aml_weight():
    c=load_catalog()['families']['homicidios']
    assert c['aml_weight']==0.0 and c['score_eligible'] is False
    assert classify_category('HOMICIDIOS')['weight']==0.0

def test_duplicate_latest_sections_are_quarantined():
    rows,pops,diag=parse_latest_2025(LATEST_DUP,1)
    assert diag['duplicated_sections'] is True
    assert rows[0]['quality_status']=='quarantined_duplicate_section'
    assert rows[0]['score_eligible'] is False
    assert pops['arica']==257163

def test_v3_score_uses_only_drug_eligible_rows():
    rows=[]
    for name,rate,pop,eligible,family in [('A',100,100000,True,'delitos_asociados_drogas'),('B',10,100000,True,'delitos_asociados_drogas'),('C',10000,100000,False,'delitos_contra_vida_integridad')]:
        rows.append({'year':2024,'period':'2024','territory_id':'CL-13-'+name.lower(),'region_code':'13','region_name':'Metropolitana de Santiago','commune_name':name,'commune_name_norm':name.lower(),'commune_code':None,'cead_family_key':family,'quality_status':'usable','score_eligible':eligible,'rate_100k':rate,'population':pop,'estimated_frequency':round(rate*pop/100000),'source_id':'bcn_siit_cead_communal','ultimate_source_id':'cead_estadisticas_delictuales'})
    out=build_cead_commune_aml_priority(rows)
    assert len(out)==2
    assert out[0]['commune_name']=='A'
    assert all(r['commune_name']!='C' for r in out)
