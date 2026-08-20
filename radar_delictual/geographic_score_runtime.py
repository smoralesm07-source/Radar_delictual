from __future__ import annotations

import json

from .config import PROCESSED_DIR, PUBLIC_DIR
from .geographic_score import _integration_rows, _load_config, _methodology_html, build_cead_geographic_score


def normalize_quality_status(master: list[dict]) -> list[dict]:
    """Normaliza estados QA gobernados solo para el cálculo del score.

    El backbone CEAD usa estados como ``usable_bridge`` para conservar la
    procedencia de la observación. El motor base del score reconoce ``usable``.
    Esta función adapta una copia en memoria y nunca modifica el maestro fuente.
    """
    normalized = []
    for current in master:
        row = dict(current)
        quality = str(row.get("quality_status") or "").lower()
        if quality.startswith("usable_"):
            row["quality_status"] = "usable"
        normalized.append(row)
    return normalized


def materialize_geographic_score() -> dict:
    config = _load_config()
    master_path = PROCESSED_DIR / "cead_annual_master_v4.jsonl"
    if not master_path.exists():
        return {"ok": False, "reason": "cead_annual_master_v4.jsonl no disponible"}

    master = normalize_quality_status([
        json.loads(line)
        for line in master_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ])
    scores = build_cead_geographic_score(master, config)

    score_path = PROCESSED_DIR / "cead_geographic_score_v1.json"
    score_path.write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    (PROCESSED_DIR / "cead_geographic_score_methodology_v1.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    integration_path = PROCESSED_DIR / "integration_ready.json"
    integration = json.loads(integration_path.read_text(encoding="utf-8")) if integration_path.exists() else []
    integration = [
        row for row in integration
        if row.get("signal_family") != "cead_criminogenic_geographic_score"
    ] + _integration_rows(scores)
    integration_path.write_text(json.dumps(integration, ensure_ascii=False, indent=2), encoding="utf-8")

    data_path = PUBLIC_DIR / "data.json"
    if data_path.exists():
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        payload["cead_geographic_score"] = scores
        payload["cead_geographic_score_methodology"] = config
        payload["integration"] = integration
        data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    index_path = PUBLIC_DIR / "index.html"
    if index_path.exists():
        html = index_path.read_text(encoding="utf-8")
        marker = '<section class="panel" style="margin-top:14px"><h2>Salud y trazabilidad de fuentes</h2>'
        block = _methodology_html(config, scores)
        if 'id="cead-geographic-score"' not in html and marker in html:
            html = html.replace(marker, block + marker, 1)
            index_path.write_text(html, encoding="utf-8")

    scored_records = sum(row.get("score") is not None for row in scores)
    return {
        "ok": True,
        "score_version": config["version"],
        "records": len(scores),
        "scored_records": scored_records,
        "output": str(score_path),
    }
