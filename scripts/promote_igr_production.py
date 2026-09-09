from __future__ import annotations

import json
from pathlib import Path

CFG = Path('config/cead_geographic_score_v11_candidate.json')
RUNTIME = Path('radar_delictual/geographic_score_v11_runtime.py')
TEST = Path('tests/test_geographic_score_v11_rc1.py')


def patch_config() -> None:
    cfg = json.loads(CFG.read_text(encoding='utf-8'))
    cfg['version'] = '1.1.0'
    cfg['status'] = 'production'
    cfg['name'] = 'Componente criminógeno CEAD · IGR'
    rc1 = cfg.setdefault('rc1_policy', {})
    rc1['full_replacement_status'] = 'promoted_to_production'
    rc1['promoted_at'] = '2026-09-09'
    presentation = cfg.setdefault('presentation_policy', {})
    presentation['status'] = 'production_primary_reading'
    presentation['primary_outputs'] = ['score', 'national_percentile']
    presentation['secondary_outputs'] = ['provisional_level', 'confidence', 'provisional_boundary_status']
    presentation['band_role'] = 'secondary_context'
    cfg['methodology']['interpretation'] = (
        'IGR vigente. La lectura primaria combina score continuo 0-100 y percentil nacional; '
        'la confianza informa robustez de la estimación y la banda es un apoyo secundario. '
        'El IGR describe amenaza territorial comunal y no se atribuye a entidades.'
    )
    cfg['level_policy']['note'] = (
        'El score continuo y el percentil nacional son las salidas primarias del IGR. '
        'La banda recalibrada queda como contexto secundario y no sustituye la lectura continua.'
    )
    CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def patch_runtime() -> None:
    text = RUNTIME.read_text(encoding='utf-8')
    if 'from .geographic_score import _integration_rows' not in text:
        text = text.replace(
            'from .geographic_score_runtime import normalize_quality_status\n',
            'from .geographic_score import _integration_rows\nfrom .geographic_score_runtime import normalize_quality_status\n',
            1,
        )

    old = '''    score_path = PROCESSED_DIR / "cead_geographic_score_v11_candidate.json"\n    methodology_path = PROCESSED_DIR / "cead_geographic_score_methodology_v11_candidate.json"\n    comparison_path = PROCESSED_DIR / "cead_geographic_score_v11_comparison.json"\n    score_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")\n    methodology_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")\n'''
    new = '''    score_path = PROCESSED_DIR / "cead_geographic_score_v11_candidate.json"\n    methodology_path = PROCESSED_DIR / "cead_geographic_score_methodology_v11_candidate.json"\n    production_score_path = PROCESSED_DIR / "cead_geographic_score.json"\n    production_methodology_path = PROCESSED_DIR / "cead_geographic_score_methodology.json"\n    comparison_path = PROCESSED_DIR / "cead_geographic_score_v11_comparison.json"\n    serialized_rows = json.dumps(rows, ensure_ascii=False, indent=2)\n    serialized_methodology = json.dumps(candidate, ensure_ascii=False, indent=2)\n    score_path.write_text(serialized_rows, encoding="utf-8")\n    methodology_path.write_text(serialized_methodology, encoding="utf-8")\n    production_score_path.write_text(serialized_rows, encoding="utf-8")\n    production_methodology_path.write_text(serialized_methodology, encoding="utf-8")\n'''
    if old not in text:
        raise RuntimeError('No se encontró bloque de materialización esperado')
    text = text.replace(old, new, 1)

    old = '''    comparison.update({\n        "candidate_version": candidate["version"],\n        "base_score_version": candidate["base_score_version"],\n        "population_source": population_meta,\n        "production_replaced": False,\n    })\n'''
    new = '''    comparison.update({\n        "candidate_version": candidate["version"],\n        "base_score_version": candidate["base_score_version"],\n        "population_source": population_meta,\n        "production_replaced": True,\n    })\n'''
    if old not in text:
        raise RuntimeError('No se encontró bloque de comparación esperado')
    text = text.replace(old, new, 1)

    old = '''    data_path = PUBLIC_DIR / "data.json"\n    if data_path.exists():\n        payload = json.loads(data_path.read_text(encoding="utf-8"))\n        # El candidato se publica como artefacto técnico de comparación, nunca\n        # bajo la clave del score vigente ni en integration_ready.\n        payload["cead_geographic_score_candidate"] = rows\n        payload["cead_geographic_score_candidate_methodology"] = candidate\n        payload["cead_geographic_score_candidate_comparison"] = comparison\n        data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")\n\n    confidences = [float(row["confidence"]) for row in rows if row.get("confidence") is not None]\n    return {\n        "ok": True,\n        "experimental": True,\n        "production_replaced": False,\n        "score_version": candidate["version"],\n        "records": len(rows),\n        "population_communes": len(population),\n        "confidence_min": min(confidences) if confidences else None,\n        "confidence_max": max(confidences) if confidences else None,\n        "comparison": comparison,\n        "output": str(score_path),\n    }\n'''
    new = '''    # La versión promovida reemplaza el artefacto histórico de producción al final\n    # de la corrida. Se conserva el archivo candidate como evidencia de transición.\n    legacy_score_path = PROCESSED_DIR / "cead_geographic_score_v1.json"\n    legacy_methodology_path = PROCESSED_DIR / "cead_geographic_score_methodology_v1.json"\n    legacy_score_path.write_text(serialized_rows, encoding="utf-8")\n    legacy_methodology_path.write_text(serialized_methodology, encoding="utf-8")\n\n    integration_path = PROCESSED_DIR / "integration_ready.json"\n    integration = json.loads(integration_path.read_text(encoding="utf-8")) if integration_path.exists() else []\n    integration = [\n        row for row in integration\n        if row.get("signal_family") != "cead_criminogenic_geographic_score"\n    ] + _integration_rows(rows)\n    integration_path.write_text(json.dumps(integration, ensure_ascii=False, indent=2), encoding="utf-8")\n\n    data_path = PUBLIC_DIR / "data.json"\n    if data_path.exists():\n        payload = json.loads(data_path.read_text(encoding="utf-8"))\n        payload["cead_geographic_score"] = rows\n        payload["cead_geographic_score_methodology"] = candidate\n        payload["cead_geographic_score_candidate"] = rows\n        payload["cead_geographic_score_candidate_methodology"] = candidate\n        payload["cead_geographic_score_candidate_comparison"] = comparison\n        payload["integration"] = integration\n        data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")\n\n    confidences = [float(row["confidence"]) for row in rows if row.get("confidence") is not None]\n    return {\n        "ok": True,\n        "experimental": False,\n        "production_replaced": True,\n        "score_version": candidate["version"],\n        "records": len(rows),\n        "population_communes": len(population),\n        "confidence_min": min(confidences) if confidences else None,\n        "confidence_max": max(confidences) if confidences else None,\n        "comparison": comparison,\n        "output": str(production_score_path),\n    }\n'''
    if old not in text:
        raise RuntimeError('No se encontró bloque final esperado')
    text = text.replace(old, new, 1)
    RUNTIME.write_text(text, encoding='utf-8')


def patch_test() -> None:
    text = TEST.read_text(encoding='utf-8')
    text = text.replace('assert cfg["version"] == "1.1.0-rc.1"', 'assert cfg["version"] == "1.1.0"')
    text = text.replace('assert cfg["status"] == "release_candidate"', 'assert cfg["status"] == "production"')
    if 'assert cfg["rc1_policy"]["full_replacement_status"] == "promoted_to_production"' not in text:
        needle = '    assert cfg["rc1_policy"]["score_formula_frozen"] is True\n'
        text = text.replace(needle, needle + '    assert cfg["rc1_policy"]["full_replacement_status"] == "promoted_to_production"\n', 1)
    TEST.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    patch_config()
    patch_runtime()
    patch_test()
