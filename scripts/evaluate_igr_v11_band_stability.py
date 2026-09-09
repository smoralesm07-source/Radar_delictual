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
LEVEL_INDEX = {x: i for i, x in enumerate(LEVELS)}
BOUNDARIES = [26.61, 45.43, 61.89, 71.12]


def raw_level(score: float) -> str:
    if score >= BOUNDARIES[3]: return 'Muy alto'
    if score >= BOUNDARIES[2]: return 'Alto'
    if score >= BOUNDARIES[1]: return 'Medio'
    if score >= BOUNDARIES[0]: return 'Bajo'
    return 'Muy bajo'


def hysteresis_level(score: float, previous: str, margin: float) -> str:
    idx = LEVEL_INDEX[previous]
    while idx < len(LEVELS) - 1 and score >= BOUNDARIES[idx] + margin:
        idx += 1
    while idx > 0 and score < BOUNDARIES[idx - 1] - margin:
        idx -= 1
    return LEVELS[idx]


def corr(xs, ys):
    if len(xs) != len(ys) or len(xs) < 3: return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    dx = [x-mx for x in xs]; dy = [y-my for y in ys]
    den = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    return sum(x*y for x,y in zip(dx,dy))/den if den else None


def load_v1() -> dict[str, dict]:
    rows = json.loads((PROCESSED / 'cead_geographic_score_v1.json').read_text(encoding='utf-8'))
    return {r['territory_id']: r for r in rows if r.get('score') is not None}


