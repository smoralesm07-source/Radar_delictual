from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import requests

from .config import PROCESSED_DIR, PUBLIC_DIR
from .geographic_score import _integration_rows
from .geographic_score_runtime import normalize_quality_status
from .geographic_score_v11 import (
    build_cead_geographic_score_v11_candidate,
    compare_v1_candidate,
    load_candidate_config,
)


POPULATION_CACHE = PROCESSED_DIR / "censo2024_population_commune.json"


def _read_population_cache(path: Path = POPULATION_CACHE) -> tuple[dict[str, float], dict]:
    if not path.exists():
        return {}, {"available": False, "source": "cache_missing"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", payload if isinstance(payload, list) else [])
    population = {
        str(row.get("commune_code") or "").zfill(5): float(row.get("population") or 0)
        for row in rows
        if row.get("commune_code") and float(row.get("population") or 0) > 0
    }
    return population, {
        "available": len(population) >= 340,
        "source": "cache",
        "communes": len(population),
        "metadata": payload.get("metadata", {}) if isinstance(payload, dict) else {},
    }


def load_census_population_2024(offline: bool = False) -> tuple[dict[str, float], dict]:
    cached, cached_meta = _read_population_cache()
    if cached_meta.get("available"):
        return cached, cached_meta
    if offline:
        return cached, {**cached_meta, "offline": True}

    config = load_candidate_config()
    url = config["population"]["bridge_url"]
    try:
        response = requests.get(url, headers={"User-Agent": "Radar-Delictual-IGR-Candidate/1.1"}, timeout=45)
        response.raise_for_status()
        reader = csv.DictReader(io.StringIO(response.text), delimiter=";")
        population: dict[str, float] = {}
        names: dict[str, str] = {}
        for row in reader:
            if str(row.get("nivel") or "").strip().lower() != "comuna":
                continue
            if str(row.get("sexo") or "").strip().lower() != "total":
                continue
            if str(row.get("edad") or "").strip().lower() != "total":
                continue
            code = str(row.get("codigo_comuna") or "").strip().zfill(5)
            try:
                value = float(row.get("poblacion") or 0)
            except (TypeError, ValueError):
                continue
            if len(code) == 5 and code.isdigit() and value > 0:
                population[code] = value
                names[code] = str(row.get("comuna") or "")

        if len(population) < 340:
            raise ValueError(f"Censo 2024 comunal incompleto: {len(population)} comunas")

        payload = {
            "metadata": {
                "reference_year": config["population"]["reference_year"],
                "metric": config["population"]["metric"],
                "bridge_url": url,
                "ultimate_source": config["population"]["ultimate_source"],
                "bridge_note": config["population"]["bridge_note"],
            },
            "rows": [
                {"commune_code": code, "commune_name": names.get(code), "population": int(value)}
                for code, value in sorted(population.items())
            ],
        }
        POPULATION_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return population, {"available": True, "source": "bridge_refresh", "communes": len(population), "metadata": payload["metadata"]}
    except Exception as exc:
        return cached, {**cached_meta, "available": bool(cached), "source": "cache_fallback" if cached else "unavailable", "error": f"{type(exc).__name__}: {exc}"}


def materialize_geographic_score_v11_candidate(offline: bool = False) -> dict:
    candidate = load_candidate_config()
    master_path = PROCESSED_DIR / "cead_annual_master_v4.jsonl"
    if not master_path.exists():
        return {"ok": False, "reason": "cead_annual_master_v4.jsonl no disponible"}

    master = normalize_quality_status([
        json.loads(line)
        for line in master_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ])
    population, population_meta = load_census_population_2024(offline=offline)
    rows = build_cead_geographic_score_v11_candidate(master, population, candidate)

    # El motor conserva nombres internos de la etapa candidate por trazabilidad,
    # pero una corrida con contrato productivo no debe publicar metadatos experimentales.
    if candidate.get("status") == "production":
        for row in rows:
            row["signal_family"] = "cead_criminogenic_geographic_score"
            row["level_status"] = "secondary_context"
            row["provisional_level_status"] = "secondary_context"

    score_path = PROCESSED_DIR / "cead_geographic_score_v11_candidate.json"
    methodology_path = PROCESSED_DIR / "cead_geographic_score_methodology_v11_candidate.json"
    production_score_path = PROCESSED_DIR / "cead_geographic_score.json"
    production_methodology_path = PROCESSED_DIR / "cead_geographic_score_methodology.json"
    comparison_path = PROCESSED_DIR / "cead_geographic_score_v11_comparison.json"
    serialized_rows = json.dumps(rows, ensure_ascii=False, indent=2)
    serialized_methodology = json.dumps(candidate, ensure_ascii=False, indent=2)
    score_path.write_text(serialized_rows, encoding="utf-8")
    methodology_path.write_text(serialized_methodology, encoding="utf-8")
    production_score_path.write_text(serialized_rows, encoding="utf-8")
    production_methodology_path.write_text(serialized_methodology, encoding="utf-8")

    v1_path = PROCESSED_DIR / "cead_geographic_score_v1.json"
    v1_rows = json.loads(v1_path.read_text(encoding="utf-8")) if v1_path.exists() else []
    comparison = compare_v1_candidate(v1_rows, rows, population)
    comparison.update({
        "candidate_version": candidate["version"],
        "base_score_version": candidate["base_score_version"],
        "population_source": population_meta,
        "production_replaced": True,
    })
    comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")

    # La versión promovida reemplaza el artefacto histórico de producción al final
    # de la corrida. Se conserva el archivo candidate como evidencia de transición.
    legacy_score_path = PROCESSED_DIR / "cead_geographic_score_v1.json"
    legacy_methodology_path = PROCESSED_DIR / "cead_geographic_score_methodology_v1.json"
    legacy_score_path.write_text(serialized_rows, encoding="utf-8")
    legacy_methodology_path.write_text(serialized_methodology, encoding="utf-8")

    integration_path = PROCESSED_DIR / "integration_ready.json"
    integration = json.loads(integration_path.read_text(encoding="utf-8")) if integration_path.exists() else []
    integration = [
        row for row in integration
        if row.get("signal_family") != "cead_criminogenic_geographic_score"
    ] + _integration_rows(rows)
    integration_path.write_text(json.dumps(integration, ensure_ascii=False, indent=2), encoding="utf-8")

    data_path = PUBLIC_DIR / "data.json"
    if data_path.exists():
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        payload["cead_geographic_score"] = rows
        payload["cead_geographic_score_methodology"] = candidate
        payload["cead_geographic_score_candidate"] = rows
        payload["cead_geographic_score_candidate_methodology"] = candidate
        payload["cead_geographic_score_candidate_comparison"] = comparison
        payload["integration"] = integration
        data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    confidences = [float(row["confidence"]) for row in rows if row.get("confidence") is not None]
    return {
        "ok": True,
        "experimental": False,
        "production_replaced": True,
        "score_version": candidate["version"],
        "records": len(rows),
        "population_communes": len(population),
        "confidence_min": min(confidences) if confidences else None,
        "confidence_max": max(confidences) if confidences else None,
        "comparison": comparison,
        "output": str(production_score_path),
    }
