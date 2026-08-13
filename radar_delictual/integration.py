from __future__ import annotations
import json
from .config import CONFIG_DIR


def build_integration_contract(region_priority:list[dict], commune_priority:list[dict]) -> list[dict]:
    rows=[]
    for r in region_priority:
        rows.append({"territory_id":f"CL-{r['region_code']}","geography_level":"region","period":str(r["year"]),"signal_family":"ministerio_publico_aml_proxy","score":r["pressure_score"],"score_version":"0.3","aml_relevance":"analytical_proxy","join_keys":{"region_code":r["region_code"],"commune_code":None,"commune_name_norm":None},"source_families":["ministerio_publico_saf"],"excludes_homicide_weight":True})
    for r in commune_priority:
        rows.append({"territory_id":r["territory_id"],"geography_level":"commune","period":r["period"],"signal_family":"cead_art27_drug_family","score":r["cead_aml_priority_score"],"score_version":"0.3","aml_relevance":"direct_predicate_family","article27_relation":r["article27_relation"],"join_keys":{"region_code":r["region_code"],"commune_code":r.get("commune_code"),"commune_name_norm":r.get("commune_name_norm")},"source_families":["bcn_siit","cead_estadisticas_delictuales"],"excludes_homicide_weight":True})
    return rows


def load_sector_hypotheses() -> dict:
    return json.loads((CONFIG_DIR/"sector_signal_hypotheses.json").read_text(encoding="utf-8"))
