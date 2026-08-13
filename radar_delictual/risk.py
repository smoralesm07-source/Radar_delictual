import math
from collections import defaultdict

AML_CLASSES = {"base_19913", "proxy_19913"}
ORG_CLASSES = {"crimen_organizado_proxy"}


def _percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda kv: (kv[1], kv[0]))
    n = len(ordered)
    if n == 1:
        return {ordered[0][0]: 50.0}
    return {key: 100.0 * i / (n - 1) for i, (key, _) in enumerate(ordered)}


def build_region_risk(records: list[dict]) -> list[dict]:
    regional = [r for r in records if r.get("territory_level") == "region" and r.get("metric") == "delitos_ingresados"]
    years = sorted({int(r["year"]) for r in regional})
    if not years:
        return []
    by_year_region = defaultdict(list)
    national_category = defaultdict(int)
    national_total = defaultdict(int)
    for r in regional:
        y = int(r["year"])
        code = r["region_code"]
        by_year_region[(y, code)].append(r)
        national_category[(y, r["crime_category"])] += int(r["value"])
        national_total[y] += int(r["value"])
    signals = []
    previous_aml: dict[str, float] = {}
    for year in years:
        raw_aml, raw_org, diversity, names = {}, {}, {}, {}
        for (y, code), rows in by_year_region.items():
            if y != year:
                continue
            names[code] = rows[0]["region_name"]
            region_total = max(1, sum(int(r["value"]) for r in rows))
            aml = org = 0.0
            active_aml_categories = 0
            for r in rows:
                count = int(r["value"])
                cls = r.get("aml_class", "contexto_general")
                weight = float(r.get("weight", 0.1))
                nat_count = max(1, national_category[(year, r["crime_category"])])
                regional_share = count / region_total
                national_share = nat_count / max(1, national_total[year])
                concentration = regional_share / national_share if national_share else 0.0
                component = math.log1p(count) * max(0.25, min(3.0, concentration)) * weight
                if cls in AML_CLASSES:
                    aml += component
                    if count > 0:
                        active_aml_categories += 1
                elif cls in ORG_CLASSES:
                    org += component
            raw_aml[code], raw_org[code], diversity[code] = aml, org, float(active_aml_categories)
        p_aml, p_org, p_div = _percentile_ranks(raw_aml), _percentile_ranks(raw_org), _percentile_ranks(diversity)
        for code in sorted(names):
            if code in previous_aml and previous_aml[code] > 0:
                trend = 50.0 + 50.0 * max(-1.0, min(1.0, (raw_aml[code] - previous_aml[code]) / previous_aml[code]))
            else:
                trend = 50.0
            score = round(0.55*p_aml.get(code,0)+0.25*p_org.get(code,0)+0.10*trend+0.10*p_div.get(code,0),1)
            level = "muy_alta" if score >= 80 else "alta" if score >= 65 else "media" if score >= 40 else "baja"
            signals.append({"year":year,"region_code":code,"region_name":names[code],"pressure_score":score,"pressure_level":level,"aml_component_percentile":round(p_aml.get(code,0),1),"organized_crime_component_percentile":round(p_org.get(code,0),1),"trend_component":round(trend,1),"diversification_percentile":round(p_div.get(code,0),1),"method":"proxy_mp_v0.1","interpretation":"Presión delictual AML (proxy); no es probabilidad de LA/FT ni atribución de delito."})
        previous_aml = dict(raw_aml)
    return signals
