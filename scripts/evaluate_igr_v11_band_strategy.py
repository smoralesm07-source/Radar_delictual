from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from pathlib import Path

from radar_delictual.geographic_score_runtime import normalize_quality_status
from radar_delictual.geographic_score_v11 import (
    build_cead_geographic_score_v11_candidate,
    load_candidate_config,
)
from radar_delictual.geographic_score_v11_runtime import _read_population_cache

PROCESSED = Path("data/processed")
ANALYSIS = Path("analysis")
LEVELS = ["Muy bajo", "Bajo", "Medio", "Alto", "Muy alto"]
LEVEL_INDEX = {name: i for i, name in enumerate(LEVELS)}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    return sum(x * y for x, y in zip(dx, dy)) / den if den else None


def fixed_level(score: float, boundaries: list[float]) -> str:
    b0, b1, b2, b3 = boundaries
    return (
        "Muy alto" if score >= b3
        else "Alto" if score >= b2
        else "Medio" if score >= b1
        else "Bajo" if score >= b0
        else "Muy bajo"
    )


def hysteresis_level(score: float, previous: str, boundaries: list[float], margin: float) -> str:
    """Aplica histéresis simétrica conservando estado de la banda previa."""
    idx = LEVEL_INDEX[previous]
    while idx < len(LEVELS) - 1 and score >= boundaries[idx] + margin:
        idx += 1
    while idx > 0 and score < boundaries[idx - 1] - margin:
        idx -= 1
    return LEVELS[idx]


def assign_relative_bands(rows: dict[str, dict], target_counts: dict[str, int]) -> dict[str, str]:
    """Bandas por posición nacional, manteniendo la prevalencia 2025 de RC1."""
    ordered = sorted(rows, key=lambda tid: (-float(rows[tid]["score"]), tid))
    out: dict[str, str] = {}
    cursor = 0
    for level in reversed(LEVELS):
        count = int(target_counts.get(level, 0))
        for tid in ordered[cursor:cursor + count]:
            out[tid] = level
        cursor += count
    for tid in ordered[cursor:]:
        out[tid] = "Muy bajo"
    return out


def rank_percentiles(rows: dict[str, dict]) -> dict[str, float]:
    ordered = sorted(rows, key=lambda tid: (-float(rows[tid]["score"]), tid))
    n = len(ordered)
    if n <= 1:
        return {tid: 100.0 for tid in ordered}
    return {
        tid: round(100.0 * (n - 1 - rank) / (n - 1), 1)
        for rank, tid in enumerate(ordered)
    }


def transition_metrics(
    prev_rows: dict[str, dict],
    curr_rows: dict[str, dict],
    prev_labels: dict[str, str],
    curr_labels: dict[str, str],
    prev_pct: dict[str, float],
    curr_pct: dict[str, float],
) -> dict:
    common = sorted(set(prev_rows) & set(curr_rows))
    changed = []
    counter_direction = 0
    large_moves = 0
    large_moves_with_band_change = 0
    abs_pct_moves = []
    score_pairs = []
    pct_pairs = []

    for tid in common:
        before = float(prev_rows[tid]["score"])
        after = float(curr_rows[tid]["score"])
        delta = after - before
        score_pairs.append((before, after))
        pct_pairs.append((float(prev_pct[tid]), float(curr_pct[tid])))
        abs_pct_moves.append(abs(float(curr_pct[tid]) - float(prev_pct[tid])))
        label_changed = prev_labels[tid] != curr_labels[tid]
        if abs(delta) >= 5.0:
            large_moves += 1
            large_moves_with_band_change += int(label_changed)
        if label_changed:
            direction = LEVEL_INDEX[curr_labels[tid]] - LEVEL_INDEX[prev_labels[tid]]
            if (direction > 0 and delta < 0) or (direction < 0 and delta > 0):
                counter_direction += 1
            changed.append({
                "territory_id": tid,
                "commune_name": curr_rows[tid].get("commune_name"),
                "from": prev_labels[tid],
                "to": curr_labels[tid],
                "score_from": before,
                "score_to": after,
                "score_delta": round(delta, 2),
                "percentile_from": prev_pct[tid],
                "percentile_to": curr_pct[tid],
            })

    small_change_count = sum(abs(float(item["score_delta"])) < 3.0 for item in changed)
    return {
        "common_communes": len(common),
        "band_changes": len(changed),
        "band_churn_pct": round(100.0 * len(changed) / len(common), 2) if common else None,
        "small_move_changes_lt3": small_change_count,
        "small_move_share_of_changes_pct": round(100.0 * small_change_count / len(changed), 2) if changed else 0.0,
        "counter_direction_changes": counter_direction,
        "large_score_moves_ge5": large_moves,
        "large_move_band_change_rate_pct": round(100.0 * large_moves_with_band_change / large_moves, 2) if large_moves else None,
        "score_correlation": round(corr([x for x, _ in score_pairs], [y for _, y in score_pairs]), 4) if score_pairs else None,
        "percentile_correlation": round(corr([x for x, _ in pct_pairs], [y for _, y in pct_pairs]), 4) if pct_pairs else None,
        "median_abs_percentile_move": round(statistics.median(abs_pct_moves), 1) if abs_pct_moves else None,
        "p90_abs_percentile_move": round(percentile(abs_pct_moves, 0.90), 1) if abs_pct_moves else None,
        "largest_band_changes": sorted(changed, key=lambda item: abs(float(item["score_delta"])), reverse=True)[:15],
    }


