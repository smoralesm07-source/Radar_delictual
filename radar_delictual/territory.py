from __future__ import annotations

import re
import unicodedata

from .config import RAW_DIR
from .homicides import parse_cut_workbook


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").lower()
    value = value.replace("’", "'").replace("`", "'")
    return re.sub(r"[^a-z0-9']+", " ", value).strip()


def canonical_commune_code(value: object) -> str | None:
    text = re.sub(r"\D", "", str(value or ""))
    if not text or len(text) > 5:
        return None
    code = text.zfill(5)
    return code if len(code) == 5 and code.isdigit() else None


def commune_territory_id(value: object) -> str | None:
    code = canonical_commune_code(value)
    return f"CL-COM-{code}" if code else None


def attach_cut_codes(records: list[dict], cut_map: dict[str, dict] | None = None) -> tuple[list[dict], dict]:
    """Añade CUT comunal sin convertir fallas de join en ceros.

    El identificador interoperable se deriva siempre del código oficial y usa
    `CL-COM-{CUT}`. Los nombres quedan como atributos descriptivos, nunca como clave.
    """
    if cut_map is None:
        path = RAW_DIR / "CUT_2018_v04.xls"
        if not path.exists():
            return records, {
                "source_id": "cead_cut_join",
                "ok": False,
                "matched_communes": 0,
                "note": "CUT no disponible en runtime; no se inventa una clave territorial."
            }
        try:
            cut_map = parse_cut_workbook(path)
        except Exception as exc:
            return records, {
                "source_id": "cead_cut_join",
                "ok": False,
                "matched_communes": 0,
                "error": f"{type(exc).__name__}: {exc}",
                "note": "No se alteran los registros ante falla de normalización territorial."
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
        code = canonical_commune_code(match.get("commune_code"))
        region_code = str(record.get("region_code", "")).zfill(2)
        if not code or (region_code and code[:2] != region_code):
            region_mismatch.add(key)
            record.setdefault("territory_key_status", "cut_region_mismatch")
            continue
        record["commune_code"] = code
        record["territory_id"] = commune_territory_id(code)
        record["territory_key_status"] = "official_cut"
        record["territory_mapping_method"] = "CODE_EXACT"
        record["territory_mapping_confidence"] = 1.0
        matched.add(code)

    unique_input = {_norm(r["commune_name"]) for r in records if r.get("territory_level") == "commune" and r.get("commune_name")}
    status = {
        "source_id": "cead_cut_join",
        "ok": len(matched) >= 340 and not region_mismatch,
        "input_communes": len(unique_input),
        "matched_communes": len(matched),
        "unmatched_communes": len(unmatched),
        "region_mismatches": len(region_mismatch),
        "territory_id_format": "CL-COM-{CUT}",
        "note": "Join por nombre normalizado con validación de código regional; la clave final siempre se deriva del CUT oficial."
    }
    return records, status
