from __future__ import annotations

import json
from datetime import datetime, timezone

from .aml import annotate_aml
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
from .risk_v2 import build_commune_homicide_pressure, build_region_priority_v2
from .sources import load_sources, probe_sources


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def _write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run(offline: bool = False) -> dict:
    metric_path = PROCESSED_DIR / "territorial_metrics.jsonl"
    evidence_path = EVIDENCE_DIR / "source_evidence.jsonl"
    status_path = PROCESSED_DIR / "source_status.json"
    if offline:
        records = load_existing_jsonl(metric_path)
        evidence = load_existing_jsonl(evidence_path)
        status_doc = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        source_status = status_doc.get("sources", [])
        events = load_existing_jsonl(PROCESSED_DIR / "osint_events.jsonl")
        publications = load_existing_jsonl(PROCESSED_DIR / "official_publications.jsonl")
        mp_metrics = [r for r in records if r.get("metric") == "delitos_ingresados"]
        homicide_metrics = [r for r in records if r.get("metric") == "victimas_homicidio_consumado"]
    else:
        mp_raw, mp_evidence, mp_status = collect_mp_history(TARGET_START_YEAR, TARGET_END_YEAR)
        mp_metrics = annotate_aml(add_national_rollups(mp_raw)) if mp_raw else []
        homicide_metrics, homicide_evidence, homicide_status = collect_homicide_official(download_evidence=True)
        legal_evidence, legal_status = collect_legal_evidence()
        events, event_status = collect_osint_events()
        publications, discovery_status = discover_official_publications()
        source_cfg = load_sources()["sources"]
        probes = probe_sources([s for s in source_cfg if s["priority"] == 1])
        source_status = mp_status + homicide_status + legal_status + event_status + [discovery_status] + probes
        evidence = mp_evidence + homicide_evidence + legal_evidence
        records = mp_metrics + homicide_metrics
        if not mp_metrics and metric_path.exists():
            old = load_existing_jsonl(metric_path); old_mp = [r for r in old if r.get("metric") == "delitos_ingresados"]
            records = old_mp + homicide_metrics; mp_metrics = old_mp
            source_status.append({"source_id":"fallback_mp","ok":True,"note":"Se conserva último dato bueno de Fiscalía por falla de extracción."})
    mp_risk_v1 = build_region_risk(mp_metrics)
    region_priority = build_region_priority_v2(mp_risk_v1, homicide_metrics)
    commune_pressure = build_commune_homicide_pressure(homicide_metrics)
    legal = legal_summary()
    integration = build_integration_contract(region_priority, commune_pressure)
    _write_jsonl(metric_path, records)
    _write_jsonl(evidence_path, evidence)
    _write_jsonl(PROCESSED_DIR / "osint_events.jsonl", events)
    _write_jsonl(PROCESSED_DIR / "official_publications.jsonl", publications)
    _write_json(PROCESSED_DIR / "risk_signals.json", mp_risk_v1)
    _write_json(PROCESSED_DIR / "territorial_priority_v2.json", region_priority)
    _write_json(PROCESSED_DIR / "commune_homicide_pressure.json", commune_pressure)
    _write_json(PROCESSED_DIR / "legal_mapping_summary.json", legal)
    _write_json(PROCESSED_DIR / "integration_ready.json", integration)
    status_doc = {"generated_at":datetime.now(timezone.utc).isoformat(),"offline":offline,"target_period":[TARGET_START_YEAR,TARGET_END_YEAR],"version":"0.2.0","sources":source_status,"coverage":{"mp_region_years":sorted({r["year"] for r in mp_metrics if r.get("territory_level")=="region"}),"homicide_communes_2024":len([r for r in homicide_metrics if r.get("territory_level")=="commune" and r.get("period")=="2024"]),"homicide_recent_period":"2025-H1" if any(r.get("period")=="2025-H1" for r in homicide_metrics) else None}}
    _write_json(status_path, status_doc)
    build_dashboard(records, mp_risk_v1, source_status, events=events, region_priority=region_priority, commune_pressure=commune_pressure, legal=legal, publications=publications, integration=integration)
    return {"version":"0.2.0","metrics":len(records),"mp_risk_signals":len(mp_risk_v1),"region_priority_signals":len(region_priority),"commune_pressure_signals":len(commune_pressure),"integration_records":len(integration),"osint_events":len(events),"official_publications":len(publications),"evidence":len(evidence),"latest_year":max([r["year"] for r in records], default=None)}
