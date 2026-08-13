from __future__ import annotations

import re
import unicodedata

import pandas as pd

from .cead_external import collect_external

EXPECTED_COLUMNS={"comuna","cut_comuna","region","cut_region","fecha","delito","delito_n"}


def _norm(value:str)->str:
    value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


def _code(value,width:int)->str|None:
    if pd.isna(value): return None
    try: return str(int(float(value))).zfill(width)
    except Exception: return None


def normalize_bridge_frame(frame:pd.DataFrame,start_year:int=2020):
    """Transformación pura conservada por compatibilidad; no descarga datos externos."""
    missing=EXPECTED_COLUMNS-set(frame.columns)
    if missing: raise ValueError(f"CEAD bridge schema missing columns: {sorted(missing)}")
    df=frame[list(EXPECTED_COLUMNS)].copy(); df["fecha"]=pd.to_datetime(df["fecha"],errors="coerce"); df["delito_n"]=pd.to_numeric(df["delito_n"],errors="coerce")
    df=df[df["fecha"].notna() & df["delito_n"].notna()].copy(); df=df[df["fecha"].dt.year>=int(start_year)].copy(); df["year"]=df["fecha"].dt.year.astype(int)
    df["commune_code"]=df["cut_comuna"].map(lambda x:_code(x,5)); df["region_code"]=df["cut_region"].map(lambda x:_code(x,2)); df["commune_name"]=df["comuna"].astype(str); df["region_name"]=df["region"].astype(str); df["offense"]=df["delito"].astype(str); df["offense_norm"]=df["offense"].map(_norm); df=df[df["commune_code"].notna()].copy()
    stats={"min_date":df["fecha"].min().date().isoformat() if len(df) else None,"max_date":df["fecha"].max().date().isoformat() if len(df) else None,"communes":int(df["commune_code"].nunique()),"offenses":int(df["offense"].nunique()),"years":sorted(df["year"].unique().tolist()) if len(df) else []}
    return df,stats


def annualize_bridge(df:pd.DataFrame)->list[dict]:
    keys=["year","commune_code","commune_name","region_code","region_name","offense","offense_norm"]; annual=df.groupby(keys,dropna=False,as_index=False)["delito_n"].sum(min_count=1); out=[]
    for r in annual.to_dict("records"):
        out.append({"year":int(r["year"]),"period":str(int(r["year"])),"territory_level":"commune","territory_id":f"CL-{r['commune_code']}","commune_code":r["commune_code"],"commune_name":r["commune_name"],"region_code":r["region_code"],"region_name":r["region_name"],"crime_category":r["offense"],"crime_category_norm":r["offense_norm"],"metric":"casos_policiales","value":int(round(float(r["delito_n"]))),"source_id":"cead_community_bridge","ultimate_source_id":"cead_estadisticas_delictuales","source_tier":"mirror_of_primary","quality_status":"usable_bridge"})
    return out


def collect_cead_bridge(start_year:int=2020):
    """Radar Delictual consume CEAD-Data-Pipeline; no extrae CEAD ni su réplica."""
    return collect_external(start_year)


def drug_family_rows(records:list[dict])->list[dict]:
    aliases={"delitos asociados a drogas","crimenes y simples delitos ley de drogas"}
    return [r for r in records if _norm(r.get("crime_category","")) in aliases]
