import pandas as pd

from radar_delictual.cead_bridge import annualize_bridge, normalize_bridge_frame
from radar_delictual.cead_direct import drug_payload, parse_cead_html
from radar_delictual.cead_master import annotate_master, build_predicate_features, merge_annual_sources
from radar_delictual.risk_v4 import build_current_predicate_activity


def test_direct_payload_uses_cead_numeric_cut_and_drug_catalog():
    payload=drug_payload(2025,"01101")
    assert ("comuna[]","1101") in payload
    assert ("familia[]","4") in payload
    assert ("grupo[]","401") in payload
    assert ("subgrupo[]","40101") in payload
    assert ("subgrupo[]","40104") in payload


def test_direct_parser_reads_monthly_table():
    html='''<table><tr><th>Delito</th><th>Enero</th><th>Febrero</th><th>Marzo</th></tr><tr><td>Delitos asociados a drogas</td><td>10</td><td>12</td><td>9</td></tr></table>'''
    rows=parse_cead_html(html,2025,"01101")
    assert len(rows)==3
    assert rows[0]["period"]=="2025-01"
    assert rows[1]["cases_policiales"]==12


def test_bridge_normalization_and_annualization():
    df=pd.DataFrame([
        {"comuna":"Iquique","cut_comuna":1101,"region":"Tarapacá","cut_region":1,"fecha":"2024-01-01","delito":"Delitos asociados a drogas","delito_n":3},
        {"comuna":"Iquique","cut_comuna":1101,"region":"Tarapacá","cut_region":1,"fecha":"2024-02-01","delito":"Delitos asociados a drogas","delito_n":4},
        {"comuna":"Iquique","cut_comuna":1101,"region":"Tarapacá","cut_region":1,"fecha":"2025-01-01","delito":"Delitos asociados a drogas","delito_n":5},
    ])
    clean,stats=normalize_bridge_frame(df,2020)
    annual=annualize_bridge(clean)
    assert stats["communes"]==1
    assert {r["year"] for r in annual}=={2024,2025}
    row=[r for r in annual if r["year"]==2024][0]
    assert row["commune_code"]=="01101"
    assert row["value"]==7
    assert row["source_tier"]=="mirror_of_primary"


def test_direct_precedence_and_homicide_exclusion():
    bridge=[{"year":2025,"period":"2025","territory_level":"commune","territory_id":"CL-01101","commune_code":"01101","commune_name":"Iquique","region_code":"01","region_name":"Tarapacá","crime_category":"Delitos asociados a drogas","metric":"casos_policiales","value":100,"source_id":"cead_community_bridge","ultimate_source_id":"cead_estadisticas_delictuales","source_tier":"mirror_of_primary","quality_status":"usable_bridge"}]
    direct=[dict(bridge[0],value=110,source_id="cead_direct_post",source_tier="primary_direct",quality_status="usable")]
    master=merge_annual_sources(direct,bridge)
    assert len(master)==1
    assert master[0]["value"]==110
    assert master[0]["source_tier"]=="primary_direct"
    assert master[0]["score_eligible"] is True
    homicide=annotate_master([dict(bridge[0],crime_category="Homicidios")])[0]
    assert homicide["score_eligible"] is False
    assert homicide["aml_weight"]==0.0


def test_predicate_features_and_current_activity_are_longitudinal():
    master=annotate_master([
        {"year":2024,"period":"2024","territory_level":"commune","territory_id":"CL-01101","commune_code":"01101","commune_name":"Iquique","region_code":"01","region_name":"Tarapacá","crime_category":"Delitos asociados a drogas","metric":"casos_policiales","value":80,"source_id":"cead_community_bridge","source_tier":"mirror_of_primary","quality_status":"usable_bridge"},
        {"year":2025,"period":"2025","territory_level":"commune","territory_id":"CL-01101","commune_code":"01101","commune_name":"Iquique","region_code":"01","region_name":"Tarapacá","crime_category":"Delitos asociados a drogas","metric":"casos_policiales","value":100,"source_id":"cead_community_bridge","source_tier":"mirror_of_primary","quality_status":"usable_bridge"},
    ])
    features=build_predicate_features(master)
    assert len(features)==2
    activity=build_current_predicate_activity(master)
    assert activity[0]["year"]==2025
    assert activity[0]["yoy_pct"]==25.0
