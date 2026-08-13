from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from .config import RAW_DIR, REFERENCE_DIR, TIMEOUT_SECONDS, USER_AGENT

HOMICIDE_2024_URL = "https://prevenciondehomicidios.cl/wp-content/uploads/2025/08/INFORME_HOMICIDIOS_2024.pdf"
HOMICIDE_H1_2025_URL = "https://prevenciondehomicidios.cl/wp-content/uploads/2025/09/Informe_primer_semestre_2025.pdf"
CUT_URL = "https://www.subdere.gov.cl/sites/default/files/documentos/CUT_2018_v04.xls"

REGION_CODES = {"arica y parinacota":"15","tarapaca":"01","antofagasta":"02","atacama":"03","coquimbo":"04","valparaiso":"05","metropolitana":"13","metropolitana de santiago":"13","o'higgins":"06","libertador general bernardo o'higgins":"06","maule":"07","nuble":"16","biobio":"08","la araucania":"09","los rios":"14","los lagos":"10","aysen":"11","aysen del general carlos ibanez del campo":"11","magallanes":"12","magallanes y de la antartica chilena":"12"}
CANONICAL_REGION = {"15":"Arica y Parinacota","01":"Tarapacá","02":"Antofagasta","03":"Atacama","04":"Coquimbo","05":"Valparaíso","13":"Metropolitana de Santiago","06":"Libertador General Bernardo O'Higgins","07":"Maule","16":"Ñuble","08":"Biobío","09":"La Araucanía","14":"Los Ríos","10":"Los Lagos","11":"Aysén del General Carlos Ibáñez del Campo","12":"Magallanes y de la Antártica Chilena"}

def _norm(value:str)->str:
    value=unicodedata.normalize("NFKD",str(value)).encode("ascii","ignore").decode("ascii")
    value=value.lower().replace("’","'").replace("`", "'")
    return re.sub(r"[^a-z0-9']+"," ",value).strip()

def _slug(value:str)->str: return re.sub(r"[^a-z0-9]+","-",_norm(value)).strip("-")

def _sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def _download(url:str,filename:str)->tuple[Path,dict]:
    path=RAW_DIR/filename; r=requests.get(url,timeout=TIMEOUT_SECONDS,headers={"User-Agent":USER_AGENT}); r.raise_for_status(); path.write_bytes(r.content)
    return path,{"url":url,"retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":_sha256(path),"bytes":path.stat().st_size}

def parse_cut_workbook(path:Path)->dict[str,dict]:
    xls=pd.ExcelFile(path); found={}
    for sheet in xls.sheet_names:
        raw=pd.read_excel(path,sheet_name=sheet,header=None); header_row=code_idx=name_idx=region_idx=None
        for i in range(min(20,len(raw))):
            headers=[_norm(x) for x in raw.iloc[i].fillna("").tolist()]
            ci=next((j for j,h in enumerate(headers) if "comuna" in h and ("codigo" in h or "cut" in h)),None)
            ni=next((j for j,h in enumerate(headers) if "comuna" in h and ("nombre" in h or h=="comuna")),None)
            ri=next((j for j,h in enumerate(headers) if "region" in h and "nombre" in h),None)
            if ci is not None and ni is not None: header_row,code_idx,name_idx,region_idx=i,ci,ni,ri; break
        if header_row is not None:
            for _,row in raw.iloc[header_row+1:].iterrows():
                code_raw,name_raw=row.iloc[code_idx],row.iloc[name_idx]
                if pd.isna(code_raw) or pd.isna(name_raw): continue
                digits=re.sub(r"\D","",str(code_raw).split(".")[0])
                if len(digits)<4 or len(digits)>5: continue
                code=digits.zfill(5); name=str(name_raw).strip(); region=str(row.iloc[region_idx]).strip() if region_idx is not None and not pd.isna(row.iloc[region_idx]) else None
                found[_norm(name)]={"commune_code":code,"commune_name_cut":name,"region_name_cut":region}
        if len(found)>=300: break
    if len(found)<300:
        for sheet in xls.sheet_names:
            raw=pd.read_excel(path,sheet_name=sheet,header=None); cols=list(range(raw.shape[1])); code_cols=[]
            for c in cols:
                vals=raw.iloc[:,c].dropna().astype(str).str.replace(r"\.0$","",regex=True); ratio=vals.str.fullmatch(r"\d{4,5}").mean() if len(vals) else 0
                if ratio>.5: code_cols.append(c)
            text_cols=[c for c in cols if raw.iloc[:,c].astype(str).str.contains("Santiago|Arica|Iquique|Valpara",case=False,regex=True).any()]
            for ci in code_cols:
                for ni in text_cols:
                    for _,row in raw.iterrows():
                        code_raw,name_raw=row.iloc[ci],row.iloc[ni]; digits=re.sub(r"\D","",str(code_raw).split(".")[0])
                        if len(digits) not in (4,5) or pd.isna(name_raw): continue
                        name=str(name_raw).strip()
                        if len(name)<2: continue
                        found.setdefault(_norm(name),{"commune_code":digits.zfill(5),"commune_name_cut":name,"region_name_cut":None})
            if len(found)>=300: break
    if len(found)<300: raise ValueError(f"CUT incompleto: solo {len(found)} comunas reconocidas")
    return found

