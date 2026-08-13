from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone

from .aml import annotate_aml
from .cead_bridge import collect_cead_bridge
from .cead_communal import collect_cead_communal
from .cead_direct import annualize_direct, collect_direct_year, probe_cead_direct
from .cead_master import build_manifest, build_predicate_features, load_catalog_v4, merge_annual_sources, merge_direct_cache
from .collectors import collect_mp_history, load_existing_jsonl
from .config import EVIDENCE_DIR, PROCESSED_DIR, TARGET_END_YEAR, TARGET_START_YEAR
from .dashboard import build_dashboard
from .integration import build_integration_contract
from .legal import collect_legal_evidence, legal_summary
from .monitor import collect_osint_events
from .normalize import add_national_rollups
from .official_discovery import discover_official_publications
from .risk import build_region_risk
from .risk_v3 import build_cead_commune_aml_priority, build_region_mp_priority
from .risk_v4 import build_current_predicate_activity
from .sources import load_sources, probe_sources


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def _write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception: return default


def _norm(value:str)->str:
    value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


def _attach_bridge_codes(records:list[dict], communes:list[dict])->tuple[list[dict],dict]:
    by_name={(_norm(c.get("commune_name")),str(c.get("region_code") or "").zfill(2)):c for c in communes}
    matched=set()
    for r in records:
        if r.get("territory_level")!="commune": continue
        key=(_norm(r.get("commune_name")),str(r.get("region_code") or "").zfill(2)); c=by_name.get(key)
        if not c: continue
        code=str(c.get("commune_code") or "").zfill(5)
        if len(code)==5 and code.isdigit():
            r["commune_code"]=code; r["territory_id"]=f"CL-{code}"; r["territory_key_status"]="bridge_cut"
            matched.add(code)
    return records,{"source_id":"cead_bridge_cut_join","ok":len(matched)>=340,"matched_communes":len(matched),"note":"CUT comunal reutilizado desde la serie CEAD puente; evita depender de disponibilidad puntual de SUBDERE."}


def _load_master_fallback()->list[dict]:
    return load_existing_jsonl(PROCESSED_DIR/"cead_annual_master_v4.jsonl")


