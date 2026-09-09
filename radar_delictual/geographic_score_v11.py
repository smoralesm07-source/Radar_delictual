from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict

from .config import CONFIG_DIR
from .geographic_score import _load_config as _load_v1_config
from .geographic_score import _norm, _percentile_rank, _quantile, _trend_score


def load_candidate_config() -> dict:
    return json.loads((CONFIG_DIR / "cead_geographic_score_v11_candidate.json").read_text(encoding="utf-8"))


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def _temporal_anomaly_score(history: list[float], current: float) -> float:
    """Anomalía del último valor respecto de la historia de la misma comuna."""
    if len(history) < 3:
        return 50.0
    med = statistics.median(history)
    deviations = [abs(x - med) for x in history]
    mad = statistics.median(deviations)
    if mad == 0:
        if current == med:
            return 50.0
        return 75.0 if current > med else 25.0
    robust_z = 0.6745 * (current - med) / mad
    return round(50.0 + 50.0 * math.tanh(robust_z / 3.0), 2)


def _population_reliability(population: float, candidate: dict) -> float:
    """Confiabilidad 0-1 del denominador para estabilizar tasas en comunas pequeñas."""
    if population <= 0:
        return 0.0
    reliability = candidate["intensity_mix"].get("rate_reliability", {})
    scale = float(reliability.get("population_scale", 25000))
    if scale <= 0:
        return 1.0
    return population / (population + scale)


def _source_quality_value(tier: str | None, candidate: dict) -> float:
    table = candidate["source_quality"]
    key = str(tier or "unknown")
    return float(table.get(key, table.get("unknown", 0.5)))


def _crime_series(master: list[dict], aliases: list[str], candidate: dict) -> tuple[dict, dict]:
    wanted = {_norm(a) for a in aliases}
    values: dict[tuple[str, int], float] = defaultdict(float)
    qualities: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in master:
        if row.get("quality_status") not in {None, "usable", "validated", "ok"}:
            continue
        if _norm(row.get("crime_category")) not in wanted:
            continue
        commune = str(row.get("commune_code") or "").zfill(5)
        if len(commune) != 5 or not commune.isdigit() or row.get("year") is None:
            continue
        key = (commune, int(row["year"]))
        values[key] += float(row.get("value") or 0)
        qualities[key].append(_source_quality_value(row.get("source_tier"), candidate))
    quality_mean = {key: statistics.mean(vals) for key, vals in qualities.items() if vals}
    return dict(values), quality_mean


