from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
import requests

DATA_REPO="smoralesm07-source/CEAD-Data-Pipeline"
BASE=f"https://raw.githubusercontent.com/{DATA_REPO}/data/data/processed"
ANNUAL_URL=f"{BASE}/cead_annual.parquet"
MANIFEST_URL=f"{BASE}/manifest.json"
EXPECTED={"year","commune_code","commune_name","region_code","region_name","crime_category","metric","value"}


def collect_external(start_year:int=2020):
    headers={"User-Agent":"RadarDelictual/0.5 CEAD-consumer"}
    mr=requests.get(MANIFEST_URL,headers=headers,timeout=30); mr.raise_for_status(); manifest=mr.json()
    r=requests.get(ANNUAL_URL,headers=headers,timeout=90); r.raise_for_status()
    df=pd.read_parquet(io.BytesIO(r.content),engine="pyarrow")
    missing=EXPECTED-set(df.columns)
    if missing: raise ValueError(f"External CEAD schema missing: {sorted(missing)}")
    df=df[pd.to_numeric(df["year"],errors="coerce")>=int(start_year)].copy(); df["year"]=df["year"].astype(int); df["value"]=pd.to_numeric(df["value"],errors="coerce"); df=df[df["value"].notna()].copy()
    df["territory_level"]="commune"; df["observation_unit"]="caso_policial"; df["acquisition_method"]="external_cead_data_pipeline"
    records=df.to_dict("records")
    for row in records:
        row["value"]=int(round(float(row["value"]))); row["period"]=str(row.get("period") or row["year"]); row["ultimate_source_id"]=row.get("ultimate_source_id") or "cead_estadisticas_delictuales"
    communes=df[["commune_code","commune_name","region_code","region_name"]].drop_duplicates().sort_values(["region_code","commune_code"]).to_dict("records")
    coverage=manifest.get("coverage",{}); meta={"source_id":"cead_data_pipeline_external","producer_repo":DATA_REPO,"producer_manifest":manifest,"retrieved_at":datetime.now(timezone.utc).isoformat(),"communes":coverage.get("communes",df["commune_code"].nunique()),"expected_communes":coverage.get("expected_communes",346),"offenses":coverage.get("offenses",df["crime_category"].nunique()),"min_date":coverage.get("min_date"),"max_date":coverage.get("max_date"),"years":coverage.get("years",sorted(df["year"].unique().tolist())),"ok":len(records)>0 and df["commune_code"].nunique()>=340}
    evidence=[{"evidence_id":"cead:external:annual","source_id":"cead_data_pipeline_external","ultimate_source_id":"cead_estadisticas_delictuales","url":ANNUAL_URL,"retrieved_at":meta["retrieved_at"],"bytes":len(r.content),"producer_repo":DATA_REPO}]
    return records,evidence,meta,communes