def _load_reference()->tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    reg=pd.read_csv(REFERENCE_DIR/"homicides_regions.csv",dtype={"region_code":str}); c24=pd.read_csv(REFERENCE_DIR/"homicides_2024_communes.csv"); c25=pd.read_csv(REFERENCE_DIR/"homicides_h1_2025_communes.csv"); reg["region_code"]=reg["region_code"].str.zfill(2); return reg,c24,c25

def validate_reference(reg,c24,c25)->None:
    annual_2024=reg[(reg.period_type=="annual")&(reg.year==2024)]; h1_2025=reg[reg.period=="2025-H1"]
    assert int(annual_2024.victims.sum())==1207; assert int(c24.victims.sum())==1207; assert int(h1_2025.victims.sum())==511; assert int(c25.victims.sum())==511
    for region,group in c24.groupby("region_name"):
        code=REGION_CODES[_norm(region)]; expected=int(annual_2024.loc[annual_2024.region_code==code,"victims"].iloc[0]); assert int(group.victims.sum())==expected,(region,int(group.victims.sum()),expected)

def _commune_records(c24,c25,cut_map):
    recent={(_norm(r.region_name),_norm(r.commune_name)):int(r.victims) for r in c25.itertuples()}; records=[]
    for r in c24.itertuples():
        region_code=REGION_CODES[_norm(r.region_name)]; cut=(cut_map or {}).get(_norm(r.commune_name),{}); commune_code=cut.get("commune_code"); key=(_norm(r.region_name),_norm(r.commune_name))
        records.append({"year":2024,"period":"2024","period_type":"annual","territory_level":"commune","region_code":region_code,"region_name":CANONICAL_REGION[region_code],"commune_code":commune_code,"commune_name":r.commune_name,"territory_id":f"CL-{commune_code}" if commune_code else f"CL-{region_code}-{_slug(r.commune_name)}","crime_category":"HOMICIDIO CONSUMADO - VÍCTIMAS","metric":"victimas_homicidio_consumado","value":int(r.victims),"rate_100k":float(r.rate_100k),"population":int(r.population),"recent_h1_2025_victims":recent.get(key,0),"recent_h1_2025_status":"observed_positive" if key in recent else "derived_zero_not_listed_in_complete_positive_table","source_id":"homicidios_interinstitucional_2024","observation_unit":"victima_homicidio_consumado","data_status":"observed_official_table","aml_class":"crimen_organizado_proxy","weight":0.65})
    existing={(_norm(x["region_name"]),_norm(x["commune_name"])) for x in records}
    for r in c25.itertuples():
        key=(_norm(r.region_name),_norm(r.commune_name))
        if key in existing: continue
        region_code=REGION_CODES[_norm(r.region_name)]; cut=(cut_map or {}).get(_norm(r.commune_name),{}); commune_code=cut.get("commune_code")
        records.append({"year":2025,"period":"2025-H1","period_type":"h1","territory_level":"commune","region_code":region_code,"region_name":CANONICAL_REGION[region_code],"commune_code":commune_code,"commune_name":r.commune_name,"territory_id":f"CL-{commune_code}" if commune_code else f"CL-{region_code}-{_slug(r.commune_name)}","crime_category":"HOMICIDIO CONSUMADO - VÍCTIMAS","metric":"victimas_homicidio_consumado","value":int(r.victims),"rate_100k":None,"population":None,"recent_h1_2025_victims":int(r.victims),"source_id":"homicidios_interinstitucional_h1_2025","observation_unit":"victima_homicidio_consumado","data_status":"observed_official_table_partial","aml_class":"crimen_organizado_proxy","weight":0.65})
    return records