def _component_metrics(
    series: dict[tuple[str, int], float],
    source_quality: dict[tuple[str, int], float],
    commune: str,
    latest_year: int,
    population: dict[str, float],
    candidate: dict,
    excluded_history_year: int | None = None,
) -> dict | None:
    years = sorted({
        year for c, year in series
        if c == commune and year <= latest_year and year != excluded_history_year
    })
    if not years or latest_year not in years:
        return None

    current = float(series.get((commune, latest_year), 0.0))
    latest_values = [float(v) for (c, y), v in series.items() if y == latest_year]
    volume_percentile = _percentile_rank(latest_values, current)

    pop = float(population.get(commune) or 0)
    rate_scale = float(candidate["population"].get("rate_scale", 100000))
    current_rate = (current / pop * rate_scale) if pop > 0 else None
    rate_values = []
    if current_rate is not None:
        for (c, y), value in series.items():
            if y != latest_year:
                continue
            p = float(population.get(c) or 0)
            if p > 0:
                rate_values.append(float(value) / p * rate_scale)
    rate_percentile = _percentile_rank(rate_values, current_rate) if current_rate is not None and rate_values else None

    mix = candidate["intensity_mix"]
    base_volume_weight = float(mix["volume_percentile"])
    base_rate_weight = float(mix["rate_per_100k_percentile"])
    denominator_reliability = _population_reliability(pop, candidate)
    if rate_percentile is None:
        intensity = volume_percentile
        population_available = False
        effective_rate_weight = 0.0
        effective_volume_weight = base_volume_weight + base_rate_weight
    else:
        # La tasa puede ser muy volátil en comunas pequeñas. El peso máximo de
        # tasa se contrae con el tamaño poblacional y lo que se retira vuelve a
        # volumen, de modo que la intensidad siempre conserva materialidad.
        effective_rate_weight = base_rate_weight * denominator_reliability
        effective_volume_weight = base_volume_weight + base_rate_weight * (1.0 - denominator_reliability)
        total_intensity_weight = effective_volume_weight + effective_rate_weight
        intensity = round(
            (effective_volume_weight * volume_percentile + effective_rate_weight * rate_percentile)
            / total_intensity_weight,
            2,
        ) if total_intensity_weight > 0 else volume_percentile
        population_available = True

    observed = 0
    high = 0
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
    raw_temporal_anomaly = _temporal_anomaly_score(history, current)

    # Una anomalía longitudinal puede ser matemáticamente grande con soporte
    # mínimo (por ejemplo, pasar de 0 a 1 caso). Eso es informativo como cambio,
    # pero no debe pesar igual que una ruptura sostenida sobre decenas de hechos.
    # Contraemos sólo la anomalía hacia el punto neutro 50; intensidad,
    # persistencia y tendencia permanecen intactas.
    anomaly_cfg = candidate.get("temporal_anomaly_reliability", {})
    support_scale = float(anomaly_cfg.get("support_scale", 20.0))
    anomaly_support = sum(max(0.0, x) for x in history) + max(0.0, current)
    anomaly_reliability = (
        anomaly_support / (anomaly_support + support_scale)
        if support_scale > 0 else 1.0
    )
    temporal_anomaly = round(
        50.0 + anomaly_reliability * (raw_temporal_anomaly - 50.0),
        2,
    )

    fw = candidate["feature_weights"]
    score = round(
        float(fw["intensity"]) * intensity
        + float(fw["persistence"]) * persistence
        + float(fw["trend"]) * trend
        + float(fw["temporal_anomaly"]) * temporal_anomaly,
        2,
    )

    quality_values = [source_quality[(commune, y)] for y in years if (commune, y) in source_quality]
    source_quality_mean = statistics.mean(quality_values) if quality_values else float(candidate["source_quality"]["unknown"])

    return {
        "score": score,
        "value": current,
        "population": int(pop) if pop > 0 else None,
        "rate_per_100k": round(current_rate, 2) if current_rate is not None else None,
        "volume_percentile": volume_percentile,
        "rate_percentile": rate_percentile,
        "rate_reliability": round(100.0 * denominator_reliability, 1),
        "effective_volume_weight": round(effective_volume_weight, 4),
        "effective_rate_weight": round(effective_rate_weight, 4),
        "intensity": intensity,
        "persistence": persistence,
        "trend": trend,
        "temporal_anomaly": temporal_anomaly,
        "temporal_anomaly_raw": raw_temporal_anomaly,
        "temporal_anomaly_reliability": round(100.0 * anomaly_reliability, 1),
        "temporal_anomaly_support": round(anomaly_support, 1),
        "years_observed": observed,
        "population_available": population_available,
        "source_quality": round(100.0 * source_quality_mean, 1),
    }


def _build_layer(
    master: list[dict],
    communes: list[str],
    latest_year: int,
    layer: dict,
    layer_id: str,
    population: dict[str, float],
    candidate: dict,
    expected_years: int,
    excluded_history_year: int | None = None,
) -> dict[str, dict]:
    components = layer.get("components", [])
    prepared = []
    for comp in components:
        series, source_quality = _crime_series(master, comp.get("aliases", []), candidate)
        if series:
            prepared.append((comp, series, source_quality, float(candidate["semantic_precision"]["default_component"])))

    # Igual que v1: la familia agregada de drogas permite calcular la capa,
    # pero en v1.1 su menor precisión semántica sí reduce la confianza.
    if layer_id == "predicate_direct" and not prepared:
        for alias in layer.get("fallback_aliases", []):
            series, source_quality = _crime_series(master, [alias], candidate)
            if series:
                prepared = [(
                    {"id": "drug_family_fallback", "label": alias, "weight": 1.0, "aliases": [alias]},
                    series,
                    source_quality,
                    float(candidate["semantic_precision"]["predicate_family_fallback"]),
                )]
                break

    out = {}
    total_config_weight = sum(float(c.get("weight", 0)) for c in components) or 1.0
    for commune in communes:
        details = []
        available_weight = 0.0
        weighted_score = 0.0
        thematic_numerator = 0.0
        temporal_numerator = 0.0
        source_numerator = 0.0
        population_numerator = 0.0
        for comp, series, source_quality, semantic_precision in prepared:
            metrics = _component_metrics(
                series,
                source_quality,
                commune,
                latest_year,
                population,
                candidate,
                excluded_history_year=excluded_history_year,
            )
            if not metrics:
                continue
            w = float(comp.get("weight", 0))
            available_weight += w
            weighted_score += w * metrics["score"]
            thematic_numerator += w * semantic_precision
            temporal_numerator += w * min(1.0, metrics["years_observed"] / max(expected_years, 1))
            source_numerator += w * (metrics["source_quality"] / 100.0)
            population_numerator += w * (1.0 if metrics["population_available"] else 0.0)
            details.append({
                "id": comp.get("id"),
                "label": comp.get("label"),
                "configured_weight": w,
                "semantic_precision": semantic_precision,
                **metrics,
            })

        score = round(weighted_score / available_weight, 2) if available_weight > 0 else None
        coverage = min(1.0, available_weight / total_config_weight) if total_config_weight > 0 else 0.0
        thematic = min(1.0, thematic_numerator / total_config_weight) if total_config_weight > 0 else 0.0
        temporal = min(1.0, temporal_numerator / total_config_weight) if total_config_weight > 0 else 0.0
        source = min(1.0, source_numerator / total_config_weight) if total_config_weight > 0 else 0.0
        population_cov = min(1.0, population_numerator / total_config_weight) if total_config_weight > 0 else 0.0
        out[commune] = {
            "score": score,
            "coverage": round(coverage, 4),
            "thematic_coverage": round(thematic, 4),
            "temporal_coverage": round(temporal, 4),
            "source_quality": round(source, 4),
            "population_coverage": round(population_cov, 4),
            "components": details,
        }
    return out


