from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from pathlib import Path

from radar_delictual.geographic_score_runtime import normalize_quality_status
from radar_delictual.geographic_score_v11 import build_cead_geographic_score_v11_candidate, load_candidate_config
from radar_delictual.geographic_score_v11_runtime import _read_population_cache

PROCESSED = Path('data/processed')
ANALYSIS = Path('analysis')
LEVELS = ['Muy bajo', 'Bajo', 'Medio', 'Alto', 'Muy alto']


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def quantile(values: list[float], q: float) -> float | None:
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
    mx, my = statistics.mean(xs), statistics.mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return sum(x*y for x, y in zip(dx, dy)) / den if den else None


def rank_map(rows: dict[str, dict]) -> dict[str, int]:
    ids = sorted(rows, key=lambda t: (-float(rows[t]['score']), t))
    return {tid: i + 1 for i, tid in enumerate(ids)}


def main() -> None:
    raw_master = [
        json.loads(line)
        for line in (PROCESSED / 'cead_annual_master_v4.jsonl').read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]
    master = normalize_quality_status(raw_master)
    population, population_meta = _read_population_cache()
    candidate = load_candidate_config()
    calibration = load(ANALYSIS / 'igr_v11_candidate3_diagnostics.json')['provisional_calibration']
    b = calibration['thresholds']
    t25 = float(b['25']['candidate_threshold'])
    t45 = float(b['45']['candidate_threshold'])
    t65 = float(b['65']['candidate_threshold'])
    t80 = float(b['80']['candidate_threshold'])

    def level(score: float) -> str:
        return 'Muy alto' if score >= t80 else 'Alto' if score >= t65 else 'Medio' if score >= t45 else 'Bajo' if score >= t25 else 'Muy bajo'

    years_available = sorted({int(r['year']) for r in master if r.get('year') is not None})
    cutoffs = [y for y in (2023, 2024, 2025) if y in years_available]
    by_year: dict[int, dict[str, dict]] = {}
    year_summaries = {}

    for cutoff in cutoffs:
        subset = [r for r in master if r.get('year') is not None and int(r['year']) <= cutoff]
        rows = build_cead_geographic_score_v11_candidate(subset, population, candidate)
        rows = [r for r in rows if r.get('score') is not None]
        rowmap = {r['territory_id']: r for r in rows}
        by_year[cutoff] = rowmap
        scores = [float(r['score']) for r in rows]
        confidences = [float(r['confidence']) for r in rows if r.get('confidence') is not None]
        counts = Counter(level(float(r['score'])) for r in rows)
        shares = {lv: round(100 * counts.get(lv, 0) / len(rows), 2) for lv in LEVELS}
        pop_pairs = [
            (float(r['score']), math.log(float(r['population'])))
            for r in rows if float(r.get('population') or 0) > 0
        ]
        borderline_sd = 0
        within_one = 0
        for r in rows:
            score = float(r['score'])
            distances = [abs(score - x) for x in (t25, t45, t65, t80)]
            nearest = min(distances)
            sd = max(float(r.get('stability_sd') or 0), 0.5)
            borderline_sd += int(nearest <= sd)
            within_one += int(nearest <= 1.0)

        year_summaries[str(cutoff)] = {
            'communes': len(rows),
            'score_distribution': {
                'min': round(min(scores), 2),
                'p10': round(quantile(scores, .10), 2),
                'p25': round(quantile(scores, .25), 2),
                'median': round(statistics.median(scores), 2),
                'p75': round(quantile(scores, .75), 2),
                'p90': round(quantile(scores, .90), 2),
                'max': round(max(scores), 2),
            },
            'confidence': {
                'median': round(statistics.median(confidences), 1) if confidences else None,
                'min': round(min(confidences), 1) if confidences else None,
                'max': round(max(confidences), 1) if confidences else None,
            },
            'level_counts': {lv: counts.get(lv, 0) for lv in LEVELS},
            'level_shares_pct': shares,
            'population_bias_score_vs_log_population': round(corr([x for x, _ in pop_pairs], [y for _, y in pop_pairs]), 4),
            'borderline_within_stability_sd': borderline_sd,
            'within_one_point_of_boundary': within_one,
        }

    adjacent = {}
    for y0, y1 in zip(cutoffs, cutoffs[1:]):
        a, bmap = by_year[y0], by_year[y1]
        common = sorted(set(a) & set(bmap))
        ar, br = rank_map({i: a[i] for i in common}), rank_map({i: bmap[i] for i in common})
        changed = []
        for tid in common:
            la = level(float(a[tid]['score']))
            lb = level(float(bmap[tid]['score']))
            if la != lb:
                changed.append({
                    'territory_id': tid,
                    'commune_name': bmap[tid].get('commune_name'),
                    'from': la,
                    'to': lb,
                    'score_from': a[tid]['score'],
                    'score_to': bmap[tid]['score'],
                    'confidence_to': bmap[tid].get('confidence'),
                })
        top25_a = set(sorted(common, key=lambda i: float(a[i]['score']), reverse=True)[:25])
        top25_b = set(sorted(common, key=lambda i: float(bmap[i]['score']), reverse=True)[:25])
        adjacent[f'{y0}->{y1}'] = {
            'common_communes': len(common),
            'score_correlation': round(corr([float(a[i]['score']) for i in common], [float(bmap[i]['score']) for i in common]), 4),
            'rank_correlation': round(corr([float(ar[i]) for i in common], [float(br[i]) for i in common]), 4),
            'level_changes': len(changed),
            'level_churn_pct': round(100 * len(changed) / len(common), 2),
            'top25_overlap': len(top25_a & top25_b),
            'largest_score_moves': sorted(changed, key=lambda r: abs(float(r['score_to']) - float(r['score_from'])), reverse=True)[:15],
        }

    prevalence_drift = {}
    for lv in LEVELS:
        vals = [year_summaries[str(y)]['level_shares_pct'][lv] for y in cutoffs]
        prevalence_drift[lv] = {
            'min_share_pct': min(vals),
            'max_share_pct': max(vals),
            'range_pp': round(max(vals) - min(vals), 2),
        }

    report = {
        'candidate_version': candidate['version'],
        'status': 'diagnostic_only',
        'production_replaced': False,
        'population_reference': population_meta,
        'fixed_provisional_thresholds_from_2025': {
            'Muy alto': t80, 'Alto': t65, 'Medio': t45, 'Bajo': t25,
        },
        'cutoffs': cutoffs,
        'years': year_summaries,
        'adjacent_year_stability': adjacent,
        'prevalence_drift': prevalence_drift,
        'interpretation': (
            'Backtest descriptivo de estabilidad temporal. Usa Censo 2024 como denominador constante para aislar '
            'el comportamiento del índice. No valida causalidad ni convierte las bandas en oficiales.'
        ),
    }
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    (ANALYSIS / 'igr_v11_candidate3_backtest_2023_2025.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    print(json.dumps({'years': year_summaries, 'adjacent': adjacent, 'drift': prevalence_drift}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