def collect_homicide_official(download_evidence:bool=True)->tuple[list[dict],list[dict],list[dict]]:
    reg,c24,c25=_load_reference(); validate_reference(reg,c24,c25); evidence=[]; status=[]
    for filename,sid,source_url in [("homicides_regions.csv","reference:homicides_regions_v0.2",HOMICIDE_2024_URL),("homicides_2024_communes.csv","reference:homicides_communes_2024_v0.2",HOMICIDE_2024_URL),("homicides_h1_2025_communes.csv","reference:homicides_communes_h1_2025_v0.2",HOMICIDE_H1_2025_URL)]:
        ref_path=REFERENCE_DIR/filename; evidence.append({"evidence_id":sid,"source_id":sid,"url":source_url,"reference_path":f"data/reference/{filename}","retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":_sha256(ref_path),"bytes":ref_path.stat().st_size,"observation_unit":"tabla_transcrita_y_validada_desde_informe_oficial","provenance_status":"audited_reference"})
    cut_map=None
    if download_evidence:
        for sid,url,filename in [("homicidios_interinstitucional_2024",HOMICIDE_2024_URL,"homicidios_2024.pdf"),("homicidios_interinstitucional_h1_2025",HOMICIDE_H1_2025_URL,"homicidios_h1_2025.pdf")]:
            try:
                _,ev=_download(url,filename); ev.update({"evidence_id":sid,"source_id":sid,"observation_unit":"victima_homicidio_consumado"}); evidence.append(ev); status.append({"source_id":sid,"ok":True,"evidence_sha256":ev["sha256"]})
            except Exception as exc: status.append({"source_id":sid,"ok":False,"error":f"{type(exc).__name__}: {exc}","reference_table_available":True})
        try:
            cut_path,ev=_download(CUT_URL,"CUT_2018_v04.xls"); cut_map=parse_cut_workbook(cut_path); ev.update({"evidence_id":"subdere_cut_2018","source_id":"subdere_cut_2018","observation_unit":"codigo_unico_territorial"}); evidence.append(ev); status.append({"source_id":"subdere_cut_2018","ok":True,"communes":len(cut_map)})
        except Exception as exc: status.append({"source_id":"subdere_cut_2018","ok":False,"error":f"{type(exc).__name__}: {exc}","fallback":"territory_id slug estable"})
    records=[]
    for r in reg.itertuples():
        records.append({"year":int(r.year),"period":r.period,"period_type":r.period_type,"territory_level":"region","region_code":str(r.region_code).zfill(2),"region_name":r.region_name,"commune_code":None,"commune_name":None,"territory_id":f"CL-{str(r.region_code).zfill(2)}","crime_category":"HOMICIDIO CONSUMADO - VÍCTIMAS","metric":"victimas_homicidio_consumado","value":int(r.victims),"rate_100k":float(r.rate_100k),"source_id":"homicidios_interinstitucional_2024" if r.period_type=="annual" else "homicidios_interinstitucional_h1_2025","observation_unit":"victima_homicidio_consumado","data_status":"observed_official_table","aml_class":"crimen_organizado_proxy","weight":0.65})
    records.extend(_commune_records(c24,c25,cut_map)); return records,evidence,status