def _level(score: float | None) -> str | None:
    # Legado v1.0: solo para comparar. El candidato no promueve estas bandas.
    if score is None:
        return None
    return "Muy alto" if score >= 80 else "Alto" if score >= 65 else "Medio" if score >= 45 else "Bajo" if score >= 25 else "Muy bajo"


def _build_candidate_rows(
    master: list[dict],
    population: dict[str, float],
    candidate: dict,
    excluded_history_year: int | None = None,
    include_details: bool = True,
) -> list[dict]:
    base = _load_v1_config()
    years = sorted({int(r["year"]) for r in master if r.get("year") is not None})
    if not years:
        return []
    latest_year = max(years)
    expected_years = len(years)

    metadata = {}
    communes = set()
    for row in master:
        code = str(row.get("commune_code") or "").zfill(5)
        if len(code) == 5 and code.isdigit():
            communes.add(code)
            metadata.setdefault(code, {
                "territory_id": row.get("territory_id") or f"CL-{code}",
                "region_code": row.get("region_code"),
                "region_name": row.get("region_name"),
                "commune_code": code,
                "commune_name": row.get("commune_name"),
            })
    communes = sorted(communes)

    layers = {}
    for layer_id, layer_cfg in base["layers"].items():
        layers[layer_id] = _build_layer(
            master,
            communes,
            latest_year,
            layer_cfg,
            layer_id,
            population,
            candidate,
            expected_years,
            excluded_history_year=excluded_history_year,
        )

    layer_weights = base["layer_weights"]
    configured_total = sum(float(x) for x in layer_weights.values()) or 1.0
    rows = []
    for commune in communes:
        available_layer_weight = 0.0
        weighted_score = 0.0
        methodological_coverage = 0.0
        thematic = 0.0
        temporal = 0.0
        source = 0.0
        population_cov = 0.0
        layer_rows = {}
        for layer_id, configured_weight in layer_weights.items():
            row = layers[layer_id][commune]
            if include_details:
                layer_rows[layer_id] = {
                    "label": base["layers"][layer_id]["label"],
                    "configured_weight": configured_weight,
                    **row,
                }
            if row["score"] is not None:
                available_layer_weight += float(configured_weight)
                weighted_score += float(configured_weight) * float(row["score"])
            methodological_coverage += float(configured_weight) * float(row["coverage"])
            thematic += float(configured_weight) * float(row["thematic_coverage"])
            temporal += float(configured_weight) * float(row["temporal_coverage"])
            source += float(configured_weight) * float(row["source_quality"])
            population_cov += float(configured_weight) * float(row["population_coverage"])

        score = round(weighted_score / available_layer_weight, 2) if available_layer_weight > 0 else None
        pop = float(population.get(commune) or 0)
        denominator_reliability = 100.0 * _population_reliability(pop, candidate)
        rows.append({
            **metadata[commune],
            "period": str(latest_year),
            "year": latest_year,
            "signal_family": "cead_criminogenic_geographic_score_candidate",
            "score": score,
            "level": _level(score),
            "level_status": "comparison_only",
            "confidence": None,
            "score_version": candidate["version"],
            "base_score_version": candidate["base_score_version"],
            "layer_weights": layer_weights,
            "layers": layer_rows if include_details else None,
            "methodological_coverage": round(100.0 * methodological_coverage / configured_total, 1),
            "confidence_components": {
                "thematic_coverage": round(100.0 * thematic / configured_total, 1),
                "temporal_coverage": round(100.0 * temporal / configured_total, 1),
                "source_quality": round(100.0 * source / configured_total, 1),
                "stability": None,
                "denominator_reliability": round(denominator_reliability, 1),
            },
            "population": int(pop) if pop > 0 else None,
            "population_coverage": round(100.0 * population_cov / configured_total, 1),
            "population_available": bool(pop),
            "interpretation": candidate["methodology"]["interpretation"],
        })
    return sorted(rows, key=lambda r: ((r.get("score") is not None), r.get("score") or -1, r.get("commune_code")), reverse=True)


