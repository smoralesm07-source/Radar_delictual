from __future__ import annotations

import re
import unicodedata


def _norm(value:str)->str:
    value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


def _preferred_drug_rows(master:list[dict])->list[dict]:
    """Una observación por comuna/año: prefiere familia CEAD sobre grupo agregado."""
    aliases={"delitos asociados a drogas":0,"crimenes y simples delitos ley de drogas":1}
    chosen={}
    for r in master:
        n=_norm(r.get("crime_category",""))
        if n not in aliases or not r.get("score_eligible"): continue
        key=(int(r["year"]),r.get("commune_code")); rank=aliases[n]
        if key not in chosen or rank<chosen[key][0]: chosen[key]=(rank,r)
    return [r for _,r in chosen.values()]


def build_current_predicate_activity(master:list[dict])->list[dict]:
    """Volumen comunal reciente de la familia CEAD drogas, sin convertirlo en riesgo LA/FT."""
    rows=_preferred_drug_rows(master)
    if not rows: return []
    latest=max(int(r["year"]) for r in rows); previous=latest-1
    by={(int(r["year"]),r["commune_code"]):r for r in rows}
    out=[]
    for r in rows:
        if int(r["year"])!=latest: continue
        prev=by.get((previous,r["commune_code"])); now=int(r.get("value") or 0); prev_value=int(prev.get("value") or 0) if prev else None
        growth=None if prev_value in {None,0} else round((now-prev_value)*100.0/prev_value,1)
        out.append({"year":latest,"previous_year":previous,"territory_id":r["territory_id"],"region_code":r.get("region_code"),"region_name":r.get("region_name"),"commune_code":r.get("commune_code"),"commune_name":r.get("commune_name"),"crime_category":r.get("crime_category"),"cases_policiales":now,"previous_cases_policiales":prev_value,"yoy_pct":growth,"aml_class":r.get("aml_class"),"article27_mapping_key":r.get("article27_mapping_key"),"source_id":r.get("source_id"),"source_tier":r.get("source_tier"),"quality_status":r.get("quality_status"),"interpretation":"Actividad territorial reciente de una familia relacionada con delitos base. Es volumen de casos policiales; no es tasa, probabilidad de LA/FT ni atribución a residentes, empresas o sectores."})
    return sorted(out,key=lambda x:(x["cases_policiales"],x["commune_code"]),reverse=True)
