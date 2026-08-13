from __future__ import annotations

import math


def _percentile(values:dict[str,float])->dict[str,float]:
    if not values: return {}
    ordered=sorted(values.items(),key=lambda x:(x[1],x[0]))
    if len(ordered)==1: return {ordered[0][0]:50.0}
    return {k:100.0*i/(len(ordered)-1) for i,(k,_) in enumerate(ordered)}


def build_cead_commune_aml_priority(records:list[dict]) -> list[dict]:
    rows=[r for r in records if r.get("year")==2024 and r.get("cead_family_key")=="delitos_asociados_drogas" and r.get("quality_status")=="usable" and r.get("score_eligible") is True]
    if not rows: return []
    rates=[float(r["rate_100k"]) for r in rows if r.get("rate_100k") is not None]
    prior=sorted(rates)[len(rates)//2] if rates else 0.0
    shrunk={}; volume={}
    for r in rows:
        key=r["territory_id"]; rate=float(r.get("rate_100k") or 0); pop=int(r.get("population") or 0)
        reliability=pop/(pop+25000.0) if pop>0 else 0.45
        shrunk[key]=reliability*rate+(1-reliability)*prior
        freq=r.get("estimated_frequency")
        volume[key]=math.log1p(max(0,int(freq))) if freq is not None else 0.0
    p_rate=_percentile(shrunk); p_volume=_percentile(volume)
    out=[]
    for r in rows:
        key=r["territory_id"]
        has_volume=r.get("estimated_frequency") is not None
        score=round((0.70*p_rate[key]+0.30*p_volume[key]) if has_volume else p_rate[key],1)
        level="muy_alta" if score>=80 else "alta" if score>=65 else "media" if score>=40 else "baja"
        out.append({"year":2024,"period":"2024","territory_id":key,"region_code":r["region_code"],"region_name":r["region_name"],"commune_code":r.get("commune_code"),"commune_name":r["commune_name"],"commune_name_norm":r.get("commune_name_norm"),"cead_aml_priority_score":score,"priority_level":level,"drug_complaint_rate_100k":float(r["rate_100k"]),"population":r.get("population"),"estimated_drug_complaints":r.get("estimated_frequency"),"shrunk_drug_rate":round(shrunk[key],2),"rate_percentile":round(p_rate[key],1),"volume_percentile":round(p_volume[key],1) if has_volume else None,"article27_relation":"direct_family_ley_20000","legal_basis":"Ley 19.913 art. 27 → Ley 20.000","source_id":r["source_id"],"ultimate_source_id":r["ultimate_source_id"],"method":"cead_art27_commune_priority_v0.3","method_confidence":"high" if r.get("population") else "medium","interpretation":"Prioridad analítica territorial basada exclusivamente en denuncias CEAD de la familia drogas vinculada a Ley 20.000. No es probabilidad de LA/FT ni atribución a personas, empresas o sectores."})
    return sorted(out,key=lambda x:x["cead_aml_priority_score"],reverse=True)


def build_region_mp_priority(mp_risk:list[dict])->list[dict]:
    latest=max((r["year"] for r in mp_risk),default=None)
    if latest is None: return []
    out=[]
    for r in mp_risk:
        if r["year"]!=latest: continue
        x=dict(r); x["method"]="ministerio_publico_aml_proxy_v0.3"; x["interpretation"]="Proxy regional basado en categorías de delitos ingresados a SAF con relevancia AML. Homicidios y criminalidad general tienen peso cero."; out.append(x)
    return sorted(out,key=lambda x:x["pressure_score"],reverse=True)
