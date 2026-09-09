from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path


def load(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x * x for x in dx) * sum(y * y for y in dy))
    if not den:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / den


def rank_map(rows: dict[str, dict]) -> dict[str, int]:
    ids = sorted(rows, key=lambda tid: (-float(rows[tid]["score"]), tid))
    return {tid: idx + 1 for idx, tid in enumerate(ids)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True, help="snapshot candidate.3")
    ap.add_argument("--rc1", default="data/processed/cead_geographic_score_v11_candidate.json")
    ap.add_argument("--v1", default="data/processed/cead_geographic_score_v1.json")
    ap.add_argument("--backtest", default="analysis/igr_v11_candidate3_backtest_2023_2025.json")
    ap.add_argument("--out", default="analysis/igr_v11_rc1_validation.json")
    args = ap.parse_args()

    baseline_rows = load(args.baseline)
    rc1_rows = load(args.rc1)
    v1_rows = load(args.v1)
    backtest = load(args.backtest)

    baseline = {r["territory_id"]: r for r in baseline_rows if r.get("score") is not None}
    rc1 = {r["territory_id"]: r for r in rc1_rows if r.get("score") is not None}
    v1 = {r["territory_id"]: r for r in v1_rows if r.get("score") is not None}
    common = sorted(set(baseline) & set(rc1) & set(v1))
    if len(common) < 300:
        raise SystemExit(f"Cobertura insuficiente: {len(common)}")

    score_diffs = [abs(float(rc1[t]["score"]) - float(baseline[t]["score"])) for t in common]
    level_diffs = sum(rc1[t].get("provisional_level") != baseline[t].get("provisional_level") for t in common)

    confidences = [float(rc1[t]["confidence"]) for t in common]
    baseline_confidences = [float(baseline[t]["confidence"]) for t in common]
    log_pop = [math.log(float(rc1[t]["population"])) for t in common if float(rc1[t].get("population") or 0) > 0]
    pop_ids = [t for t in common if float(rc1[t].get("population") or 0) > 0]
    rc1_conf_pop = corr([float(rc1[t]["confidence"]) for t in pop_ids], log_pop)
    baseline_conf_pop = corr([float(baseline[t]["confidence"]) for t in pop_ids], log_pop)
    rc1_conf_stability = corr(
        [float(rc1[t]["confidence"]) for t in common],
        [float((rc1[t].get("confidence_components") or {}).get("stability") or 0) for t in common],
    )

    rc1_rank = rank_map(rc1)
    v1_rank = rank_map(v1)
    score_corr = corr([float(v1[t]["score"]) for t in common], [float(rc1[t]["score"]) for t in common])
    rank_corr = corr([float(v1_rank[t]) for t in common], [float(rc1_rank[t]) for t in common])
    v1_pop_corr = corr([float(v1[t]["score"]) for t in pop_ids], log_pop)
    rc1_pop_corr = corr([float(rc1[t]["score"]) for t in pop_ids], log_pop)

    confidence_counts = Counter(str(rc1[t].get("confidence_level") or "Sin nivel") for t in common)
    provisional_changes = [t for t in common if v1[t].get("level") != rc1[t].get("provisional_level")]
    borderline = [t for t in common if rc1[t].get("provisional_boundary_status") == "borderline"]

    order = {"Muy bajo": 0, "Bajo": 1, "Medio": 2, "Alto": 3, "Muy alto": 4}
    threshold_only = []
    coherent = []
    for t in provisional_changes:
        old_level = v1[t].get("level")
        new_level = rc1[t].get("provisional_level")
        if old_level not in order or new_level not in order:
            continue
        band_step = order[new_level] - order[old_level]
        delta = float(rc1[t]["score"]) - float(v1[t]["score"])
        if (band_step > 0 and delta <= 0) or (band_step < 0 and delta >= 0):
            threshold_only.append(t)
        else:
            coherent.append(t)

    adjacent = backtest.get("adjacent_year_stability") or {}
    churn_values = [float(v.get("level_churn_pct")) for v in adjacent.values() if v.get("level_churn_pct") is not None]
    mean_churn = statistics.mean(churn_values) if churn_values else None

    score_gate = (
        max(score_diffs, default=999) <= 1e-9
        and level_diffs == 0
        and score_corr is not None and score_corr >= 0.99
        and rank_corr is not None and rank_corr >= 0.99
        and v1_pop_corr is not None and rc1_pop_corr is not None
        and rc1_pop_corr < v1_pop_corr
    )
    confidence_gate = (
        rc1_conf_pop is not None and abs(rc1_conf_pop) < 0.20
        and len([k for k, v in confidence_counts.items() if v > 0]) >= 3
        and max(confidences) - min(confidences) >= 5.0
    )
    band_gate = bool(mean_churn is not None and mean_churn <= 25.0 and len(threshold_only) == 0)

    report = {
        "version": rc1_rows[0].get("score_version") if rc1_rows else None,
        "status": "release_candidate_validation",
        "matched_communes": len(common),
        "formula_freeze": {
            "baseline_version": baseline_rows[0].get("score_version") if baseline_rows else None,
            "max_abs_score_difference": round(max(score_diffs, default=0.0), 10),
            "provisional_level_differences": level_diffs,
            "score_identical_to_candidate3": max(score_diffs, default=1.0) <= 1e-9,
        },
        "score": {
            "score_correlation_v1": round(score_corr, 4) if score_corr is not None else None,
            "rank_correlation_v1": round(rank_corr, 4) if rank_corr is not None else None,
            "population_bias_v1": round(v1_pop_corr, 4) if v1_pop_corr is not None else None,
            "population_bias_rc1": round(rc1_pop_corr, 4) if rc1_pop_corr is not None else None,
            "population_bias_reduction": round(v1_pop_corr - rc1_pop_corr, 4) if v1_pop_corr is not None and rc1_pop_corr is not None else None,
        },
        "confidence": {
            "baseline_candidate3_corr_log_population": round(baseline_conf_pop, 4) if baseline_conf_pop is not None else None,
            "rc1_corr_log_population": round(rc1_conf_pop, 4) if rc1_conf_pop is not None else None,
            "rc1_corr_stability": round(rc1_conf_stability, 4) if rc1_conf_stability is not None else None,
            "min": round(min(confidences), 1),
            "median": round(statistics.median(confidences), 1),
            "mean": round(statistics.mean(confidences), 1),
            "max": round(max(confidences), 1),
            "sd": round(statistics.pstdev(confidences), 2),
            "levels": dict(confidence_counts),
            "denominator_reliability_weight": 0.0,
            "interpretation": "El denominador sigue visible y modula el peso de la tasa, pero deja de entrar al compuesto de confianza para evitar doble penalización y efecto proxy de población.",
        },
        "bands": {
            "provisional_changes_vs_v1": len(provisional_changes),
            "borderline_communes": len(borderline),
            "threshold_only_or_direction_inversion_changes": len(threshold_only),
            "direction_coherent_changes": len(coherent),
            "mean_historical_churn_pct": round(mean_churn, 2) if mean_churn is not None else None,
            "historical_churn": {k: v.get("level_churn_pct") for k, v in adjacent.items()},
            "interpretation": "La banda sigue siendo diagnóstica: un recambio anual alto y cambios producidos por recalibración de cortes impiden promoverla como clasificación oficial.",
        },
        "gates": {
            "score_rc_ready": score_gate,
            "confidence_rc_ready": confidence_gate,
            "bands_rc_ready": band_gate,
            "full_replacement_ready": bool(score_gate and confidence_gate and band_gate),
        },
        "decision": (
            "PROMOTE_SCORE_AND_CONFIDENCE_TO_RC1_KEEP_BANDS_DIAGNOSTIC"
            if score_gate and confidence_gate and not band_gate
            else "FULL_REPLACEMENT_READY"
            if score_gate and confidence_gate and band_gate
            else "REJECT_RC1"
        ),
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not score_gate:
        raise SystemExit("FAIL: score RC1 no conserva candidate.3 o empeora controles")
    if not confidence_gate:
        raise SystemExit("FAIL: confianza RC1 aún presenta sesgo o poca discriminación")


if __name__ == "__main__":
    main()
