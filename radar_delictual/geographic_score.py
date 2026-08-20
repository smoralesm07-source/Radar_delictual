from __future__ import annotations

import json
import math
import re
import statistics
import unicodedata
from collections import defaultdict
from pathlib import Path

from .config import CONFIG_DIR, PROCESSED_DIR, PUBLIC_DIR


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _load_config() -> dict:
    return json.loads((CONFIG_DIR / "cead_geographic_score_v1.json").read_text(encoding="utf-8"))


def _percentile_rank(values: list[float], value: float) -> float:
    if not values:
        return 50.0
    if len(values) == 1:
        return 50.0
    lower = sum(1 for x in values if x < value)
    equal = sum(1 for x in values if x == value)
    return round(100.0 * (lower + 0.5 * equal) / len(values), 2)


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _trend_score(current: float, history: list[float]) -> float:
    if not history:
        return 50.0
    baseline = statistics.mean(history[-3:])
    if baseline <= 0:
        return 75.0 if current > 0 else 50.0
    delta = (current - baseline) / baseline
    return round(50.0 + 50.0 * math.tanh(delta), 2)


def _anomaly_score(values: list[float], value: float) -> float:
    if len(values) < 3:
        return 50.0
    med = statistics.median(values)
    deviations = [abs(x - med) for x in values]
    mad = statistics.median(deviations)
    if mad == 0:
        return 50.0 if value == med else (75.0 if value > med else 25.0)
    robust_z = 0.6745 * (value - med) / mad
    return round(50.0 + 50.0 * math.tanh(robust_z / 3.0), 2)


def _crime_series(master: list[dict], aliases: list[str]) -> dict[tuple[str, int], float]:
    wanted = {_norm(a) for a in aliases}
    out: dict[tuple[str, int], float] = defaultdict(float)
    for row in master:
        if row.get("quality_status") not in {None, "usable", "validated", "ok"}:
            continue
        if _norm(row.get("crime_category")) not in wanted:
            continue
        commune = str(row.get("commune_code") or "").zfill(5)
        if len(commune) != 5 or not commune.isdigit():
            continue
        out[(commune, int(row["year"]))] += float(row.get("value") or 0)
    return dict(out)


def _component_metrics(series: dict[tuple[str, int], float], commune: str, latest_year: int) -> dict | None:
    years = sorted({year for c, year in series if c == commune and year <= latest_year})
    if not years or latest_year not in years:
        return None
    current = float(series.get((commune, latest_year), 0.0))
    latest_values = [float(v) for (c, y), v in series.items() if y == latest_year]
    intensity = _percentile_rank(latest_values, current)

    observed = 0; high = 0
    for year in years:
        year_values = [float(v) for (c, y), v in series.items() if y == year]
        if not year_values:
            continue
        observed += 1
        threshold = _quantile(year_values, 0.75)
        if float(series.get((commune, year), 0.0)) >= threshold:
            high += 1
    persistence = round(100.0 * high / observed, 2) if observed else 0.0

    history = [float(series[(commune, y)]) for y in years if y < latest_year]
    trend = _trend_score(current, history)
    anomaly = _anomaly_score(latest_values, current)
    fw = {"intensity": 0.40, "persistence": 0.25, "trend": 0.20, "anomaly": 0.15}
    score = round(sum(fw[k] * v for k, v in {"intensity": intensity, "persistence": persistence, "trend": trend, "anomaly": anomaly}.items()), 2)
    return {"score": score, "value": current, "intensity": intensity, "persistence": persistence, "trend": trend, "anomaly": anomaly, "years_observed": observed}


def _build_layer(master: list[dict], communes: list[str], latest_year: int, layer: dict, layer_id: str) -> dict[str, dict]:
    components = layer.get("components", [])
    prepared = []
    for comp in components:
        series = _crime_series(master, comp.get("aliases", []))
        if series:
            prepared.append((comp, series))

    # Capa 1: si no existen subgrupos directos, usar un único agregado como fallback y evitar doble conteo.
    if layer_id == "predicate_direct" and not prepared:
        for alias in layer.get("fallback_aliases", []):
            series = _crime_series(master, [alias])
            if series:
                prepared = [({"id": "drug_family_fallback", "label": alias, "weight": 1.0, "aliases": [alias]}, series)]
                break

    out = {}
    total_config_weight = sum(float(c.get("weight", 0)) for c in components) or 1.0
    for commune in communes:
        details = []
        available_weight = 0.0
        weighted = 0.0
        for comp, series in prepared:
            metrics = _component_metrics(series, commune, latest_year)
            if not metrics:
                continue
            w = float(comp.get("weight", 0))
            available_weight += w
            weighted += w * metrics["score"]
            details.append({"id": comp.get("id"), "label": comp.get("label"), "configured_weight": w, **metrics})
        score = round(weighted / available_weight, 2) if available_weight > 0 else None
        coverage = min(1.0, available_weight / total_config_weight) if total_config_weight > 0 else 0.0
        out[commune] = {"score": score, "coverage": round(coverage, 4), "components": details}
    return out