def prevalence(labels: dict[str, str]) -> dict[str, float]:
    counts = Counter(labels.values())
    n = len(labels)
    return {
        level: round(100.0 * counts.get(level, 0) / n, 2) if n else 0.0
        for level in LEVELS
    }


def prevalence_drift(year_labels: dict[int, dict[str, str]]) -> dict:
    out = {}
    for level in LEVELS:
        shares = [prevalence(labels)[level] for labels in year_labels.values()]
        out[level] = {
            "min_pct": min(shares),
            "max_pct": max(shares),
            "range_pp": round(max(shares) - min(shares), 2),
        }
    return out


def summarize_strategy(name: str, year_labels: dict[int, dict[str, str]], by_year: dict[int, dict[str, dict]], pcts: dict[int, dict[str, float]]) -> dict:
    years = sorted(year_labels)
    transitions = {}
    churn = []
    small_share = []
    counter = 0
    large_capture = []
    for y0, y1 in zip(years, years[1:]):
        metrics = transition_metrics(
            by_year[y0], by_year[y1],
            year_labels[y0], year_labels[y1],
            pcts[y0], pcts[y1],
        )
        transitions[f"{y0}->{y1}"] = metrics
        churn.append(float(metrics["band_churn_pct"] or 0.0))
        small_share.append(float(metrics["small_move_share_of_changes_pct"] or 0.0))
        counter += int(metrics["counter_direction_changes"])
        if metrics["large_move_band_change_rate_pct"] is not None:
            large_capture.append(float(metrics["large_move_band_change_rate_pct"]))

    return {
        "name": name,
        "mean_band_churn_pct": round(statistics.mean(churn), 2) if churn else None,
        "mean_small_move_share_of_changes_pct": round(statistics.mean(small_share), 2) if small_share else None,
        "counter_direction_changes_total": counter,
        "mean_large_move_band_change_rate_pct": round(statistics.mean(large_capture), 2) if large_capture else None,
        "year_prevalence_pct": {str(y): prevalence(year_labels[y]) for y in years},
        "prevalence_drift": prevalence_drift(year_labels),
        "transitions": transitions,
    }


