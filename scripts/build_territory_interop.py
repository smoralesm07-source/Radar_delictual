from __future__ import annotations

import hashlib
import json
from pathlib import Path

from radar_delictual.territory import canonical_commune_code, commune_territory_id

SOURCE = Path("data/processed/cead_annual_master_v4.jsonl")
OUTPUT = Path("data/processed/territory_interop_v1.jsonl")
STATUS = Path("data/processed/territory_interop_status_v1.json")
MANIFEST = Path("data/processed/cead_update_manifest.json")
EVENTS = Path("data/processed/territory_events_fusion_v1.jsonl")
EVIDENCE = Path("data/processed/evidence_fusion_v1.jsonl")
FUSION_STATUS = Path("data/processed/fusion_interop_status_v1.json")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def adapt(row: dict) -> dict:
    out = dict(row)
    code = canonical_commune_code(out.get("commune_code"))
    if code:
        out["commune_code"] = code
        out["territory_id"] = commune_territory_id(code)
        out["territory_mapping_method"] = "CODE_EXACT"
        out["territory_mapping_confidence"] = 1.0
    else:
        out["territory_id"] = None
        out["territory_mapping_method"] = "UNRESOLVED"
        out["territory_mapping_confidence"] = 0.0
    out["interop_version"] = "1.0"
    out["radar_id"] = "RADAR_DELICTUAL"
    return out


def source_evidence() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    bridge = manifest.get("bridge_snapshot", {}) or {}
    producer = bridge.get("producer_manifest", {}) or {}
    source = producer.get("bridge_snapshot", {}) or {}
    source_id = source.get("source_id") or bridge.get("source_id") or "cead_governed_snapshot"
    retrieved_at = source.get("retrieved_at") or manifest.get("generated_at")
    content_hash = source.get("content_sha256")
    source_url = source.get("download_url")
    if not retrieved_at:
        raise RuntimeError("CEAD lineage timestamp missing; refusing lineage-free export")
    seed = f"{source_id}|{content_hash or ''}|{retrieved_at}"
    evidence_id = "EVD-DELICTUAL-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return {
        "evidence_id": evidence_id,
        "producer_id": "RADAR_DELICTUAL",
        "source_id": source_id,
        "ultimate_source_id": source.get("ultimate_source_id") or "cead_estadisticas_delictuales",
        "source_url": source_url,
        "source_tier": source.get("source_tier") or "GOVERNED_PUBLIC",
        "capture_method": "RADAR_DELICTUAL_GOVERNED_TERRITORIAL_PIPELINE",
        "source_run_id": manifest.get("generated_at"),
        "content_sha256": content_hash,
        "quality_status": "STALE" if (producer.get("freshness", {}) or {}).get("status") == "stale" else "VALID",
        "source_published_at": None,
        "retrieved_at": retrieved_at,
        "ingested_at": manifest.get("generated_at") or retrieved_at,
        "schema_version": "1.0",
    }


def canonical_event(row: dict, evidence: dict) -> dict | None:
    territory_id = row.get("territory_id")
    year = row.get("year") or row.get("commercial_year")
    category = row.get("crime_category") or row.get("category") or row.get("offense")
    if not territory_id or year in (None, "") or not category:
        return None
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    seed = f"{territory_id}|{y}|{category}|{row.get('source_id') or ''}"
    event_id = "EVT-DELICTUAL-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    attributes = {k: v for k, v in row.items() if k not in {"interop_version", "radar_id", "territory_id"}}
    freshness_state = "STALE" if evidence.get("quality_status") == "STALE" else "CURRENT"
    return {
        "event_id": event_id,
        "event_type": "TERRITORIAL_CRIME_STATISTIC",
        "producer_id": "RADAR_DELICTUAL",
        "entity_ids": [],
        "territory_ids": [territory_id],
        "sector_ids": [],
        "evidence_ids": [evidence["evidence_id"]],
        "temporal": {
            "valid_from": f"{y:04d}-01-01T00:00:00+00:00",
            "valid_to": f"{y + 1:04d}-01-01T00:00:00+00:00",
            "source_published_at": evidence.get("source_published_at"),
            "observed_at": evidence.get("retrieved_at"),
            "retrieved_at": evidence.get("retrieved_at"),
            "ingested_at": evidence.get("ingested_at"),
            "last_seen_at": evidence.get("retrieved_at"),
            "freshness_state": freshness_state,
        },
        "attributes": attributes,
    }


def main() -> None:
    rows = [adapt(x) for x in read_jsonl(SOURCE)]
    if not rows:
        raise RuntimeError("CEAD annual master empty; missing is not zero")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")

    status = {
        "interop_version": "1.0",
        "radar_id": "RADAR_DELICTUAL",
        "rows": len(rows),
        "resolved": sum(bool(x.get("territory_id")) for x in rows),
        "unresolved": sum(not bool(x.get("territory_id")) for x in rows),
        "territory_id_format": "CL-COM-{CUT}",
    }
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    evidence = source_evidence()
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False) + "\n", encoding="utf-8")
    events = [event for event in (canonical_event(row, evidence) for row in rows) if event]
    EVENTS.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in events), encoding="utf-8")
    fusion_status = {
        "interop_version": "1.0",
        "radar_id": "RADAR_DELICTUAL",
        "status": "FUSION_EXPORT_READY_TERRITORY_CONTEXT",
        "territory_rows": len(rows),
        "events": len(events),
        "evidence": 1,
        "resolved_territories": status["resolved"],
        "unresolved_territories": status["unresolved"],
        "source_failure_is_zero": False,
        "policy": "TERRITORIAL_STATISTICS_ARE_CONTEXT_NOT_ENTITY_ATTRIBUTION",
        "freshness_state": "STALE" if evidence.get("quality_status") == "STALE" else "CURRENT",
    }
    FUSION_STATUS.write_text(json.dumps(fusion_status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(fusion_status, ensure_ascii=False))


if __name__ == "__main__":
    main()
