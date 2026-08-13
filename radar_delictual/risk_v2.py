from __future__ import annotations
import math


def _pr(values: dict[str,float]) -> dict[str,float]:
    if not values: return {}
    ordered = sorted(values.items(), key=lambda x:(x[1],x[0]))
    if len(ordered)==1: return {ordered[0][0]:50.0}
    return {k:100*i/(len(ordered)-1) for i,(k,_) in enumerate(ordered)}


def build_region_priority_v2(mp_risk: list[dict], homicide_metrics: list[dict]) -> list[dict]:
    latest_mp_year = max((r["year"] for r in mp_risk), default=None)
    mp = {r["region_code"]:r for r in mp_risk if r["year"]==latest_mp_year}
    annual = {r["region_code"]:r for r in homicide_metrics if r.get("territory_level")=="region" and r.get("period")=="2024"}
    h1_24 = {r["region_code"]:r for r in homicide_metrics if r.get("territory_level")=="region" and r.get("period")=="2024-H1"}
    h1_25 = {r["region_code"]:r for r in homicide_metrics if r.get("territory_level")=="region" and r.get("period")=="2025-H1"}
    p_annual = _pr({k:float(v["rate_100k"]) for k,v in annual.items()})
    p_recent = _pr({k:float(v["rate_100k"]) for k,v in h1_25.items()})
    out=[]
    for code, base in mp.items():
        a, r25, r24 = annual.get(code), h1_25.get(code), h1_24.get(code)
        if not (a and r25 and r24): continue
        delta = (float(r25["rate_100k"])-float(r24["rate_100k"]))/max(float(r24["rate_100k"]),0.1)
        trend = max(0.0,min(100.0,50+50*max(-1,min(1,delta))))
        score = round(.60*float(base["pressure_score"])+.20*p_annual[code]+.15*p_recent[code]+.05*trend,1)
        level = "muy_alta" if score>=80 else "alta" if score>=65 else "media" if score>=40 else "baja"
        out.append({"year":latest_mp_year,"period":"2025-H1","region_code":code,"region_name":base["region_name"],"territorial_priority_score":score,"priority_level":level,"mp_aml_proxy_score":float(base["pressure_score"]),"homicide_2024_rate":float(a["rate_100k"]),"homicide_2024_percentile":round(p_annual[code],1),"homicide_h1_2025_rate":float(r25["rate_100k"]),"homicide_h1_2025_percentile":round(p_recent[code],1),"homicide_h1_rate_change_pct":round(delta*100,1),"recent_trend_component":round(trend,1),"method":"territorial_priority_v0.2","interpretation":"Prioridad territorial analítica AML/OSINT; no es probabilidad de LA/FT ni atribución de criminalidad a personas o sectores."})
    return sorted(out,key=lambda x:x["territorial_priority_score"],reverse=True)


def build_commune_homicide_pressure(homicide_metrics: list[dict]) -> list[dict]:
    annual = [r for r in homicide_metrics if r.get("territory_level")=="commune" and r.get("period")=="2024"]
    shrunk, volume, recent = {}, {}, {}
    for r in annual:
        key=r["territory_id"]; pop=max(1,int(r["population"])); reliability=pop/(pop+50000.0)
        shrunk[key]=reliability*float(r["rate_100k"])+(1-reliability)*6.0
        volume[key]=math.log1p(int(r["value"])); recent[key]=float(r.get("recent_h1_2025_victims",0))
    pr_rate,pr_vol,pr_recent=_pr(shrunk),_pr(volume),_pr(recent)
    out=[]
    for r in annual:
        key=r["territory_id"]
        score=round(.55*pr_rate[key]+.25*pr_vol[key]+.20*pr_recent[key],1)
        level="muy_alta" if score>=80 else "alta" if score>=65 else "media" if score>=40 else "baja"
        out.append({"year":2024,"recent_period":"2025-H1","territory_id":key,"region_code":r["region_code"],"region_name":r["region_name"],"commune_code":r.get("commune_code"),"commune_name":r["commune_name"],"homicide_pressure_score":score,"pressure_level":level,"victims_2024":int(r["value"]),"rate_100k_2024":float(r["rate_100k"]),"population_2024":int(r["population"]),"shrunk_rate_2024":round(shrunk[key],2),"victims_h1_2025":int(r.get("recent_h1_2025_victims",0)),"method":"homicide_pressure_v0.2","interpretation":"Señal territorial de violencia homicida estabilizada por población y volumen; no es un score AML ni una medición de crimen organizado."})
    return sorted(out,key=lambda x:x["homicide_pressure_score"],reverse=True)
