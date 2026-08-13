from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from .config import RAW_DIR, TIMEOUT_SECONDS, USER_AGENT
from .sources import MP_ANNUAL_URLS

REGION_MAP = {
    "I": ("01", "Tarapacá"), "II": ("02", "Antofagasta"), "III": ("03", "Atacama"),
    "IV": ("04", "Coquimbo"), "V": ("05", "Valparaíso"), "VI": ("06", "Libertador General Bernardo O'Higgins"),
    "VII": ("07", "Maule"), "VIII": ("08", "Biobío"), "IX": ("09", "La Araucanía"), "X": ("10", "Los Lagos"),
    "XI": ("11", "Aysén del General Carlos Ibáñez del Campo"), "XII": ("12", "Magallanes y de la Antártica Chilena"),
    "RM CN": ("13", "Metropolitana de Santiago"), "RM OR": ("13", "Metropolitana de Santiago"),
    "RM OCC": ("13", "Metropolitana de Santiago"), "RM SUR": ("13", "Metropolitana de Santiago"),
    "XIV": ("14", "Los Ríos"), "XV": ("15", "Arica y Parinacota"), "XVI": ("16", "Ñuble")
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_mp_workbook(year: int) -> tuple[Path, dict]:
    url = MP_ANNUAL_URLS[year]
    suffix = ".xlsx" if url.lower().endswith("xlsx") else ".xls"
    path = RAW_DIR / f"ministerio_publico_{year}{suffix}"
    r = requests.get(url, timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    path.write_bytes(r.content)
    evidence = {"evidence_id":f"mp:{year}:annual","source_id":"ministerio_publico_estadisticas","year":year,"url":url,"retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":_sha256(path),"bytes":path.stat().st_size,"observation_unit":"delitos_ingresados_en_SAF"}
    return path, evidence


def _find_table_sheet(path: Path, known: bool) -> str:
    xls = pd.ExcelFile(path)
    preferred = "TB3.1" if known else "TB3.2"
    if preferred in xls.sheet_names:
        return preferred
    needle = "IMPUTADOS CONOCIDOS" if known else "IMPUTADOS DESCONOCIDOS"
    for sheet in xls.sheet_names:
        try:
            sample = pd.read_excel(path, sheet_name=sheet, header=None, nrows=15)
            text = " ".join(sample.astype(str).fillna("").values.flatten()).upper()
            if needle in text and "CATEGORÍA DE DELITOS" in text:
                return sheet
        except Exception:
            continue
    raise ValueError(f"No se encontró tabla regional {'IC' if known else 'ID'} en {path.name}")


def _parse_regional_sheet(path: Path, sheet: str, year: int, known: bool) -> list[dict]:
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    header_row = category_col = None
    for i in range(min(50, len(df))):
        for j, value in enumerate(df.iloc[i].tolist()):
            if isinstance(value, str) and " ".join(value.upper().split()) == "CATEGORÍA DE DELITOS":
                header_row, category_col = i, j
                break
        if header_row is not None:
            break
    if header_row is None or category_col is None:
        raise ValueError(f"No se encontró encabezado de categorías en {sheet}")
    headers = df.iloc[header_row].tolist()
    region_cols = {}
    for col, value in enumerate(headers):
        key = str(value).strip() if pd.notna(value) else ""
        if key in REGION_MAP:
            region_cols[col] = key
    rows = []
    for r in range(header_row + 1, len(df)):
        category = df.iat[r, category_col]
        if not isinstance(category, str):
            continue
        category = " ".join(category.upper().split())
        if category == "TOTAL NACIONAL":
            break
        if category in {"CATEGORÍA DE DELITOS", "NAN"}:
            continue
        for col, prosecutor_region in region_cols.items():
            value = pd.to_numeric(df.iat[r, col], errors="coerce")
            if pd.isna(value):
                continue
            region_code, region_name = REGION_MAP[prosecutor_region]
            rows.append({"year":year,"region_code":region_code,"region_name":region_name,"prosecutor_region":prosecutor_region,"crime_category":category,"known_status":"known" if known else "unknown","value":int(value)})
    if not rows:
        raise ValueError(f"Tabla {sheet} sin datos regionales reconocibles")
    return rows


def parse_mp_workbook(path: Path, year: int) -> list[dict]:
    known_sheet = _find_table_sheet(path, True)
    unknown_sheet = _find_table_sheet(path, False)
    raw = _parse_regional_sheet(path, known_sheet, year, True) + _parse_regional_sheet(path, unknown_sheet, year, False)
    df = pd.DataFrame(raw)
    grouped = df.groupby(["year","region_code","region_name","crime_category"], as_index=False)["value"].sum()
    records = []
    for row in grouped.to_dict("records"):
        row.update({"territory_level":"region","metric":"delitos_ingresados","rate_100k":None,"source_id":"ministerio_publico_estadisticas","source_year":year,"observation_unit":"delito_ingresado_en_SAF","data_status":"observed"})
        records.append(row)
    return records


def collect_mp_history(start_year: int = 2020, end_year: int = 2025) -> tuple[list[dict], list[dict], list[dict]]:
    all_records, evidence, status = [], [], []
    for year in range(start_year, end_year + 1):
        try:
            path, ev = download_mp_workbook(year)
            records = parse_mp_workbook(path, year)
            all_records.extend(records)
            evidence.append(ev)
            status.append({"source_id":"ministerio_publico_estadisticas","year":year,"ok":True,"records":len(records)})
        except Exception as exc:
            status.append({"source_id":"ministerio_publico_estadisticas","year":year,"ok":False,"error":f"{type(exc).__name__}: {exc}"})
    return all_records, evidence, status


def load_existing_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
