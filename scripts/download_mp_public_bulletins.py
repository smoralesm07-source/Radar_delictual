from __future__ import annotations

import hashlib
import json
from pathlib import Path

import requests

OUT = Path("artifacts/mp_public_bulletins")
OUT.mkdir(parents=True, exist_ok=True)

FILES = [
    (2025, "annual", "mp_2025_anual.xlsx", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Bolet%C3%ADn_Anual_2025-20260101_v1.xlsx"),
    (2025, "q3", "mp_2025_ene_sep.xlsx", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Bolet%C3%ADn_institucional_enero_septiembre_2025.xlsx"),
    (2025, "h1", "mp_2025_ene_jun.xlsx", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_junio_2025_20250703_v1.xlsx"),
    (2025, "q1", "mp_2025_ene_mar.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_enero_marzo_2025v1.xls"),
    (2024, "annual", "mp_2024_anual.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_Anual__2024.xls"),
    (2024, "h1", "mp_2024_ene_jun.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_junio_2024..xls"),
    (2024, "q1", "mp_2024_ene_mar.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_marzo_2024.xls"),
    (2023, "annual", "mp_2023_anual.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_Anual_enero_diciembre_2023.xls"),
    (2023, "q3", "mp_2023_ene_sep.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_enero_septiembre_2023.xls"),
    (2023, "h1", "mp_2023_ene_jun.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_enero_junio_2023_2023_v1.xls"),
    (2023, "q1", "mp_2023_ene_mar.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_marzo_2023_20230407_v1.xls"),
    (2022, "annual", "mp_2022_anual.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/BoletIn_Anual_202220.xls"),
    (2022, "q3", "mp_2022_ene_sep.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_septiembre_2022.xls"),
    (2022, "h1", "mp_2022_ene_jun.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_junio_2022.xls"),
    (2022, "q1", "mp_2022_ene_mar.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_marzo_2022.xls"),
    (2021, "annual", "mp_2021_anual.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_anual_enero_diciembre_2021.xls"),
    (2021, "q3", "mp_2021_ene_sep.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_septiembre_2021.xls"),
    (2021, "h1", "mp_2021_ene_jun.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_junio_2021.xls"),
    (2021, "q1", "mp_2021_ene_mar.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/boletin_enero_marzo_2021.xls"),
    (2020, "annual", "mp_2020_anual.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_diciembre_2020.xls"),
    (2020, "q3", "mp_2020_ene_sep.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_septiembre_2020.xls"),
    (2020, "h1", "mp_2020_ene_jun.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_semestral_enero_junio_2020.xls"),
    (2020, "q1", "mp_2020_ene_mar.xls", "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_marzo_2020_.xls"),
]

headers = {"User-Agent": "Mozilla/5.0 (compatible; RadarDelictual-Research/1.0; public-data research)"}
manifest = []
for year, period, filename, url in FILES:
    row = {"year": year, "period": period, "filename": filename, "url": url}
    try:
        r = requests.get(url, headers=headers, timeout=60)
        row.update({"http_status": r.status_code, "content_type": r.headers.get("content-type"), "bytes": len(r.content)})
        if r.ok and len(r.content) > 1024:
            path = OUT / filename
            path.write_bytes(r.content)
            row["sha256"] = hashlib.sha256(r.content).hexdigest()
            row["downloaded"] = True
        else:
            row["downloaded"] = False
            row["error"] = r.text[:200] if r.text else "empty_or_small_response"
    except Exception as exc:
        row.update({"downloaded": False, "error": f"{type(exc).__name__}: {exc}"})
    manifest.append(row)

(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"requested": len(manifest), "downloaded": sum(1 for x in manifest if x.get('downloaded')), "failed": sum(1 for x in manifest if not x.get('downloaded'))}, ensure_ascii=False))
