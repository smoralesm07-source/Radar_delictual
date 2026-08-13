from __future__ import annotations

import json
from datetime import datetime, timezone

from .aml import annotate_aml
from .collectors import collect_mp_history, load_existing_jsonl
from .config import EVIDENCE_DIR, PROCESSED_DIR, TARGET_END_YEAR, TARGET_START_YEAR
from .dashboard import build_dashboard
from .monitor import collect_osint_events
from .normalize import add_national_rollups
from .risk import build_region_risk
from .sources import load_sources, probe_sources


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


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
    else:
        records, evidence, mp_status = collect_mp_history(TARGET_START_YEAR, TARGET_END_YEAR)
        events, event_status = collect_osint_events()
        source_cfg = load_sources()["sources"]
        probes = probe_sources([s for s in source_cfg if s["priority"] == 1])
        source_status = mp_status + event_status + probes
        if not records and metric_path.exists():
            records = load_existing_jsonl(metric_path)
            source_status.append({"source_id":"fallback","ok":True,"note":"Se conserva último dato bueno por falla de extracción."})
    records = annotate_aml(add_national_rollups([r for r in records if r.get("territory_level") != "national"])) if records else []
    risks = build_region_risk(records)
    _write_jsonl(metric_path, records)
    _write_jsonl(evidence_path, evidence)
    _write_jsonl(PROCESSED_DIR / "osint_events.jsonl", events)
    (PROCESSED_DIR / "risk_signals.json").write_text(json.dumps(risks, ensure_ascii=False, indent=2), encoding="utf-8")
    status_doc = {"generated_at":datetime.now(timezone.utc).isoformat(),"offline":offline,"target_period":[TARGET_START_YEAR,TARGET_END_YEAR],"sources":source_status}
    status_path.write_text(json.dumps(status_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    build_dashboard(records, risks, source_status, events=events)
    return {"metrics":len(records),"risk_signals":len(risks),"osint_events":len(events),"evidence":len(evidence),"latest_year":max([r["year"] for r in records], default=None)}
