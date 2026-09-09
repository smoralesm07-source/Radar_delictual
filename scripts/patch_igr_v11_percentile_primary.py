from __future__ import annotations

import json
from pathlib import Path

CFG = Path('config/cead_geographic_score_v11_candidate.json')
CODE = Path('radar_delictual/geographic_score_v11.py')
TEST = Path('tests/test_geographic_score_v11_rc1.py')


def patch_config() -> None:
    cfg = json.loads(CFG.read_text(encoding='utf-8'))
    if cfg.get('version') != '1.1.0-rc.1':
        raise RuntimeError(f"Versión inesperada: {cfg.get('version')}")

    rc1 = cfg.setdefault('rc1_policy', {})
    rc1['bands_status'] = 'secondary_context'
    rc1['full_replacement_status'] = 'ready_pending_explicit_promotion'
    rc1['band_strategy_validation'] = {
        'fixed_thresholds_mean_churn_pct': 38.12,
        'one_point_hysteresis_mean_churn_pct': 33.05,
        'relative_rank_bands_mean_churn_pct': 37.53,
        'decision': 'PROMOTE_SCORE_PERCENTILE_PRIMARY_KEEP_BAND_SECONDARY',
        'note': (
            'La histéresis reduce churn pero introduce dependencia del estado previo; '
            'las bandas relativas casi no reducen churn y pueden moverse en dirección opuesta al score. '
            'Se recomienda score continuo + percentil nacional como lectura primaria.'
        ),
    }
    cfg['presentation_policy'] = {
        'status': 'rc1_primary_reading',
        'primary_outputs': ['score', 'national_percentile'],
        'secondary_outputs': ['provisional_level', 'confidence', 'provisional_boundary_status'],
        'national_percentile_formula': (
            'Percentil nacional derivado del orden por score RC1; 100 = posición superior del universo comunal observado, '
            '0 = posición inferior. Empates comparten percentil mediante rango promedio.'
        ),
        'band_role': 'secondary_context',
        'band_warning': 'La banda no sustituye al score ni al percentil; cerca de una frontera debe privilegiarse la lectura continua.',
    }
    cfg['level_policy']['mode'] = 'score_percentile_primary_band_secondary'
    cfg['level_policy']['provisional_candidate3']['role'] = 'secondary_context'
    cfg['level_policy']['note'] = (
        'El score continuo y el percentil nacional son las salidas primarias de lectura RC1. '
        'El campo level conserva 25/45/65/80 sólo para comparar con v1.0. provisional_level usa los cortes '
        'recalibrados y queda como contexto secundario, con alerta de frontera.'
    )
    cfg['methodology']['level_calibration'] = (
        'La evaluación 2023-2025 comparó umbrales fijos, histéresis y bandas relativas. Ninguna alternativa categórica '
        'mejoró suficientemente la estabilidad sin introducir dependencia temporal o relatividad. Por ello el score continuo '
        'y el percentil nacional pasan a ser la lectura primaria RC1; la banda queda como apoyo secundario.'
    )
    cfg['methodology']['interpretation'] = (
        'IGR v1.1 RC1 en validación final. El score está congelado respecto de candidate.3 y la confianza ya fue corregida. '
        'La lectura primaria recomendada es score + percentil nacional; la banda es secundaria. Aún no sustituye el IGR v1.0 '
        'vigente hasta la promoción explícita del release.'
    )
    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def patch_code() -> None:
    text = CODE.read_text(encoding='utf-8')
    anchor = '''        else:\n            row["provisional_boundary_distance"] = None\n            row["provisional_boundary_status"] = "unavailable"\n\n    return rows\n'''
    replacement = '''        else:\n            row["provisional_boundary_distance"] = None\n            row["provisional_boundary_status"] = "unavailable"\n\n    # Lectura primaria RC1: el score conserva magnitud absoluta y el percentil\n    # agrega posición relativa nacional sin introducir otra fórmula de amenaza.\n    # Los empates reciben el mismo percentil mediante rango promedio.\n    scored = [row for row in rows if row.get("score") is not None]\n    values = [float(row["score"]) for row in scored]\n    n_scored = len(scored)\n    for row in scored:\n        value = float(row["score"])\n        higher = sum(v > value for v in values)\n        equal = sum(v == value for v in values)\n        average_rank = higher + (equal + 1.0) / 2.0\n        row["national_rank"] = higher + 1\n        row["national_rank_ties"] = equal\n        row["national_percentile"] = (\n            round(100.0 * (n_scored - average_rank) / (n_scored - 1), 1)\n            if n_scored > 1 else 100.0\n        )\n        row["primary_reading"] = "score_plus_national_percentile"\n\n    return rows\n'''
    if 'row["national_percentile"]' not in text:
        if anchor not in text:
            raise RuntimeError('No se encontró el cierre esperado de build_cead_geographic_score_v11_candidate')
        text = text.replace(anchor, replacement, 1)
    CODE.write_text(text, encoding='utf-8')


def patch_tests() -> None:
    text = TEST.read_text(encoding='utf-8')
    old = '''    assert cfg["rc1_policy"]["score_formula_frozen"] is True\n'''
    new = '''    assert cfg["rc1_policy"]["score_formula_frozen"] is True\n    assert cfg["presentation_policy"]["primary_outputs"] == ["score", "national_percentile"]\n    assert cfg["presentation_policy"]["band_role"] == "secondary_context"\n'''
    if new not in text:
        if old not in text:
            raise RuntimeError('No se encontró aserción RC1 esperada')
        text = text.replace(old, new, 1)

    if 'def test_rc1_exposes_national_rank_and_percentile_as_primary_context():' not in text:
        text = text.rstrip() + r'''


def test_rc1_exposes_national_rank_and_percentile_as_primary_context():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, 100),
            row("13102", year, 30),
            row("13103", year, 5),
        ]

    scores = build_cead_geographic_score_v11_candidate(
        master,
        {"13101": 100000, "13102": 100000, "13103": 100000},
    )
    ordered = sorted(scores, key=lambda item: float(item["score"]), reverse=True)

    assert ordered[0]["national_rank"] == 1
    assert ordered[0]["national_percentile"] == 100.0
    assert ordered[-1]["national_percentile"] == 0.0
    assert all(0.0 <= float(item["national_percentile"]) <= 100.0 for item in scores)
    assert all(item["primary_reading"] == "score_plus_national_percentile" for item in scores)
'''
    TEST.write_text(text.rstrip() + '\n', encoding='utf-8')


if __name__ == '__main__':
    patch_config()
    patch_code()
    patch_tests()
