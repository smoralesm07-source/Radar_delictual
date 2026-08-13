from pathlib import Path
import pandas as pd
from radar_delictual.homicides import _load_reference, validate_reference, parse_cut_workbook
from radar_delictual.risk_v2 import build_commune_homicide_pressure

def test_reference_totals_match_official_reports():
    reg,c24,c25=_load_reference(); validate_reference(reg,c24,c25); assert int(c24.victims.sum())==1207; assert int(c25.victims.sum())==511; assert len(c24)==205

def test_small_population_rate_is_shrunk():
    reg,c24,c25=_load_reference(); from radar_delictual.homicides import _commune_records; rows=_commune_records(c24,c25,None); scores=build_commune_homicide_pressure(rows); colchane=next(r for r in scores if r['commune_name']=='Colchane'); assert colchane['shrunk_rate_2024'] < colchane['rate_100k_2024']; assert scores[0]['homicide_pressure_score'] >= colchane['homicide_pressure_score']

def test_cut_parser_synthetic(tmp_path:Path):
    p=tmp_path/'cut.xlsx'; rows=[['Código Región','Nombre Región','Código Provincia','Nombre Provincia','Código Comuna','Nombre Comuna']]
    for i in range(300): rows.append([13,'Metropolitana',131,'Santiago',13000+i,f'Comuna {i}'])
    pd.DataFrame(rows).to_excel(p,index=False,header=False); out=parse_cut_workbook(p); assert len(out)>=300; assert out['comuna 1']['commune_code']=='13001'
