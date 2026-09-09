from __future__ import annotations

import json
from pathlib import Path

CFG = Path('config/cead_geographic_score_v11_candidate.json')
CODE = Path('radar_delictual/geographic_score_v11.py')
TEST = Path('tests/test_geographic_score_v11_candidate.py')


def patch_config() -> None:
    cfg = json.loads(CFG.read_text(encoding='utf-8'))
    if cfg.get('version') not in {'1.1.0-candidate.2', '1.1.0-candidate.3'}:
        raise RuntimeError(f"Versión inesperada: {cfg.get('version')}")
    cfg['version'] = '1.1.0-candidate.3'
    cfg['temporal_anomaly_reliability'] = {
        'method': 'event_support_shrinkage',
        'support_scale': 20,
        'formula': 'q = soporte/(soporte+20); anomalía_ajustada = 50 + q*(anomalía_cruda-50)',
        'note': (
            'El soporte es la suma de casos observados en la historia de la comuna más el corte actual. '
            'La contracción evita que variaciones de uno o pocos casos en series escasas dominen la anomalía.'
        ),
    }
    cfg['methodology']['temporal_anomaly'] = (
        'Separación robusta del valor actual respecto de la historia de la misma comuna, usando mediana y MAD. '
        'La anomalía cruda se contrae hacia 50 según soporte de eventos q=soporte/(soporte+20), para que cambios '
        'de uno o pocos casos en series escasas no generen saltos artificiales. Sustituye la anomalía transversal '
        'de v1.0 y mantiene intensidad y anomalía conceptualmente separadas.'
    )
    cfg['level_policy']['note'] = (
        'Los cortes 25/45/65/80 se conservan únicamente para comparar con v1.0. La calibración de bandas se '
        'estima después de estabilizar la anomalía temporal y permanece experimental hasta validación.'
    )
    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def patch_code() -> None:
    text = CODE.read_text(encoding='utf-8')
    old = '''    history = [float(series[(commune, y)]) for y in years if y < latest_year]\n    trend = _trend_score(current, history)\n    temporal_anomaly = _temporal_anomaly_score(history, current)\n'''
    new = '''    history = [float(series[(commune, y)]) for y in years if y < latest_year]\n    trend = _trend_score(current, history)\n    raw_temporal_anomaly = _temporal_anomaly_score(history, current)\n\n    # Una anomalía longitudinal puede ser matemáticamente grande con soporte\n    # mínimo (por ejemplo, pasar de 0 a 1 caso). Eso es informativo como cambio,\n    # pero no debe pesar igual que una ruptura sostenida sobre decenas de hechos.\n    # Contraemos sólo la anomalía hacia el punto neutro 50; intensidad,\n    # persistencia y tendencia permanecen intactas.\n    anomaly_cfg = candidate.get("temporal_anomaly_reliability", {})\n    support_scale = float(anomaly_cfg.get("support_scale", 20.0))\n    anomaly_support = sum(max(0.0, x) for x in history) + max(0.0, current)\n    anomaly_reliability = (\n        anomaly_support / (anomaly_support + support_scale)\n        if support_scale > 0 else 1.0\n    )\n    temporal_anomaly = round(\n        50.0 + anomaly_reliability * (raw_temporal_anomaly - 50.0),\n        2,\n    )\n'''
    if old in text:
        text = text.replace(old, new, 1)
    elif 'raw_temporal_anomaly = _temporal_anomaly_score(history, current)' not in text:
        raise RuntimeError('No se encontró el bloque de anomalía temporal esperado')

    old_return = '''        "trend": trend,\n        "temporal_anomaly": temporal_anomaly,\n        "years_observed": observed,\n'''
    new_return = '''        "trend": trend,\n        "temporal_anomaly": temporal_anomaly,\n        "temporal_anomaly_raw": raw_temporal_anomaly,\n        "temporal_anomaly_reliability": round(100.0 * anomaly_reliability, 1),\n        "temporal_anomaly_support": round(anomaly_support, 1),\n        "years_observed": observed,\n'''
    if old_return in text:
        text = text.replace(old_return, new_return, 1)
    elif '"temporal_anomaly_raw": raw_temporal_anomaly' not in text:
        raise RuntimeError('No se encontró el bloque de salida de anomalía esperado')
    CODE.write_text(text, encoding='utf-8')


def patch_tests() -> None:
    text = TEST.read_text(encoding='utf-8')
    marker = 'def test_sparse_temporal_anomaly_is_shrunk_toward_neutral():'
    if marker in text:
        return
    addition = r'''


def test_sparse_temporal_anomaly_is_shrunk_toward_neutral():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024):
        master += [
            row("13101", year, "Delitos asociados a drogas", 0),
            row("13102", year, "Delitos asociados a drogas", 0),
        ]
    master += [
        row("13101", 2025, "Delitos asociados a drogas", 1),
        row("13102", 2025, "Delitos asociados a drogas", 0),
    ]

    scores = build_cead_geographic_score_v11_candidate(
        master, {"13101": 5000, "13102": 5000}
    )
    by = {r["commune_code"]: r for r in scores}
    comp = by["13101"]["layers"]["predicate_direct"]["components"][0]

    assert comp["temporal_anomaly_raw"] > 50.0
    assert 50.0 < comp["temporal_anomaly"] < comp["temporal_anomaly_raw"]
    assert comp["temporal_anomaly_reliability"] < 10.0
    assert comp["temporal_anomaly_support"] == 1.0


def test_temporal_anomaly_retains_signal_when_event_support_is_substantial():
    master = []
    for year, value in zip((2020, 2021, 2022, 2023, 2024), (30, 31, 29, 30, 30)):
        master += [
            row("13101", year, "Delitos asociados a drogas", value),
            row("13102", year, "Delitos asociados a drogas", 10),
        ]
    master += [
        row("13101", 2025, "Delitos asociados a drogas", 60),
        row("13102", 2025, "Delitos asociados a drogas", 10),
    ]

    scores = build_cead_geographic_score_v11_candidate(
        master, {"13101": 100000, "13102": 100000}
    )
    by = {r["commune_code"]: r for r in scores}
    comp = by["13101"]["layers"]["predicate_direct"]["components"][0]

    assert comp["temporal_anomaly_raw"] > 50.0
    assert comp["temporal_anomaly"] > 50.0
    assert comp["temporal_anomaly_reliability"] > 90.0
    assert abs(comp["temporal_anomaly"] - comp["temporal_anomaly_raw"]) < 6.0
'''
    TEST.write_text((text.rstrip() + addition).rstrip() + '\n', encoding='utf-8')


if __name__ == '__main__':
    patch_config()
    patch_code()
    patch_tests()
