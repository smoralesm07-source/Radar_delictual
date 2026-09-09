from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

PROCESSED = Path('data/processed')
ANALYSIS = Path('analysis')

ORDER = {'Muy bajo': 0, 'Bajo': 1, 'Medio': 2, 'Alto': 3, 'Muy alto': 4}


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> None:
    v1 = load(PROCESSED / 'cead_geographic_score_v1.json')
    c3 = load(PROCESSED / 'cead_geographic_score_v11_candidate.json')
    diag = load(ANALYSIS / 'igr_v11_candidate3_diagnostics.json')
    thresholds = diag['provisional_calibration']['thresholds']
    t25 = float(thresholds['25']['candidate_threshold'])
    t45 = float(thresholds['45']['candidate_threshold'])
    t65 = float(thresholds['65']['candidate_threshold'])
    t80 = float(thresholds['80']['candidate_threshold'])

    def calibrated_level(score: float) -> tuple[str, float]:
        if score >= t80:
            return 'Muy alto', score - t80
        if score >= t65:
            return 'Alto', min(score - t65, t80 - score)
        if score >= t45:
            return 'Medio', min(score - t45, t65 - score)
        if score >= t25:
            return 'Bajo', min(score - t25, t45 - score)
        return 'Muy bajo', t25 - score

    v1m = {r['territory_id']: r for r in v1}
    c3m = {r['territory_id']: r for r in c3}
    ids = sorted(set(v1m) & set(c3m))
    changes = []
    transitions = Counter()
    calibrated_counts = Counter()

    for tid in ids:
        old = v1m[tid]
        new = c3m[tid]
        score = float(new['score'])
        old_level = old['level']
        new_level, boundary_distance = calibrated_level(score)
        calibrated_counts[new_level] += 1
        transitions[f'{old_level} -> {new_level}'] += 1
        if old_level == new_level:
            continue
        step = ORDER[new_level] - ORDER[old_level]
        sd = float(new.get('stability_sd') or 0)
        uncertainty = max(sd, 0.5)
        pop = int(new.get('population') or 0)
        confidence = float(new.get('confidence') or 0)
        flags = []
        if abs(boundary_distance) <= uncertainty:
            flags.append('borderline_estabilidad')
        if step > 0 and pop < 25000:
            flags.append('upgrade_poblacion_pequena')
        if confidence >= 80:
            flags.append('confianza_alta')
        elif confidence < 75:
            flags.append('confianza_moderada_baja')
        if abs(step) > 1:
            flags.append('salto_multiple')
        changes.append({
            'territory_id': tid,
            'commune_name': new.get('commune_name'),
            'region_name': new.get('region_name'),
            'v1_level': old_level,
            'candidate3_calibrated_level': new_level,
            'band_step': step,
            'v1_score': round(float(old['score']), 2),
            'candidate3_score': round(score, 2),
            'score_delta': round(score - float(old['score']), 2),
            'candidate_confidence': round(confidence, 1),
            'population': pop,
            'stability_sd': round(sd, 3),
            'distance_to_nearest_calibrated_boundary': round(abs(boundary_distance), 2),
            'flags': flags,
        })

    upgrades = [r for r in changes if r['band_step'] > 0]
    downgrades = [r for r in changes if r['band_step'] < 0]
    borderline = [r for r in changes if 'borderline_estabilidad' in r['flags']]
    small_upgrades = [r for r in upgrades if r['population'] < 25000]
    multi = [r for r in changes if abs(r['band_step']) > 1]

    result = {
        'candidate_version': c3[0].get('score_version') if c3 else None,
        'status': 'diagnostic_only',
        'production_replaced': False,
        'thresholds': {'Muy alto': t80, 'Alto': t65, 'Medio': t45, 'Bajo': t25},
        'summary': {
            'matched_communes': len(ids),
            'changed_level': len(changes),
            'unchanged_level': len(ids) - len(changes),
            'agreement_pct': round(100 * (len(ids) - len(changes)) / len(ids), 2),
            'upgrades': len(upgrades),
            'downgrades': len(downgrades),
            'borderline_changes': len(borderline),
            'small_population_upgrades': len(small_upgrades),
            'multi_band_jumps': len(multi),
            'high_confidence_changes': sum('confianza_alta' in r['flags'] for r in changes),
        },
        'calibrated_level_counts': dict(calibrated_counts),
        'transition_matrix': dict(sorted(transitions.items())),
        'small_population_upgrades': sorted(small_upgrades, key=lambda r: r['population']),
        'borderline_changes': sorted(borderline, key=lambda r: r['distance_to_nearest_calibrated_boundary']),
        'multi_band_jumps': sorted(multi, key=lambda r: abs(r['band_step']), reverse=True),
        'all_changes': sorted(changes, key=lambda r: abs(r['score_delta']), reverse=True),
        'interpretation': (
            'Las bandas son una calibración provisional para comparar continuidad de lectura con v1.0. '
            'No convierten el candidato en clasificación oficial ni atribuyen riesgo a entidades o personas.'
        ),
    }
    out = ANALYSIS / 'igr_v11_candidate3_calibrated_changes.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
