from __future__ import annotations

import re
import unicodedata

from .config import RAW_DIR
from .homicides import parse_cut_workbook


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").lower()
    value = value.replace("’", "'").replace("`", "'")
    return re.sub(r"[^a-z0-9']+", " ", value).strip()


def attach_cut_codes(records: list[dict], cut_map: dict[str, dict] | None = None) -> tuple[list[dict], dict]:
    """Añade CUT comunal a registros territoriales sin convertir fallas de join en ceros.

    Si `cut_map` no se entrega, reutiliza el CUT ya descargado por el colector
    interinstitucional. Se valida que los dos primeros dígitos del código comunal
    coincidan con la región del registro antes de aplicar el identificador oficial.
    """
    if cut_map is None:
        path = RAW_DIR / "CUT_2018_v04.xls"
        if not path.exists():
            return records, {
                "source_id": "cead_cut_join",
                "ok": False,
                "matched_communes": 0,
                "note": "CUT no disponible en runtime; se mantiene territory_id textual estable."
            }
        try:
            cut_map = parse_cut_workbook(path)
        except Exception as exc:
            return records, {
                "source_id": "cead_cut_join",
                "ok": False,
                "matched_communes": 0,
                "error": f"{type(exc).__name__}: {exc}",
                "note": "No se alteran los registros CEAD ante falla de normalización territorial."
            }

    matched: set[str] = set()
    region_mismatch: set[str] = set()
    unmatched: set[str] = set()

    for record in records:
        if record.get("territory_level") != "commune" or not record.get("commune_name"):
            continue
        key = _norm(record["commune_name"])
        match = cut_map.get(key)
        if not match:
            unmatched.add(key)
            record.setdefault("territory_key_status", "name_fallback")
            continue
        code = str(match.get("commune_code", "")).strip().zfill(5)
        region_code = str(record.get("region_code", "")).zfill(2)
        if len(code) != 5 or not code.isdigit() or (region_code and code[:2] != region_code):
            region_mismatch.add(key)
            record.setdefault("territory_key_status", "cut_region_mismatch")
            continue
        record["commune_code"] = code
        record["territory_id"] = f"CL-{code}"
        record["territory_key_status"] = "official_cut"
        matched.add(code)

    unique_input = {_norm(r["commune_name"]) for r in records if r.get("territory_level") == "commune" and r.get("commune_name")}
    status = {
        "source_id": "cead_cut_join",
        "ok": len(matched) >= 340 and not region_mismatch,
        "input_communes": len(unique_input),
        "matched_communes": len(matched),
        "unmatched_communes": len(unmatched),
        "region_mismatches": len(region_mismatch),
        "note": "Join CEAD→CUT por nombre normalizado con validación de código regional; no modifica métricas delictuales."
    }
    return records, status