def build_years() -> dict[int, dict[str, dict]]:
    raw = [json.loads(line) for line in (PROCESSED/'cead_annual_master_v4.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    master = normalize_quality_status(raw)
    population, _ = _read_population_cache()
    candidate = load_candidate_config()
    out = {}
    for cutoff in (2022, 2023, 2024, 2025):
        subset = [r for r in master if r.get('year') is not None and int(r['year']) <= cutoff]
        rows = build_cead_geographic_score_v11_candidate(subset, population, candidate)
        out[cutoff] = {r['territory_id']: r for r in rows if r.get('score') is not None}
    return out


def churn(labels0: dict[str,str], labels1: dict[str,str]) -> dict:
    ids = sorted(set(labels0) & set(labels1))
    changed = [i for i in ids if labels0[i] != labels1[i]]
    return {'n': len(ids), 'changes': len(changed), 'churn_pct': round(100*len(changed)/len(ids),2)}


def main():
    years = build_years()
    v1 = load_v1()
    raw_labels = {y: {i: raw_level(float(r['score'])) for i,r in rows.items()} for y,rows in years.items()}

    strategies = {}

    # Stateful hysteresis: the score remains untouched. Only the published band
    # needs enough evidence to cross a boundary. This is preferable to smoothing
    # the score itself if it controls churn without masking large moves.
    hyst_specs = {
        'hysteresis_1pt': lambda row: 1.0,
        'hysteresis_2pt': lambda row: 2.0,
        'hysteresis_stability': lambda row: max(1.0, float(row.get('stability_sd') or 0)),
    }
    for name, margin_fn in hyst_specs.items():
        labels = {2022: dict(raw_labels[2022])}
        for year in (2023, 2024, 2025):
            prev = labels[year-1]
            cur = {}
            for tid,row in years[year].items():
                if tid not in prev:
                    cur[tid] = raw_level(float(row['score']))
                    continue
                cur[tid] = hysteresis_level(float(row['score']), prev[tid], margin_fn(row))
            labels[year] = cur
        strategies[name] = {'labels': labels}

    # EWMA alternatives are evaluated only as diagnostics. They alter the value
    # used to band and therefore are a stronger intervention than hysteresis.
    for alpha in (0.8, 0.7, 0.6):
        name = f'ewma_{int(alpha*100)}'
        band_scores = {2022: {i: float(r['score']) for i,r in years[2022].items()}}
        labels = {2022: {i: raw_level(s) for i,s in band_scores[2022].items()}}
        for year in (2023, 2024, 2025):
            bs = {}
            for tid,row in years[year].items():
                score = float(row['score'])
                prev = band_scores[year-1].get(tid, score)
                bs[tid] = alpha*score + (1-alpha)*prev
            band_scores[year] = bs
            labels[year] = {i: raw_level(s) for i,s in bs.items()}
        strategies[name] = {'labels': labels, 'band_scores': band_scores}

    raw = {
        '2023->2024': churn(raw_labels[2023], raw_labels[2024]),
        '2024->2025': churn(raw_labels[2024], raw_labels[2025]),
    }
    raw['mean_churn_pct'] = round(statistics.mean([raw[k]['churn_pct'] for k in ('2023->2024','2024->2025')]),2)

    result = {
        'candidate_version': next(iter(years[2025].values())).get('score_version'),
        'status': 'diagnostic_only',
        'production_replaced': False,
        'thresholds': {'Bajo':26.61,'Medio':45.43,'Alto':61.89,'Muy alto':71.12},
        'raw_banding': raw,
        'strategies': {},
    }

    for name,obj in strategies.items():
        labels = obj['labels']
        y23 = churn(labels[2023], labels[2024])
        y24 = churn(labels[2024], labels[2025])
        ids25 = sorted(set(labels[2025]) & set(raw_labels[2025]) & set(v1))
        diff_raw = sum(labels[2025][i] != raw_labels[2025][i] for i in ids25)
        agree_v1 = sum(labels[2025][i] == v1[i]['level'] for i in ids25)
        counts25 = Counter(labels[2025].values())

        # Responsiveness diagnostics using raw score moves 2024->2025.
        ids_yoy = sorted(set(years[2024]) & set(years[2025]))
        raw_changed = [i for i in ids_yoy if raw_labels[2024][i] != raw_labels[2025][i]]
        large = [i for i in raw_changed if abs(float(years[2025][i]['score']) - float(years[2024][i]['score'])) >= 10]
        small = [i for i in raw_changed if abs(float(years[2025][i]['score']) - float(years[2024][i]['score'])) < 5]
        changed_strategy = {i for i in ids_yoy if labels[2024][i] != labels[2025][i]}
        large_captured = sum(i in changed_strategy for i in large)
        small_suppressed = sum(i not in changed_strategy for i in small)

        item = {
            '2023->2024': y23,
            '2024->2025': y24,
            'mean_churn_pct': round(statistics.mean([y23['churn_pct'], y24['churn_pct']]),2),
            '2025_differs_from_raw_band': diff_raw,
            '2025_agreement_with_v1_pct': round(100*agree_v1/len(ids25),2),
            '2025_level_counts': {lv: counts25.get(lv,0) for lv in LEVELS},
            'large_raw_band_moves_2024_2025': len(large),
            'large_moves_captured': large_captured,
            'large_move_capture_pct': round(100*large_captured/len(large),2) if large else None,
            'small_raw_band_moves_2024_2025': len(small),
            'small_moves_suppressed': small_suppressed,
            'small_move_suppression_pct': round(100*small_suppressed/len(small),2) if small else None,
        }
        if 'band_scores' in obj:
            bs = obj['band_scores'][2025]
            common = sorted(set(bs)&set(years[2025]))
            item['2025_band_score_vs_raw_score_corr'] = round(corr([bs[i] for i in common],[float(years[2025][i]['score']) for i in common]),4)
            item['2025_mean_abs_band_score_lag'] = round(statistics.mean(abs(bs[i]-float(years[2025][i]['score'])) for i in common),2)
        result['strategies'][name] = item

    # Decision ranking: preserve all large movements first, then minimize churn,
    # then minimize divergence from the raw 2025 classification.
    candidates = []
    for name,item in result['strategies'].items():
        penalty = (100-(item['large_move_capture_pct'] or 0))*10 + item['mean_churn_pct'] + item['2025_differs_from_raw_band']*0.05
        candidates.append((penalty,name))
    candidates.sort()
    result['diagnostic_preference'] = candidates[0][1]
    result['diagnostic_preference_note'] = (
        'Preference is diagnostic only: preserve large annual movements first, then reduce band churn. '
        'No banding rule is promoted automatically.'
    )

    ANALYSIS.mkdir(exist_ok=True)
    (ANALYSIS/'igr_v11_candidate3_band_stability_strategies.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
