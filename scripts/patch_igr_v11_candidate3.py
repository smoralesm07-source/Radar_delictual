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

    helper_anchor = '''def _level(score: float | None) -> str | None:\n    # Legado v1.0: solo para comparar. El candidato no promueve estas bandas.\n    if score is None:\n        return None\n    return "Muy alto" if score >= 80 else "Alto" if score >= 65 else "Medio" if score >= 45 else "Bajo" if score >= 25 else "Muy bajo"\n\n\n'''
    helper_new = helper_anchor + '''def _provisional_level(score: float | None, candidate: dict) -> str | None:\n    """Banda candidate.3 calibrada; sigue siendo sólo diagnóstica."""\n    if score is None:\n        return None\n    policy = (candidate.get("level_policy") or {}).get("provisional_candidate3") or {}\n    thresholds = policy.get("thresholds") or {}\n    try:\n        low = float(thresholds["bajo_min"])\n        medium = float(thresholds["medio_min"])\n        high = float(thresholds["alto_min"])\n        very_high = float(thresholds["muy_alto_min"])\n    except (KeyError, TypeError, ValueError):\n        return None\n    value = float(score)\n    return (\n        "Muy alto" if value >= very_high\n        else "Alto" if value >= high\n        else "Medio" if value >= medium\n        else "Bajo" if value >= low\n        else "Muy bajo"\n    )\n\n\n'''
    if 'def _provisional_level(' not in text:
        if helper_anchor not in text:
            raise RuntimeError('No se encontró _level para insertar banda provisional')
        text = text.replace(helper_anchor, helper_new, 1)

    finalize_anchor = '''        row["confidence_level"] = (\n            "Alta" if confidence >= float(bands["high_min"])\n            else "Media" if confidence >= float(bands["medium_min"])\n            else "Baja"\n        )\n\n    return rows\n'''
    finalize_new = '''        row["confidence_level"] = (\n            "Alta" if confidence >= float(bands["high_min"])\n            else "Media" if confidence >= float(bands["medium_min"])\n            else "Baja"\n        )\n\n        # La banda recalibrada se publica como segundo diagnóstico, nunca como\n        # reemplazo del level legado ni como clasificación oficial. Además se\n        # explicita si el score está cerca de una frontera respecto de su propia\n        # inestabilidad leave-one-year-out.\n        provisional_policy = (candidate.get("level_policy") or {}).get("provisional_candidate3") or {}\n        row["provisional_level"] = _provisional_level(row.get("score"), candidate)\n        row["provisional_level_status"] = provisional_policy.get("status", "diagnostic_only")\n        thresholds = provisional_policy.get("thresholds") or {}\n        boundary_values = []\n        for key in ("bajo_min", "medio_min", "alto_min", "muy_alto_min"):\n            try:\n                boundary_values.append(float(thresholds[key]))\n            except (KeyError, TypeError, ValueError):\n                pass\n        if row.get("score") is not None and boundary_values:\n            distance = min(abs(float(row["score"]) - boundary) for boundary in boundary_values)\n            row["provisional_boundary_distance"] = round(distance, 2)\n            uncertainty = max(float(row.get("stability_sd") or 0.0), 0.5)\n            row["provisional_boundary_status"] = (\n                "borderline" if distance <= uncertainty\n                else "stable_relative_to_thresholds"\n            )\n        else:\n            row["provisional_boundary_distance"] = None\n            row["provisional_boundary_status"] = "unavailable"\n\n    return rows\n'''
    if 'row["provisional_level"] = _provisional_level' not in text:
        if finalize_anchor not in text:
            raise RuntimeError('No se encontró finalización de confianza para banda provisional')
        text = text.replace(finalize_anchor, finalize_new, 1)

    CODE.write_text(text, encoding='utf-8')


def patch_tests() -> None:
    text = TEST.read_text(encoding='utf-8')
    if 'def test_sparse_temporal_anomaly_is_shrunk_toward_neutral():' not in text:
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
        text = text.rstrip() + addition

    marker = 'def test_candidate_exposes_provisional_level_without_replacing_legacy_level():'
    if marker not in text:
        text = text.rstrip() + r'''


def test_candidate_exposes_provisional_level_without_replacing_legacy_level():
    master = []
    for year in (2020, 2021, 2022, 2023, 2024, 2025):
        master += [
            row("13101", year, "Delitos asociados a drogas", 100),
            row("13102", year, "Delitos asociados a drogas", 20),
            row("13103", year, "Delitos asociados a drogas", 5),
        ]
    scores = build_cead_geographic_score_v11_candidate(
        master, {"13101": 300000, "13102": 100000, "13103": 50000}
    )
    assert scores
    for item in scores:
        assert item["level_status"] == "comparison_only"
        assert item["provisional_level_status"] == "diagnostic_only"
        assert item["provisional_level"] in {"Muy bajo", "Bajo", "Medio", "Alto", "Muy alto"}
        assert item["provisional_boundary_status"] in {"borderline", "stable_relative_to_thresholds"}
        assert item["provisional_boundary_distance"] is not None
'''
    TEST.write_text(text.rstrip() + '\n', encoding='utf-8')


if __name__ == '__main__':
    patch_config()
    patch_code()
    patch_tests()
