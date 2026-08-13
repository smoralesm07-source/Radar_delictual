from __future__ import annotations

import re
import unicodedata


def _norm(value:str)->str:
    value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


def build_current_predicate_activity(master:list[dict])->list[dict]:
    """Volumen comunal reciente de la familia CEAD drogas, sin convertirlo en riesgo LA/FT.

    El indicador se mantiene como conteo de casos policiales y variación interanual.
    No se usa tasa inexistente ni se corrige por población con datos de otra unidad.
    """
    aliases={"delitos asociados a drogas","crimenes y simples delitos ley de drogas"}
    rows=[r for r in master if _norm(r.get("crime_category","")) in aliases and r.get("score_eligible")]
    if not rows: return []
    latest=max(int(r["year"]) for r in rows); previous=latest-1
    by={(int(r["year"]),r["commune_code"]):r for r in rows}
    out=[]
    for r in rows:
        if int(r["year"])!=latest: continue
        prev=by.get((previous,r["commune_code"])); now=int(r.get("value") or 0); prev_value=int(prev.get("value") or 0) if prev else None
        growth=None if prev_value in {None,0} else round((now-prev_value)*100.0/prev_value,1)
        out.append({
            "year":latest,"previous_year":previous,"territory_id":r["territory_id"],"region_code":r.get("region_code"),"region_name":r.get("region_name"),"commune_code":r.get("commune_code"),"commune_name":r.get("commune_name"),
            "crime_category":r.get("crime_category"),"cases_policiales":now,"previous_cases_policiales":prev_value,"yoy_pct":growth,
            "aml_class":r.get("aml_class"),"article27_mapping_key":r.get("article27_mapping_key"),"source_id":r.get("source_id"),"source_tier":r.get("source_tier"),"quality_status":r.get("quality_status"),
            "interpretation":"Actividad territorial reciente de una familia relacionada con delitos base. Es volumen de casos policiales; no es tasa, probabilidad de LA/FT ni atribución a residentes, empresas o sectores."
        })
    return sorted(out,key=lambda x:(x["cases_policiales"],x["commune_code"]),reverse=True)
