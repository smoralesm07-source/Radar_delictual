from __future__ import annotations

import re
import sys
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ENDPOINTS = [
    "https://cead.minsegpublica.gob.cl/wp-content/themes/gobcl-wp-master/data/get_estadisticas_delictuales.php",
    "https://cead.spd.gov.cl/wp-content/themes/gobcl-wp-master/data/get_estadisticas_delictuales.php",
]

MONTHS = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]


def payload(year: int = 2025, commune: str = "1101") -> list[tuple[str, str]]:
    data: list[tuple[str, str]] = [
        ("medida", "1"),
        ("tipoVal", "1,2"),
        ("anio[]", str(year)),
    ]
    data += [("trimestre[]", str(q)) for q in (4, 3, 2, 1)]
    data += [("mes[]", str(m)) for m, _ in MONTHS]
    data += [("mes_nombres[]", name) for _, name in MONTHS]
    data += [
        ("comuna[]", commune),
        ("familia[]", "4"),
        ("familia_nombres[]", "Delitos asociados a drogas"),
        ("grupo[]", "401"),
        ("grupo_nombres[]", "Crímenes y simples delitos ley de drogas"),
        ("subgrupo[]", "40101"),
        ("subgrupo[]", "40102"),
        ("subgrupo[]", "40103"),
        ("subgrupo[]", "40104"),
        ("subgrupo_nombres[]", "Tráfico de sustancias"),
        ("subgrupo_nombres[]", "Microtráfico de sustancias"),
        ("subgrupo_nombres[]", "Elaboración o producción de sustancias"),
        ("subgrupo_nombres[]", "Otras infracciones a la ley de drogas"),
        ("seleccion", "2"),
        ("descarga", "false"),
    ]
    return data


def inspect_response(response: requests.Response) -> dict:
    text = response.text or ""
    tables = BeautifulSoup(text, "html.parser").find_all("table") if text else []
    lowered = text.lower()
    return {
        "status": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "bytes": len(response.content),
        "tables": len(tables),
        "has_drug_label": "drog" in lowered,
        "has_month": "enero" in lowered or "diciembre" in lowered,
        "cloudflare": "cloudflare" in lowered,
        "preview": re.sub(r"\s+", " ", text[:180]).strip(),
    }


def main() -> int:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RadarDelictual/0.4; +https://github.com/smoralesm07-source/Radar_delictual)",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "text/html, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }
    any_success = False
    for endpoint in ENDPOINTS:
        headers["Referer"] = f"{urlparse(endpoint).scheme}://{urlparse(endpoint).netloc}/estadisticas-delictuales/"
        try:
            r = requests.post(endpoint, data=payload(), headers=headers, timeout=35, allow_redirects=True)
            info = inspect_response(r)
            ok = r.ok and info["tables"] > 0 and info["has_month"]
            any_success = any_success or ok
            print({"endpoint": endpoint, "ok": ok, **info})
        except Exception as exc:
            print({"endpoint": endpoint, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    # Diagnóstico no bloqueante: el pipeline v0.4 tendrá fallback explícito.
    print({"cead_direct_probe_success": any_success})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
