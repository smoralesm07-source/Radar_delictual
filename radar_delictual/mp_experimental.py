from __future__ import annotations

import json
from pathlib import Path

from .config import CONFIG_DIR


def load_mp_pilot_config() -> dict:
    return json.loads((CONFIG_DIR / "mp_aml_pilot_v1.json").read_text(encoding="utf-8"))


def assess_mp_extract(rows: list[dict], config: dict | None = None) -> dict:
    """Evalua un extracto agregado del Ministerio Publico sin incorporarlo al IGR.

    El objetivo es distinguir entre un extracto util solo para analisis regional y
    uno apto para un piloto comunal. Nunca infiere comuna a partir de fiscalia.
    """
    config = config or load_mp_pilot_config()
    if not rows:
        return {
            "status": "empty",
            "communal_ready": False,
            "regional_ready": False,
            "igr_eligible": False,
            "reason": "no_rows",
        }

    minimum = set(config["minimum_fields"])
    available = set().union(*(set(row) for row in rows))
    missing_minimum = sorted(minimum - available)
    if missing_minimum:
        return {
            "status": "invalid_schema",
            "communal_ready": False,
            "regional_ready": False,
            "igr_eligible": False,
            "missing_fields": missing_minimum,
        }

    years = sorted({int(row["year"]) for row in rows if row.get("year") not in {None, ""}})
    year_span = (years[-1] - years[0] + 1) if years else 0
    commune_fields = set(config["communal_fields"])
    has_commune_fields = commune_fields.issubset(available)
    commune_rows = [
        row for row in rows
        if row.get("occurrence_commune_code") not in {None, ""}
        and row.get("occurrence_commune_name") not in {None, ""}
    ]
    communal_coverage = len(commune_rows) / len(rows) if rows else 0.0

    regional_field_present = any(
        field in available for field in config["territorial_rule"]["regional_only"]
    )
    min_years = int(config["promotion_rules"].get("min_years", 4))

    communal_ready = bool(
        has_commune_fields
        and communal_coverage >= 0.95
        and year_span >= min_years
    )
    regional_ready = bool(regional_field_present and year_span >= min_years)

    return {
        "status": "communal_candidate" if communal_ready else "regional_only" if regional_ready else "insufficient",
        "communal_ready": communal_ready,
        "regional_ready": regional_ready,
        "igr_eligible": False,
        "rows": len(rows),
        "years": years,
        "year_span": year_span,
        "communal_coverage": round(communal_coverage, 4),
        "note": "Aun un extracto comunal satisfactorio permanece fuera de IGR hasta backtest y aprobacion metodologica.",
    }


def normalize_mp_aggregate(rows: list[dict]) -> list[dict]:
    """Normaliza un extracto ya agregado; no geocodifica ni asigna comunas."""
    out = []
    for row in rows:
        year = row.get("year")
        count = row.get("offense_count")
        if year in {None, ""} or count in {None, ""}:
            continue
        normalized = {
            "year": int(year),
            "offense_code": str(row.get("offense_code") or "").strip(),
            "offense_name": str(row.get("offense_name") or "").strip(),
            "offense_count": int(float(count)),
            "occurrence_commune_code": str(row.get("occurrence_commune_code") or "").strip() or None,
            "occurrence_commune_name": str(row.get("occurrence_commune_name") or "").strip() or None,
            "fiscal_region": str(row.get("fiscal_region") or "").strip() or None,
            "local_prosecution_office": str(row.get("local_prosecution_office") or "").strip() or None,
            "known_offender_status": str(row.get("known_offender_status") or "").strip() or None,
            "source_id": "ministerio_publico_saf_experimental",
            "quality_status": "research_only",
        }
        out.append(normalized)
    return out