def main() -> None:
    raw_master = [
        json.loads(line)
        for line in (PROCESSED / "cead_annual_master_v4.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    master = normalize_quality_status(raw_master)
    population, population_meta = _read_population_cache()
    config = load_candidate_config()
    policy = (config.get("level_policy") or {}).get("provisional_candidate3") or {}
    thresholds = policy.get("thresholds") or {}
    boundaries = [
        float(thresholds["bajo_min"]),
        float(thresholds["medio_min"]),
        float(thresholds["alto_min"]),
        float(thresholds["muy_alto_min"]),
    ]

    available_years = sorted({int(r["year"]) for r in master if r.get("year") is not None})
    years = [y for y in (2023, 2024, 2025) if y in available_years]
    by_year: dict[int, dict[str, dict]] = {}
    pcts: dict[int, dict[str, float]] = {}
    fixed: dict[int, dict[str, str]] = {}

    for cutoff in years:
        subset = [r for r in master if r.get("year") is not None and int(r["year"]) <= cutoff]
        rows = build_cead_geographic_score_v11_candidate(subset, population, config)
        rowmap = {r["territory_id"]: r for r in rows if r.get("score") is not None}
        by_year[cutoff] = rowmap
        pcts[cutoff] = rank_percentiles(rowmap)
        fixed[cutoff] = {tid: fixed_level(float(row["score"]), boundaries) for tid, row in rowmap.items()}

    if not years:
        raise SystemExit("No hay cortes 2023-2025 disponibles")

    # Histéresis: parte de la banda fija en el primer corte y conserva estado.
    hysteresis: dict[int, dict[str, str]] = {years[0]: dict(fixed[years[0]])}
    for previous_year, current_year in zip(years, years[1:]):
        labels = {}
        for tid, row in by_year[current_year].items():
            previous = hysteresis[previous_year].get(tid, fixed[current_year][tid])
            labels[tid] = hysteresis_level(float(row["score"]), previous, boundaries, 1.0)
        hysteresis[current_year] = labels

    # Bandas relativas: mantienen exactamente la distribución 2025 del esquema fijo.
    reference_year = years[-1]
    reference_counts = Counter(fixed[reference_year].values())
    relative = {
        year: assign_relative_bands(by_year[year], dict(reference_counts))
        for year in years
    }

    fixed_summary = summarize_strategy("fixed_thresholds", fixed, by_year, pcts)
    hysteresis_summary = summarize_strategy("one_point_hysteresis", hysteresis, by_year, pcts)
    relative_summary = summarize_strategy("relative_rank_bands", relative, by_year, pcts)

    percentile_transitions = {}
    for y0, y1 in zip(years, years[1:]):
        common = sorted(set(by_year[y0]) & set(by_year[y1]))
        abs_moves = [abs(pcts[y1][tid] - pcts[y0][tid]) for tid in common]
        percentile_transitions[f"{y0}->{y1}"] = {
            "communes": len(common),
            "correlation": round(corr([pcts[y0][t] for t in common], [pcts[y1][t] for t in common]), 4),
            "median_abs_move": round(statistics.median(abs_moves), 1),
            "p90_abs_move": round(percentile(abs_moves, 0.90), 1),
            "within_5_points_pct": round(100.0 * sum(v <= 5 for v in abs_moves) / len(abs_moves), 2),
            "within_10_points_pct": round(100.0 * sum(v <= 10 for v in abs_moves) / len(abs_moves), 2),
        }

    report = {
        "version": config.get("version"),
        "status": "band_strategy_evaluation",
        "score_formula_changed": False,
        "confidence_formula_changed": False,
        "population_reference": population_meta,
        "years": years,
        "fixed_thresholds": {
            "bajo_min": boundaries[0],
            "medio_min": boundaries[1],
            "alto_min": boundaries[2],
            "muy_alto_min": boundaries[3],
        },
        "relative_band_reference_counts_2025": {level: reference_counts.get(level, 0) for level in LEVELS},
        "strategies": {
            "fixed_thresholds": fixed_summary,
            "one_point_hysteresis": {
                **hysteresis_summary,
                "stateful": True,
                "margin_points": 1.0,
            },
            "relative_rank_bands": {
                **relative_summary,
                "relative_to_other_communes": True,
                "prevalence_fixed_to_2025": True,
            },
            "score_plus_national_percentile": {
                "categorical_primary_churn": 0,
                "primary_outputs": ["score_0_100", "national_percentile_0_100"],
                "secondary_output": "diagnostic_band_with_borderline_warning",
                "percentile_transitions": percentile_transitions,
                "path_dependent": False,
                "relative_context_explicit": True,
            },
        },
        "decision": "PROMOTE_SCORE_PERCENTILE_PRIMARY_KEEP_BAND_SECONDARY",
        "decision_rationale": [
            "El score RC1 ya está congelado y validado; no necesita suavizamiento adicional.",
            "La histéresis reduce churn, pero introduce dependencia del estado previo y puede retrasar una reclasificación real.",
            "Las bandas por ranking estabilizan la prevalencia, pero convierten una lectura absoluta de amenaza en una clasificación relativa y pueden cambiar aunque el score de una comuna no empeore.",
            "Score + percentil nacional preserva magnitud continua y posición relativa sin crear una segunda fórmula ni una regla categórica primaria. La banda queda como apoyo de lectura, con alerta de frontera.",
        ],
        "promotion_gate": {
            "score_primary_ready": True,
            "national_percentile_ready": True,
            "band_secondary_ready": True,
            "band_primary_ready": False,
            "full_v11_replacement_recommended": True,
            "replacement_scope": "score_and_percentile_primary_band_secondary",
        },
    }

    ANALYSIS.mkdir(parents=True, exist_ok=True)
    out = ANALYSIS / "igr_v11_band_strategy_evaluation.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
