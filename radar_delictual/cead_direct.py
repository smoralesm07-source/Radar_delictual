from __future__ import annotations

from datetime import datetime, timezone

import requests

MANIFEST_URL = "https://raw.githubusercontent.com/smoralesm07-source/CEAD-Data-Pipeline/data/data/processed/manifest.json"
PRODUCER_REPO = "smoralesm07-source/CEAD-Data-Pipeline"


def probe_cead_direct(year: int | None = None, commune_code: str = "01101") -> dict:
    """Compatibilidad v0.5: la adquisición CEAD está externalizada.

    Radar Delictual no consulta el endpoint CEAD. Lee el estado de la sonda publicado
    por CEAD-Data-Pipeline y fuerza `ok=False` para impedir cualquier refresco directo.
    """
    started = datetime.now(timezone.utc).isoformat()
    try:
        r = requests.get(MANIFEST_URL, headers={"User-Agent": "RadarDelictual/0.5 CEAD-consumer"}, timeout=20)
        r.raise_for_status()
        upstream = (r.json().get("primary_probe") or {})
        return {
            "source_id": "cead_primary_externalized",
            "retrieved_at": started,
            "ok": False,
            "externalized": True,
            "producer_repo": PRODUCER_REPO,
            "upstream_primary_available": bool(upstream.get("ok")),
            "upstream_primary_status": upstream,
            "latest_nonzero_period": None,
            "note": "La adquisición primaria CEAD pertenece a CEAD-Data-Pipeline; Radar Delictual solo consume su dataset publicado.",
        }
    except Exception as exc:
        return {
            "source_id": "cead_primary_externalized",
            "retrieved_at": started,
            "ok": False,
            "externalized": True,
            "producer_repo": PRODUCER_REPO,
            "latest_nonzero_period": None,
            "error": f"{type(exc).__name__}: {exc}",
            "note": "No se ejecuta POST a CEAD desde Radar Delictual.",
        }


def collect_direct_year(year: int, communes, min_pause: float = 0.45):
    """Deshabilitado en Radar Delictual desde v0.5."""
    return [], [{
        "source_id": "cead_direct_disabled_in_radar",
        "ok": True,
        "executed": False,
        "year": int(year),
        "note": "Extracción directa externalizada a CEAD-Data-Pipeline.",
    }]


def annualize_direct(rows: list[dict]) -> list[dict]:
    return []