def build_cead_geographic_score_v11_candidate(
    master: list[dict],
    population: dict[str, float] | None = None,
    candidate: dict | None = None,
) -> list[dict]:
    candidate = candidate or load_candidate_config()
    population = population or {}
    rows = _build_candidate_rows(master, population, candidate, include_details=True)
    if not rows:
        return []

    latest_year = max(int(row["year"]) for row in rows)
    history_years = sorted({
        int(r["year"]) for r in master
        if r.get("year") is not None and int(r["year"]) < latest_year
    })
    variants: dict[str, list[float]] = defaultdict(list)
    for year in history_years:
        candidate_rows = _build_candidate_rows(
            master,
            population,
            candidate,
            excluded_history_year=year,
            include_details=False,
        )
        for row in candidate_rows:
            if row.get("score") is not None:
                variants[row["territory_id"]].append(float(row["score"]))

    cw = candidate["confidence_weights"]
    penalty = float(candidate["stability"]["penalty_per_sd_point"])
    minimum_variants = int(candidate["stability"]["minimum_variants"])
    bands = candidate.get("confidence_bands", {"high_min": 80, "medium_min": 70})
    for row in rows:
        values = variants.get(row["territory_id"], [])
        if len(values) >= minimum_variants:
            sd = statistics.pstdev(values)
            stability = _clamp(100.0 - penalty * sd)
        else:
            sd = None
            stability = 50.0
        row["confidence_components"]["stability"] = round(stability, 1)
        row["stability_sd"] = round(sd, 3) if sd is not None else None
        confidence = (
            float(cw["thematic_coverage"]) * row["confidence_components"]["thematic_coverage"]
            + float(cw["temporal_coverage"]) * row["confidence_components"]["temporal_coverage"]
            + float(cw["source_quality"]) * row["confidence_components"]["source_quality"]
            + float(cw["stability"]) * row["confidence_components"]["stability"]
            + float(cw["denominator_reliability"]) * row["confidence_components"]["denominator_reliability"]
        )
        row["confidence"] = round(_clamp(confidence), 1)
        row["confidence_level"] = (
            "Alta" if confidence >= float(bands["high_min"])
            else "Media" if confidence >= float(bands["medium_min"])
            else "Baja"
        )

    return rows


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if den == 0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / den


def _distribution(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "min": None, "p10": None, "p25": None, "median": None, "p75": None, "p90": None, "max": None}
    xs = sorted(float(x) for x in values)
    return {
        "n": len(xs),
        "min": round(xs[0], 2),
        "p10": round(_quantile(xs, 0.10), 2),
        "p25": round(_quantile(xs, 0.25), 2),
        "median": round(statistics.median(xs), 2),
        "p75": round(_quantile(xs, 0.75), 2),
        "p90": round(_quantile(xs, 0.90), 2),
        "max": round(xs[-1], 2),
    }


