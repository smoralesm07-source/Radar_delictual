from radar_delictual.homicides import _load_reference, _commune_records
from radar_delictual.risk_v2 import build_region_priority_v2, build_commune_homicide_pressure

def test_region_priority_has_16_regions():
    reg,c24,c25=_load_reference(); hom=[]
    for r in reg.itertuples(): hom.append({'region_code':str(r.region_code).zfill(2),'region_name':r.region_name,'territory_level':'region','period':r.period,'rate_100k':float(r.rate_100k),'value':int(r.victims)})
    pairs=[('01','Tarapacá'),('02','Antofagasta'),('03','Atacama'),('04','Coquimbo'),('05','Valparaíso'),('06',"Libertador General Bernardo O'Higgins"),('07','Maule'),('08','Biobío'),('09','La Araucanía'),('10','Los Lagos'),('11','Aysén del General Carlos Ibáñez del Campo'),('12','Magallanes y de la Antártica Chilena'),('13','Metropolitana de Santiago'),('14','Los Ríos'),('15','Arica y Parinacota'),('16','Ñuble')]
    mp=[{'year':2025,'region_code':code,'region_name':name,'pressure_score':50+i} for i,(code,name) in enumerate(pairs)]
    out=build_region_priority_v2(mp,hom); assert len(out)==16; assert all('no es probabilidad' in r['interpretation'].lower() for r in out)

def test_commune_pressure_has_205_complete_annual_communes():
    reg,c24,c25=_load_reference(); rows=_commune_records(c24,c25,None); out=build_commune_homicide_pressure(rows); assert len(out)==205
