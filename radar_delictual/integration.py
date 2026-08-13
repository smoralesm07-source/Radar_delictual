from __future__ import annotations
import json
from .config import CONFIG_DIR


def _sources(*values:str|None, fallback:str="cead_estadisticas_delictuales") -> list[str]:
    out=[]
    for value in values:
        if value and value not in out: out.append(value)
    return out or [fallback]


def build_integration_contract(region_priority:list[dict], commune_rows:list[dict]) -> list[dict]:
    """Contrato estable para Radar SII/UAF.

    En v0.4 la capa comunal prioritaria es longitudinal: conserva el conteo anual de
    casos policiales asociados a delitos base y su procedencia, en vez de forzar un
    score territorial. Se mantiene compatibilidad con las señales v0.3 en pruebas y
    snapshots antiguos.
    """
    rows=[]
    for r in region_priority:
        rows.append({"territory_id":f"CL-{r['region_code']}","geography_level":"region","period":str(r["year"]),"signal_family":"ministerio_publico_aml_proxy","score":r["pressure_score"],"value":None,"metric":"score_proxy","score_version":"0.4","aml_relevance":"analytical_proxy","join_keys":{"region_code":r["region_code"],"commune_code":None,"commune_name_norm":None},"source_families":["ministerio_publico_saf"],"excludes_homicide_weight":True})
    for r in commune_rows:
        source_families=_sources(r.get("source_id"),r.get("ultimate_source_id"))
        # v0.4 predicate feature
        if "value" in r and r.get("signal_family")=="cead_predicate_offense":
            rows.append({"territory_id":r["territory_id"],"geography_level":"commune","period":str(r["period"]),"signal_family":"cead_predicate_offense","score":None,"value":r.get("value"),"metric":r.get("metric","casos_policiales"),"score_version":"0.4","aml_relevance":r.get("aml_class","predicate_direct"),"crime_category":r.get("crime_category"),"article27_mapping_key":r.get("article27_mapping_key"),"aml_weight":r.get("aml_weight"),"mapping_confidence":r.get("mapping_confidence"),"join_keys":{"region_code":r.get("region_code"),"commune_code":r.get("commune_code"),"commune_name_norm":None},"source_families":source_families,"source_tier":r.get("source_tier"),"quality_status":r.get("quality_status"),"excludes_homicide_weight":True})
        # compatibilidad v0.3
        elif "cead_aml_priority_score" in r:
            rows.append({"territory_id":r["territory_id"],"geography_level":"commune","period":r["period"],"signal_family":"cead_art27_drug_family","score":r["cead_aml_priority_score"],"value":None,"metric":"score_proxy","score_version":"0.3-compat","aml_relevance":"direct_predicate_family","article27_relation":r.get("article27_relation"),"join_keys":{"region_code":r.get("region_code"),"commune_code":r.get("commune_code"),"commune_name_norm":r.get("commune_name_norm")},"source_families":source_families,"excludes_homicide_weight":True})
    return rows


def load_sector_hypotheses() -> dict:
    return json.loads((CONFIG_DIR/"sector_signal_hypotheses.json").read_text(encoding="utf-8"))
