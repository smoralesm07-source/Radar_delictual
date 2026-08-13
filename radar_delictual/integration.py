from __future__ import annotations
import json
from .config import CONFIG_DIR


def build_integration_contract(region_priority:list[dict], commune_pressure:list[dict]) -> list[dict]:
    rows=[]
    for r in region_priority:
        rows.append({"territory_id":f"CL-{r['region_code']}","geography_level":"region","period":r["period"],"signal_family":"territorial_aml_priority_proxy","score":r["territorial_priority_score"],"score_version":"0.2","aml_relevance":"analytical_proxy","join_keys":{"region_code":r["region_code"],"commune_code":None},"source_families":["ministerio_publico_saf","homicidios_interinstitucional"]})
    for r in commune_pressure:
        rows.append({"territory_id":r["territory_id"],"geography_level":"commune","period":"2024+2025-H1","signal_family":"homicide_pressure","score":r["homicide_pressure_score"],"score_version":"0.2","aml_relevance":"context_only","join_keys":{"region_code":r["region_code"],"commune_code":r.get("commune_code")},"source_families":["homicidios_interinstitucional"]})
    return rows


def load_sector_hypotheses() -> dict:
    return json.loads((CONFIG_DIR/"sector_signal_hypotheses.json").read_text(encoding="utf-8"))