def run(offline: bool=False)->dict:
    metric_path=PROCESSED_DIR/"territorial_metrics.jsonl"; evidence_path=EVIDENCE_DIR/"source_evidence.jsonl"; status_path=PROCESSED_DIR/"source_status.json"
    master_path=PROCESSED_DIR/"cead_annual_master_v4.jsonl"; direct_cache_path=PROCESSED_DIR/"cead_direct_annual_cache.jsonl"; manifest_path=PROCESSED_DIR/"cead_update_manifest.json"
    old_manifest=_read_json(manifest_path,{})

    if offline:
        records=load_existing_jsonl(metric_path); evidence=load_existing_jsonl(evidence_path); source_status=_read_json(status_path,{}).get("sources",[])
        mp_metrics=[r for r in records if r.get("metric")=="delitos_ingresados"]
        secondary_cead=load_existing_jsonl(PROCESSED_DIR/"cead_official_secondary_control.jsonl")
        master=load_existing_jsonl(master_path); direct_cache=load_existing_jsonl(direct_cache_path)
        manifest=_read_json(manifest_path,{}); probe=manifest.get("primary_probe",{}); bridge_meta=manifest.get("bridge_snapshot",{})
        events=load_existing_jsonl(PROCESSED_DIR/"osint_events.jsonl"); publications=load_existing_jsonl(PROCESSED_DIR/"official_publications.jsonl")
    else:
        # 1) Fiscalía: capa persecutoria regional comparable.
        mp_raw,mp_evidence,mp_status=collect_mp_history(TARGET_START_YEAR,TARGET_END_YEAR)
        mp_metrics=annotate_aml(add_national_rollups(mp_raw)) if mp_raw else []
        if not mp_metrics and metric_path.exists():
            old=load_existing_jsonl(metric_path); mp_metrics=[r for r in old if r.get("metric")=="delitos_ingresados"]
            mp_status.append({"source_id":"fallback_mp","ok":bool(mp_metrics),"note":"Se conserva último dato bueno de Fiscalía."})

        # 2) Puente CEAD: snapshot procesado de una extracción directa documentada.
        bridge_records=[]; bridge_evidence=[]; bridge_communes=[]
        try:
            bridge_records,bridge_evidence,bridge_meta,bridge_communes=collect_cead_bridge(TARGET_START_YEAR)
            bridge_status={"source_id":"cead_community_bridge","ok":True,"communes":bridge_meta.get("communes"),"offenses":bridge_meta.get("offenses"),"min_date":bridge_meta.get("min_date"),"max_date":bridge_meta.get("max_date"),"upstream_blob_sha":bridge_meta.get("upstream_blob_sha"),"content_sha256":bridge_meta.get("content_sha256"),"source_tier":"mirror_of_primary","note":"Réplica pública con proceso de extracción directa CEAD documentado; no se presenta como fuente oficial."}
        except Exception as exc:
            bridge_meta={"source_id":"cead_community_bridge","ok":False,"error":f"{type(exc).__name__}: {exc}"}; bridge_status=bridge_meta
            fallback=_load_master_fallback(); bridge_records=[r for r in fallback if r.get("source_tier")!="primary_direct"]
            bridge_communes=list({r.get("commune_code"):{"commune_code":r.get("commune_code"),"commune_name":r.get("commune_name"),"region_code":r.get("region_code"),"region_name":r.get("region_name")} for r in bridge_records if r.get("commune_code")}.values())

        # 3) Sonda del endpoint CEAD primario. Si el año actual aún no tiene datos, se prueba el año anterior.
        current_year=datetime.now().year
        probe=probe_cead_direct(current_year,"01101")
        if probe.get("ok") and not probe.get("latest_nonzero_period"):
            prior_probe=probe_cead_direct(current_year-1,"01101")
            if prior_probe.get("latest_nonzero_period"): probe=prior_probe

        direct_cache=load_existing_jsonl(direct_cache_path)
        direct_refresh_status={"source_id":"cead_direct_incremental","ok":bool(direct_cache),"executed":False,"records_cached":len(direct_cache)}
        latest_primary=probe.get("latest_nonzero_period") if probe.get("ok") else None
        last_primary=old_manifest.get("last_primary_period")
        if latest_primary and bridge_communes and (not direct_cache or latest_primary!=last_primary):
            refresh_year=int(str(latest_primary)[:4]); monthly,direct_status=collect_direct_year(refresh_year,bridge_communes)
            annual=annualize_direct(monthly); covered={r.get("commune_code") for r in annual if r.get("commune_code")}
            if len(covered)>=340:
                direct_cache=merge_direct_cache(direct_cache,annual)
                direct_refresh_status={"source_id":"cead_direct_incremental","ok":True,"executed":True,"year":refresh_year,"communes":len(covered),"annual_records":len(annual),"note":"Actualización primaria aceptada solo con cobertura nacional suficiente."}
            else:
                direct_refresh_status={"source_id":"cead_direct_incremental","ok":False,"executed":True,"year":refresh_year,"communes":len(covered),"annual_records":len(annual),"note":"Lote directo incompleto: no se incorpora al maestro; permanece la última versión buena."}

        master=merge_annual_sources(direct_cache,bridge_records)
        if not master:
            master=_load_master_fallback()

        # 4) BCN/SIIT: control oficial secundario, nunca sustituye silenciosamente a CEAD primario.
        secondary_cead=[]; secondary_evidence=[]; secondary_status=[]; topic_rows=[]
        try:
            secondary_cead,secondary_evidence,secondary_status,topic_rows=collect_cead_communal()
            secondary_cead,bridge_cut_status=_attach_bridge_codes(secondary_cead,bridge_communes)
        except Exception as exc:
            secondary_cead=load_existing_jsonl(PROCESSED_DIR/"cead_official_secondary_control.jsonl")
            secondary_status=[{"source_id":"bcn_siit_cead_communal","ok":bool(secondary_cead),"error":f"{type(exc).__name__}: {exc}","note":"Se conserva último control oficial secundario."}]
            bridge_cut_status={"source_id":"cead_bridge_cut_join","ok":False,"matched_communes":0}

        # 5) Evidencia jurídica y OSINT. Homicidios se retiran de la corrida AML v0.4.
        legal_evidence,legal_status=collect_legal_evidence(); events,event_status=collect_osint_events(); publications,discovery_status=discover_official_publications()
        source_cfg=load_sources()["sources"]; probes=probe_sources([s for s in source_cfg if s["priority"]==1 and s.get("source_id") not in {"cead_estadisticas_delictuales"}])
        source_status=mp_status+[probe,direct_refresh_status,bridge_status]+secondary_status+[bridge_cut_status]+legal_status+event_status+[discovery_status]+probes
        evidence=mp_evidence+bridge_evidence+secondary_evidence+legal_evidence
        records=mp_metrics+secondary_cead

    mp_risk_all=build_region_risk(mp_metrics); region_priority=build_region_mp_priority(mp_risk_all)
    secondary_rate_priority=build_cead_commune_aml_priority(secondary_cead)
    current_activity=build_current_predicate_activity(master)
    predicate_features=build_predicate_features(master)
    legal=legal_summary(); cead_catalog=load_catalog_v4()
    integration=build_integration_contract(region_priority,predicate_features)
    homicide_context={"enabled":False,"aml_weight":0.0,"score_eligible":False,"records_in_v04_core":0,"note":"Homicidios retirados de la adquisición y scoring AML v0.4; no son usados como proxy LA/FT."}
    bcn_control_count=len([r for r in secondary_cead if r.get("quality_status")=="usable"])
    manifest=build_manifest(probe,bridge_meta,master,direct_cache,bcn_control_count)

    _write_jsonl(metric_path,records); _write_jsonl(evidence_path,evidence)
    _write_jsonl(master_path,master); _write_jsonl(direct_cache_path,direct_cache)
    _write_jsonl(PROCESSED_DIR/"cead_predicate_features_v4.jsonl",predicate_features)
    _write_jsonl(PROCESSED_DIR/"cead_official_secondary_control.jsonl",secondary_cead)
    _write_jsonl(PROCESSED_DIR/"osint_events.jsonl",events); _write_jsonl(PROCESSED_DIR/"official_publications.jsonl",publications)
    _write_json(PROCESSED_DIR/"cead_direct_probe.json",probe); _write_json(manifest_path,manifest)
    _write_json(PROCESSED_DIR/"cead_current_predicate_activity_v4.json",current_activity)
    _write_json(PROCESSED_DIR/"cead_secondary_rate_priority_v3.json",secondary_rate_priority)
    _write_json(PROCESSED_DIR/"region_aml_proxy_v4.json",region_priority); _write_json(PROCESSED_DIR/"risk_signals.json",mp_risk_all)
    _write_json(PROCESSED_DIR/"cead_catalog_art27_v4.json",cead_catalog); _write_json(PROCESSED_DIR/"legal_mapping_summary.json",legal)
    _write_json(PROCESSED_DIR/"homicide_context.json",homicide_context); _write_json(PROCESSED_DIR/"integration_ready.json",integration)

    coverage={
        "mp_region_years":sorted({r["year"] for r in mp_metrics if r.get("territory_level")=="region"}),
        "cead_master_years":sorted({int(r["year"]) for r in master}),
        "cead_master_communes":len({r.get("commune_code") for r in master if r.get("commune_code")}),
        "cead_master_offenses":len({r.get("crime_category_norm",_norm(r.get("crime_category",""))) for r in master}),
        "cead_predicate_features":len(predicate_features),"cead_current_activity_communes":len(current_activity),
        "cead_primary_direct_available":bool(probe.get("ok")),"cead_active_backbone":manifest.get("active_backbone"),
        "cead_bridge_max_date":bridge_meta.get("max_date"),"homicides_in_aml_core":0
    }
    status_doc={"generated_at":datetime.now(timezone.utc).isoformat(),"offline":offline,"target_period":[TARGET_START_YEAR,TARGET_END_YEAR],"version":"0.4.0","sources":source_status,"coverage":coverage}
    _write_json(status_path,status_doc)
    build_dashboard(records,mp_risk_all,source_status,events=events,region_priority=region_priority,commune_priority=secondary_rate_priority,legal=legal,cead_catalog=cead_catalog,publications=publications,integration=integration,homicide_context=homicide_context,cead_metrics=secondary_cead,cead_manifest=manifest,current_activity=current_activity,predicate_features=predicate_features)
    return {"version":"0.4.0","mp_metrics":len(mp_metrics),"cead_master_records":len(master),"cead_master_communes":coverage["cead_master_communes"],"cead_master_years":coverage["cead_master_years"],"cead_master_offenses":coverage["cead_master_offenses"],"cead_predicate_features":len(predicate_features),"cead_current_activity_communes":len(current_activity),"cead_primary_direct_available":coverage["cead_primary_direct_available"],"cead_active_backbone":coverage["cead_active_backbone"],"cead_bridge_max_date":coverage["cead_bridge_max_date"],"integration_records":len(integration),"homicides_in_aml_core":0,"evidence":len(evidence)}
