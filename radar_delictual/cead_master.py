from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone

from .config import CONFIG_DIR

SOURCE_RANK={"primary_direct":10,"mirror_of_primary":20,"official_secondary":30,"quarantined":90}


def _norm(value:str)->str:
    value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


def load_catalog_v4()->dict:
    return json.loads((CONFIG_DIR/"cead_catalog_v4.json").read_text(encoding="utf-8"))


def legal_mapping_for_label(label:str,catalog:dict|None=None)->dict:
    catalog=catalog or load_catalog_v4(); n=_norm(label)
    direct={"delitos asociados a drogas":"family:4","crimenes y simples delitos ley de drogas":"group:401","trafico de sustancias":"subgroup:40101","microtrafico de sustancias":"subgroup:40102","elaboracion o produccion de sustancias":"subgroup:40103","otras infracciones a la ley de drogas":"subgroup:40104","homicidios":"subgroup:10101","femicidios":"subgroup:10102","homicidios y femicidios":"group:101","delitos asociados a armas":"family:5","crimenes y simples delitos ley de armas":"group:501","disparo injustificado":"subgroup:50101","porte posesion de armas o explosivos":"subgroup:50102","otras infracciones a la ley de armas":"subgroup:50103","violaciones y delitos sexuales":"group:102","violaciones y otros delitos sexuales":"group:102"}
    key=direct.get(n); mapping=(catalog.get("aml_mapping") or {}).get(key) if key else None
    if not mapping: mapping=(catalog.get("aml_mapping") or {}).get("default",{})
    return {"mapping_key":key or "default",**mapping}


def annotate_master(records:list[dict],catalog:dict|None=None)->list[dict]:
    catalog=catalog or load_catalog_v4(); out=[]
    for row in records:
        r=dict(row); m=legal_mapping_for_label(r.get("crime_category",""),catalog)
        r.update({"article27_mapping_key":m.get("mapping_key"),"aml_class":m.get("class"),"score_eligible":bool(m.get("score_eligible",False)),"aml_weight":float(m.get("weight",0.0)),"mapping_confidence":m.get("confidence","low"),"legal_basis":m.get("basis","")})
        if _norm(r.get("crime_category","")) in {"homicidios","femicidios","homicidios y femicidios"}: r.update({"score_eligible":False,"aml_weight":0.0,"aml_class":"context_only"})
        out.append(r)
    return out


def merge_annual_sources(direct:list[dict],bridge:list[dict])->list[dict]:
    chosen={}
    for row in bridge+direct:
        r=dict(row); tier=r.get("source_tier","quarantined")
        if not r.get("commune_code") or r.get("metric")!="casos_policiales": continue
        key=(int(r["year"]),str(r["commune_code"]).zfill(5),_norm(r.get("crime_category",""))); rank=SOURCE_RANK.get(tier,99)
        if key not in chosen or rank<chosen[key][0]: chosen[key]=(rank,r)
    out=[]
    for _,r in chosen.values(): r["source_rank"]=SOURCE_RANK.get(r.get("source_tier"),99); out.append(r)
    return annotate_master(sorted(out,key=lambda x:(x["year"],x["commune_code"],_norm(x.get("crime_category","")))))


def merge_direct_cache(existing:list[dict],new_rows:list[dict])->list[dict]:
    chosen={}
    for r in existing+new_rows:
        key=(int(r["year"]),str(r.get("commune_code") or "").zfill(5),_norm(r.get("crime_category",""))); chosen[key]=r
    return sorted(chosen.values(),key=lambda x:(x["year"],x.get("commune_code",""),_norm(x.get("crime_category",""))))


def build_predicate_features(master:list[dict])->list[dict]:
    rows=[]
    for r in master:
        if not r.get("score_eligible") or float(r.get("aml_weight",0))<=0: continue
        rows.append({"territory_id":r["territory_id"],"geography_level":"commune","region_code":r.get("region_code"),"commune_code":r.get("commune_code"),"commune_name":r.get("commune_name"),"period":str(r["year"]),"year":int(r["year"]),"signal_family":"cead_predicate_offense","crime_category":r.get("crime_category"),"metric":"casos_policiales","value":int(r.get("value") or 0),"article27_mapping_key":r.get("article27_mapping_key"),"aml_class":r.get("aml_class"),"aml_weight":r.get("aml_weight"),"mapping_confidence":r.get("mapping_confidence"),"source_id":r.get("source_id"),"source_tier":r.get("source_tier"),"ultimate_source_id":"cead_estadisticas_delictuales","quality_status":r.get("quality_status"),"excludes_homicide_weight":True})
    return rows


def build_manifest(probe:dict,bridge_meta:dict,master:list[dict],direct_cache:list[dict],bcn_control_count:int)->dict:
    years=sorted({int(r["year"]) for r in master}); communes={r.get("commune_code") for r in master if r.get("commune_code")}; offenses={_norm(r.get("crime_category","")) for r in master}; direct_years=sorted({int(r["year"]) for r in direct_cache})
    expected=int(bridge_meta.get("expected_communes") or 346); missing=bridge_meta.get("missing_expected_communes") or []
    externalized=bool(probe.get("externalized")) or bridge_meta.get("source_id")=="cead_data_pipeline_external"
    active="external_cead_data_pipeline" if externalized else ("primary_direct" if direct_cache and probe.get("ok") else "mirror_of_primary")
    policy="Consumir el snapshot validado publicado por CEAD-Data-Pipeline. La adquisición, sonda primaria, continuidad y QA de CEAD se administran fuera de Radar Delictual. Radar conserva control BCN secundario y nunca sustituye ausencia por cero." if externalized else "Mantener precedencia de fuentes y nunca sustituir ausencia por cero."
    return {"version":"0.5.0","generated_at":datetime.now(timezone.utc).isoformat(),"source_precedence":["external_cead_data_pipeline","official_secondary","quarantined"],"primary_probe":probe,"active_backbone":active,"bridge_snapshot":bridge_meta,"coverage":{"years":years,"expected_communes":expected,"observed_communes":len(communes),"unavailable_communes":missing,"offenses":len(offenses),"records":len(master),"direct_years":direct_years,"bcn_control_records":bcn_control_count},"last_primary_period":None if externalized else (probe.get("latest_nonzero_period") if probe.get("ok") else None),"update_policy":policy}
