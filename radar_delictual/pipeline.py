from __future__ import annotations

import json
from datetime import datetime, timezone

from .aml import annotate_aml
from .cead_communal import collect_cead_communal, load_catalog as load_cead_catalog
from .collectors import collect_mp_history, load_existing_jsonl
from .config import EVIDENCE_DIR, PROCESSED_DIR, TARGET_END_YEAR, TARGET_START_YEAR
from .dashboard import build_dashboard
from .homicides import collect_homicide_official
from .integration import build_integration_contract
from .legal import collect_legal_evidence, legal_summary
from .monitor import collect_osint_events
from .normalize import add_national_rollups
from .official_discovery import discover_official_publications
from .risk import build_region_risk
from .risk_v3 import build_cead_commune_aml_priority, build_region_mp_priority
from .sources import load_sources, probe_sources
from .territory import attach_cut_codes


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def _write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run(offline: bool = False) -> dict:
    metric_path=PROCESSED_DIR/"territorial_metrics.jsonl"; evidence_path=EVIDENCE_DIR/"source_evidence.jsonl"; status_path=PROCESSED_DIR/"source_status.json"
    if offline:
        records=load_existing_jsonl(metric_path); evidence=load_existing_jsonl(evidence_path)
        status_doc=json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}; source_status=status_doc.get("sources",[])
        events=load_existing_jsonl(PROCESSED_DIR/"osint_events.jsonl"); publications=load_existing_jsonl(PROCESSED_DIR/"official_publications.jsonl"); topic_rows=load_existing_jsonl(PROCESSED_DIR/"cead_topic_availability.jsonl")
        mp_metrics=[r for r in records if r.get("metric")=="delitos_ingresados"]
        cead_metrics=[r for r in records if r.get("source_id")=="bcn_siit_cead_communal"]
        homicide_metrics=[r for r in records if r.get("metric")=="victimas_homicidio_consumado"]
    else:
        mp_raw,mp_evidence,mp_status=collect_mp_history(TARGET_START_YEAR,TARGET_END_YEAR)
        mp_metrics=annotate_aml(add_national_rollups(mp_raw)) if mp_raw else []
        cead_metrics,cead_evidence,cead_status,topic_rows=collect_cead_communal()
        homicide_metrics,homicide_evidence,homicide_status=collect_homicide_official(download_evidence=True)
        legal_evidence,legal_status=collect_legal_evidence(); events,event_status=collect_osint_events(); publications,discovery_status=discover_official_publications()
        source_cfg=load_sources()["sources"]; probes=probe_sources([s for s in source_cfg if s["priority"]==1])
        source_status=mp_status+cead_status+homicide_status+legal_status+event_status+[discovery_status]+probes
        evidence=mp_evidence+cead_evidence+homicide_evidence+legal_evidence
        if not mp_metrics and metric_path.exists():
            old=load_existing_jsonl(metric_path); mp_metrics=[r for r in old if r.get("metric")=="delitos_ingresados"]; source_status.append({"source_id":"fallback_mp","ok":True,"note":"Se conserva último dato bueno de Fiscalía."})
        if not any(r.get("year")==2024 and r.get("cead_family_key")=="delitos_asociados_drogas" for r in cead_metrics) and metric_path.exists():
            old=load_existing_jsonl(metric_path); cead_metrics=[r for r in old if r.get("source_id")=="bcn_siit_cead_communal"]; source_status.append({"source_id":"fallback_cead_communal","ok":bool(cead_metrics),"note":"Se conserva último dato bueno CEAD comunal si la extracción territorial falla."})
        cead_metrics,cut_join_status=attach_cut_codes(cead_metrics)
        source_status.append(cut_join_status)
        records=mp_metrics+cead_metrics+homicide_metrics
    mp_risk_all=build_region_risk(mp_metrics); region_priority=build_region_mp_priority(mp_risk_all); commune_priority=build_cead_commune_aml_priority(cead_metrics)
    legal=legal_summary(); cead_catalog=load_cead_catalog(); integration=build_integration_contract(region_priority,commune_priority)
    homicide_context={"aml_weight":0.0,"score_eligible":False,"note":"Homicidios se conservan como contexto delictual y no aportan a scores AML/LAFT.","records":len(homicide_metrics),"periods":sorted({str(r.get('period',r.get('year'))) for r in homicide_metrics})}
    quarantined=sum(1 for r in cead_metrics if str(r.get("quality_status","")).startswith("quarantined")); annual_drug_communes=len({r["territory_id"] for r in cead_metrics if r.get("year")==2024 and r.get("cead_family_key")=="delitos_asociados_drogas" and r.get("quality_status")=="usable"})
    cut_coded_communes=len({r.get("commune_code") for r in cead_metrics if r.get("year")==2024 and r.get("cead_family_key")=="delitos_asociados_drogas" and r.get("commune_code")})
    _write_jsonl(metric_path,records); _write_jsonl(evidence_path,evidence); _write_jsonl(PROCESSED_DIR/"cead_communal_metrics.jsonl",cead_metrics); _write_jsonl(PROCESSED_DIR/"cead_topic_availability.jsonl",topic_rows)
    _write_jsonl(PROCESSED_DIR/"osint_events.jsonl",events); _write_jsonl(PROCESSED_DIR/"official_publications.jsonl",publications)
    _write_json(PROCESSED_DIR/"risk_signals.json",mp_risk_all); _write_json(PROCESSED_DIR/"region_aml_proxy_v3.json",region_priority); _write_json(PROCESSED_DIR/"cead_aml_commune_priority_v3.json",commune_priority); _write_json(PROCESSED_DIR/"cead_catalog_art27.json",cead_catalog); _write_json(PROCESSED_DIR/"legal_mapping_summary.json",legal); _write_json(PROCESSED_DIR/"homicide_context.json",homicide_context); _write_json(PROCESSED_DIR/"integration_ready.json",integration)
    status_doc={"generated_at":datetime.now(timezone.utc).isoformat(),"offline":offline,"target_period":[TARGET_START_YEAR,TARGET_END_YEAR],"version":"0.3.0","sources":source_status,"coverage":{"mp_region_years":sorted({r["year"] for r in mp_metrics if r.get("territory_level")=="region"}),"cead_annual_2024_drug_communes":annual_drug_communes,"cead_communes_with_cut":cut_coded_communes,"cead_latest_quarantined_records":quarantined,"cead_commune_priority_records":len(commune_priority),"homicide_aml_weight":0.0}}
    _write_json(status_path,status_doc)
    build_dashboard(records,mp_risk_all,source_status,events=events,region_priority=region_priority,commune_priority=commune_priority,legal=legal,cead_catalog=cead_catalog,publications=publications,integration=integration,homicide_context=homicide_context,cead_metrics=cead_metrics)
    return {"version":"0.3.0","metrics":len(records),"cead_communal_metrics":len(cead_metrics),"cead_drug_communes_2024":annual_drug_communes,"cead_communes_with_cut":cut_coded_communes,"cead_commune_priority_signals":len(commune_priority),"cead_quarantined_records":quarantined,"region_mp_proxy_signals":len(region_priority),"integration_records":len(integration),"homicide_aml_weight":0.0,"osint_events":len(events),"evidence":len(evidence),"latest_year":max([r["year"] for r in records],default=None)}
