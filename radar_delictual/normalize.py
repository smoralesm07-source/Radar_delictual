from collections import defaultdict


def add_national_rollups(records: list[dict]) -> list[dict]:
    grouped = defaultdict(int)
    for r in records:
        if r.get("territory_level") != "region":
            continue
        key = (r["year"], r["crime_category"], r["metric"], r["source_id"])
        grouped[key] += int(r["value"])
    output = list(records)
    for (year, category, metric, source_id), value in grouped.items():
        output.append({"year":year,"region_code":"CL","region_name":"Chile","crime_category":category,"value":value,"territory_level":"national","metric":metric,"rate_100k":None,"source_id":source_id,"source_year":year,"observation_unit":"delito_ingresado_en_SAF","data_status":"derived_sum"})
    return output
