from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from datetime import datetime, timezone

import pandas as pd
import requests

UPSTREAM_REPO = "bastianolea/delincuencia_chile"
UPSTREAM_PATH = "datos/procesados/cead_delincuencia_chile.parquet"
CONTENT_API = f"https://api.github.com/repos/{UPSTREAM_REPO}/contents/{UPSTREAM_PATH}"
RAW_URL = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/main/{UPSTREAM_PATH}"
LICENSE = "GPL-3.0"
EXPECTED_COLUMNS = {"comuna","cut_comuna","region","cut_region","fecha","delito","delito_n"}


def _norm(value:str) -> str:
    value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


def _code(value, width:int) -> str | None:
    if pd.isna(value): return None
    try: return str(int(float(value))).zfill(width)
    except Exception: return None


def fetch_upstream_snapshot(timeout:int=60) -> tuple[bytes,dict]:
    meta={"repo":UPSTREAM_REPO,"path":UPSTREAM_PATH,"license":LICENSE}
    download_url=RAW_URL
    try:
        m=requests.get(CONTENT_API,headers={"Accept":"application/vnd.github+json","User-Agent":"RadarDelictual/0.4"},timeout=20)
        if m.ok:
            doc=m.json(); download_url=doc.get("download_url") or RAW_URL
            meta.update({"upstream_blob_sha":doc.get("sha"),"upstream_size":doc.get("size")})
    except Exception:
        pass
    r=requests.get(download_url,headers={"User-Agent":"RadarDelictual/0.4"},timeout=timeout)
    r.raise_for_status(); content=r.content
    meta.update({"download_url":download_url,"retrieved_at":datetime.now(timezone.utc).isoformat(),"bytes":len(content),"content_sha256":hashlib.sha256(content).hexdigest()})
    return content,meta


def normalize_bridge_frame(frame:pd.DataFrame, start_year:int=2020) -> tuple[pd.DataFrame,dict]:
    missing=EXPECTED_COLUMNS-set(frame.columns)
    if missing: raise ValueError(f"CEAD bridge schema missing columns: {sorted(missing)}")
    df=frame[list(EXPECTED_COLUMNS)].copy()
    df["fecha"]=pd.to_datetime(df["fecha"],errors="coerce")
    df["delito_n"]=pd.to_numeric(df["delito_n"],errors="coerce")
    df=df[df["fecha"].notna() & df["delito_n"].notna()].copy()
    df=df[df["fecha"].dt.year>=int(start_year)].copy()
    df["year"]=df["fecha"].dt.year.astype(int)
    df["commune_code"]=df["cut_comuna"].map(lambda x:_code(x,5))
    df["region_code"]=df["cut_region"].map(lambda x:_code(x,2))
    df["commune_name"]=df["comuna"].astype(str)
    df["region_name"]=df["region"].astype(str)
    df["offense"]=df["delito"].astype(str)
    df["offense_norm"]=df["offense"].map(_norm)
    df=df[df["commune_code"].notna()].copy()
    stats={
        "min_date":df["fecha"].min().date().isoformat() if len(df) else None,
        "max_date":df["fecha"].max().date().isoformat() if len(df) else None,
        "communes":int(df["commune_code"].nunique()),"offenses":int(df["offense"].nunique()),
        "monthly_rows":int(len(df)),"years":sorted(df["year"].unique().tolist()) if len(df) else []
    }
    return df,stats


def annualize_bridge(df:pd.DataFrame) -> list[dict]:
    keys=["year","commune_code","commune_name","region_code","region_name","offense","offense_norm"]
    annual=df.groupby(keys,dropna=False,as_index=False)["delito_n"].sum(min_count=1)
    out=[]
    for r in annual.to_dict("records"):
        out.append({
            "year":int(r["year"]),"period":str(int(r["year"])),"territory_level":"commune",
            "territory_id":f"CL-{r['commune_code']}","commune_code":r["commune_code"],"commune_name":r["commune_name"],
            "region_code":r["region_code"],"region_name":r["region_name"],"crime_category":r["offense"],"crime_category_norm":r["offense_norm"],
            "metric":"casos_policiales","value":int(round(float(r["delito_n"]))),"observation_unit":"caso_policial",
            "source_id":"cead_community_bridge","ultimate_source_id":"cead_estadisticas_delictuales",
            "source_tier":"mirror_of_primary","quality_status":"usable_bridge","acquisition_method":"processed_mirror_of_direct_cead_scrape"
        })
    return out


def commune_dictionary(df:pd.DataFrame) -> list[dict]:
    cols=["commune_code","commune_name","region_code","region_name"]
    d=df[cols].drop_duplicates().sort_values(["region_code","commune_code"])
    return d.to_dict("records")


def collect_cead_bridge(start_year:int=2020) -> tuple[list[dict],list[dict],dict,list[dict]]:
    content,meta=fetch_upstream_snapshot()
    frame=pd.read_parquet(io.BytesIO(content),engine="pyarrow")
    df,stats=normalize_bridge_frame(frame,start_year=start_year)
    valid=stats["communes"]>=340 and bool(stats["max_date"]) and stats["max_date"]>="2025-12-01"
    meta.update(stats)
    meta.update({"source_id":"cead_community_bridge","ultimate_source_id":"cead_estadisticas_delictuales","source_tier":"mirror_of_primary","provenance":"Repositorio público documenta extracción mediante POST a la interfaz CEAD; el radar verifica esquema, cobertura, fechas y hash del archivo, pero no presenta la réplica como fuente oficial.","ok":valid})
    if not valid: raise ValueError(f"CEAD bridge failed coverage/freshness checks: {stats}")
    evidence=[{"evidence_id":"cead:bridge:parquet","source_id":"cead_community_bridge","url":meta.get("download_url"),"retrieved_at":meta["retrieved_at"],"sha256":meta["content_sha256"],"bytes":meta["bytes"],"upstream_blob_sha":meta.get("upstream_blob_sha"),"license":LICENSE,"observation_unit":"serie_mensual_casos_policiales"}]
    return annualize_bridge(df),evidence,meta,commune_dictionary(df)


def drug_family_rows(records:list[dict]) -> list[dict]:
    aliases={"delitos asociados a drogas","crimenes y simples delitos ley de drogas"}
    return [r for r in records if _norm(r.get("crime_category","")) in aliases]