def compare_v1_candidate(v1_rows: list[dict], candidate_rows: list[dict], population: dict[str, float] | None = None) -> dict:
    population = population or {}
    v1 = {row["territory_id"]: row for row in v1_rows if row.get("score") is not None}
    cand = {row["territory_id"]: row for row in candidate_rows if row.get("score") is not None}
    common = sorted(set(v1) & set(cand))
    if not common:
        return {"matched": 0}

    v1_rank = {tid: i + 1 for i, tid in enumerate(sorted(common, key=lambda t: float(v1[t]["score"]), reverse=True))}
    cand_rank = {tid: i + 1 for i, tid in enumerate(sorted(common, key=lambda t: float(cand[t]["score"]), reverse=True))}

    v1_scores = [float(v1[t]["score"]) for t in common]
    cand_scores = [float(cand[t]["score"]) for t in common]
    score_corr = _pearson(v1_scores, cand_scores)
    rank_corr = _pearson([float(v1_rank[t]) for t in common], [float(cand_rank[t]) for t in common])

    pop_ids = [t for t in common if float(population.get(str(cand[t].get("commune_code"))) or 0) > 0]
    log_pop = [math.log(float(population[str(cand[t]["commune_code"])])) for t in pop_ids]
    v1_pop_corr = _pearson([float(v1[t]["score"]) for t in pop_ids], log_pop) if pop_ids else None
    cand_pop_corr = _pearson([float(cand[t]["score"]) for t in pop_ids], log_pop) if pop_ids else None

    changes = []
    for tid in common:
        a = v1[tid]
        b = cand[tid]
        changes.append({
            "territory_id": tid,
            "commune_code": b.get("commune_code"),
            "commune_name": b.get("commune_name"),
            "region_name": b.get("region_name"),
            "v1_score": a.get("score"),
            "candidate_score": b.get("score"),
            "score_delta": round(float(b["score"]) - float(a["score"]), 2),
            "v1_level": a.get("level"),
            "candidate_level": b.get("level"),
            "candidate_level_status": b.get("level_status"),
            "v1_rank": v1_rank[tid],
            "candidate_rank": cand_rank[tid],
            "rank_delta": v1_rank[tid] - cand_rank[tid],
            "candidate_confidence": b.get("confidence"),
            "candidate_confidence_level": b.get("confidence_level"),
            "methodological_coverage": b.get("methodological_coverage"),
            "denominator_reliability": (b.get("confidence_components") or {}).get("denominator_reliability"),
        })
    changes.sort(key=lambda r: abs(float(r["score_delta"])), reverse=True)

    confidences = [float(cand[t]["confidence"]) for t in common if cand[t].get("confidence") is not None]
    top_n = min(25, len(common))
    top_v1 = {t for t, _ in sorted(v1.items(), key=lambda x: float(x[1]["score"]), reverse=True)[:top_n]}
    top_cand = {t for t, _ in sorted(cand.items(), key=lambda x: float(x[1]["score"]), reverse=True)[:top_n]}

    component_names = ["thematic_coverage", "temporal_coverage", "source_quality", "stability", "denominator_reliability"]
    confidence_component_distributions = {}
    for name in component_names:
        vals = [
            float((cand[t].get("confidence_components") or {}).get(name))
            for t in common
            if (cand[t].get("confidence_components") or {}).get(name) is not None
        ]
        confidence_component_distributions[name] = _distribution(vals)

    methodological_coverages = [
        float(cand[t]["methodological_coverage"])
        for t in common if cand[t].get("methodological_coverage") is not None
    ]
    level_counts = defaultdict(int)
    for t in common:
        level_counts[str(cand[t].get("level") or "Sin nivel")] += 1

    return {
        "matched": len(common),
        "score_correlation": round(score_corr, 4) if score_corr is not None else None,
        "rank_correlation": round(rank_corr, 4) if rank_corr is not None else None,
        "level_changes": sum(v1[t].get("level") != cand[t].get("level") for t in common),
        "level_policy": "legacy_thresholds_for_comparison_only",
        "candidate_level_counts": dict(level_counts),
        "top25_overlap": len(top_v1 & top_cand),
        "score_distribution": {
            "v1": _distribution(v1_scores),
            "candidate": _distribution(cand_scores),
        },
        "methodological_coverage": _distribution(methodological_coverages),
        "confidence": {
            **_distribution(confidences),
            "distinct_rounded": len(set(confidences)),
            "bands": {
                "Alta": sum(cand[t].get("confidence_level") == "Alta" for t in common),
                "Media": sum(cand[t].get("confidence_level") == "Media" for t in common),
                "Baja": sum(cand[t].get("confidence_level") == "Baja" for t in common),
            },
            "components": confidence_component_distributions,
        },
        "population_bias": {
            "matched_population": len(pop_ids),
            "v1_score_vs_log_population": round(v1_pop_corr, 4) if v1_pop_corr is not None else None,
            "candidate_score_vs_log_population": round(cand_pop_corr, 4) if cand_pop_corr is not None else None,
        },
        "largest_score_changes": changes[:50],
    }