def build_cead_geographic_score(master: list[dict], config: dict | None = None) -> list[dict]:
    config = config or _load_config()
    years = sorted({int(r["year"]) for r in master if r.get("year") is not None})
    if not years:
        return []
    latest_year = max(years)
    metadata = {}
    communes = set()
    for r in master:
        code = str(r.get("commune_code") or "").zfill(5)
        if len(code) == 5 and code.isdigit():
            communes.add(code)
            metadata.setdefault(code, {"territory_id": r.get("territory_id") or f"CL-{code}", "region_code": r.get("region_code"), "region_name": r.get("region_name"), "commune_code": code, "commune_name": r.get("commune_name")})
    communes = sorted(communes)

    layers = {}
    for layer_id, layer_cfg in config["layers"].items():
        layers[layer_id] = _build_layer(master, communes, latest_year, layer_cfg, layer_id)

    lw = config["layer_weights"]
    out = []
    for commune in communes:
        available_layer_weight = 0.0
        weighted_score = 0.0
        confidence_numerator = 0.0
        layer_rows = {}
        for layer_id, configured_weight in lw.items():
            row = layers[layer_id][commune]
            layer_rows[layer_id] = {"label": config["layers"][layer_id]["label"], "configured_weight": configured_weight, **row}
            if row["score"] is not None:
                available_layer_weight += configured_weight
                weighted_score += configured_weight * row["score"]
                confidence_numerator += configured_weight * row["coverage"]
        score = round(weighted_score / available_layer_weight, 2) if available_layer_weight > 0 else None
        confidence = round(100.0 * confidence_numerator / sum(lw.values()), 1)
        level = None
        if score is not None:
            level = "Muy alto" if score >= 80 else "Alto" if score >= 65 else "Medio" if score >= 45 else "Bajo" if score >= 25 else "Muy bajo"
        out.append({**metadata[commune], "period": str(latest_year), "year": latest_year, "signal_family": "cead_criminogenic_geographic_score", "score": score, "level": level, "confidence": confidence, "score_version": config["version"], "layer_weights": lw, "layers": layer_rows, "interpretation": config["methodology"]["interpretation"]})
    return sorted(out, key=lambda r: ((r.get("score") is not None), r.get("score") or -1, r.get("commune_code")), reverse=True)


def _integration_rows(score_rows: list[dict]) -> list[dict]:
    rows = []
    for r in score_rows:
        rows.append({
            "territory_id": r["territory_id"], "geography_level": "commune", "period": r["period"],
            "signal_family": "cead_criminogenic_geographic_score", "score": r.get("score"), "value": None,
            "metric": "score_0_100", "score_version": r.get("score_version"), "aml_relevance": "territorial_criminogenic_context",
            "confidence": r.get("confidence"), "layer_weights": r.get("layer_weights"), "layers": r.get("layers"),
            "join_keys": {"region_code": r.get("region_code"), "commune_code": r.get("commune_code"), "commune_name_norm": _norm(r.get("commune_name"))},
            "source_families": ["cead_estadisticas_delictuales"], "excludes_homicide_as_predicate": True,
            "interpretation": r.get("interpretation")
        })
    return rows


def _methodology_html(config: dict, score_rows: list[dict]) -> str:
    top = "".join(
        f'<tr><td>{i}</td><td>{r.get("commune_name", "")}</td><td>{r.get("region_name", "") or ""}</td><td class="num strong">{r.get("score") if r.get("score") is not None else "—"}</td><td>{r.get("level") or "—"}</td><td class="num">{r.get("confidence")}%</td></tr>'
        for i, r in enumerate(score_rows[:25], 1)
    ) or '<tr><td colspan="6">Sin score disponible.</td></tr>'
    layer_lines = []
    for lid, weight in config["layer_weights"].items():
        l = config["layers"][lid]
        comps = ", ".join(f'{c["label"]} ({round(c["weight"]*100)}%)' for c in l.get("components", []))
        layer_lines.append(f'<li><b>{l["label"]}: {round(weight*100)}%</b>. {comps}</li>')
    return f'''<section class="panel" style="margin-top:14px" id="cead-geographic-score"><h2>Componente criminógeno CEAD · score geográfico</h2><table><thead><tr><th>#</th><th>Comuna</th><th>Región</th><th>Score</th><th>Nivel</th><th>Confianza</th></tr></thead><tbody>{top}</tbody></table><details class="note" style="margin-top:14px"><summary style="cursor:pointer;font-weight:800">Ayuda metodológica · cómo se calcula</summary><div style="margin-top:10px"><p><b>Estructura:</b> 55% delito base directo + 35% economía criminal y facilitadores + 10% contexto criminógeno.</p><ul>{''.join(layer_lines)}</ul><p><b>Dentro de cada componente:</b> intensidad 40%, persistencia 25%, tendencia 20% y anomalía 15%.</p><p><b>Intensidad:</b> {config['methodology']['intensity']}</p><p><b>Persistencia:</b> {config['methodology']['persistence']}</p><p><b>Tendencia:</b> {config['methodology']['trend']}</p><p><b>Anomalía:</b> {config['methodology']['anomaly']}</p><p><b>Datos faltantes:</b> {config['methodology']['missing_data']}</p><p><b>Interpretación:</b> {config['methodology']['interpretation']}</p></div></details></section>'''


def materialize_geographic_score() -> dict:
    config = _load_config()
    master_path = PROCESSED_DIR / "cead_annual_master_v4.jsonl"
    if not master_path.exists():
        return {"ok": False, "reason": "cead_annual_master_v4.jsonl no disponible"}
    master = [json.loads(line) for line in master_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    scores = build_cead_geographic_score(master, config)
    (PROCESSED_DIR / "cead_geographic_score_v1.json").write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
    (PROCESSED_DIR / "cead_geographic_score_methodology_v1.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    integration_path = PROCESSED_DIR / "integration_ready.json"
    integration = json.loads(integration_path.read_text(encoding="utf-8")) if integration_path.exists() else []
    integration = [r for r in integration if r.get("signal_family") != "cead_criminogenic_geographic_score"] + _integration_rows(scores)
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

    return {"ok": True, "score_version": config["version"], "records": len(scores), "output": str(PROCESSED_DIR / "cead_geographic_score_v1.json")}
