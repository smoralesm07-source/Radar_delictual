from __future__ import annotations

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

MANIFEST_URL = "https://raw.githubusercontent.com/smoralesm07-source/CEAD-Data-Pipeline/data/data/processed/manifest.json"
PRODUCER_REPO = "smoralesm07-source/CEAD-Data-Pipeline"
MONTHS = [(1,"Enero"),(2,"Febrero"),(3,"Marzo"),(4,"Abril"),(5,"Mayo"),(6,"Junio"),(7,"Julio"),(8,"Agosto"),(9,"Septiembre"),(10,"Octubre"),(11,"Noviembre"),(12,"Diciembre")]
MONTH_LOOKUP = {name.lower(): number for number,name in MONTHS}


def drug_payload(year:int, commune_code:str) -> list[tuple[str,str]]:
    """Compatibilidad de pruebas: construye payload, pero Radar no lo envía a CEAD."""
    text=re.sub(r"\D","",str(commune_code or "")); commune=str(int(text)) if text else ""
    data=[("medida","1"),("tipoVal","1,2"),("anio[]",str(year))]
    data += [("trimestre[]",str(q)) for q in (4,3,2,1)]
    data += [("mes[]",str(m)) for m,_ in MONTHS]
    data += [("mes_nombres[]",name) for _,name in MONTHS]
    data += [("comuna[]",commune),("familia[]","4"),("familia_nombres[]","Delitos asociados a drogas"),("grupo[]","401"),("grupo_nombres[]","Crímenes y simples delitos ley de drogas")]
    for sid,name in [("40101","Tráfico de sustancias"),("40102","Microtráfico de sustancias"),("40103","Elaboración o producción de sustancias"),("40104","Otras infracciones a la ley de drogas")]: data += [("subgrupo[]",sid),("subgrupo_nombres[]",name)]
    data += [("seleccion","2"),("descarga","false")]
    return data


def parse_cead_html(html_text:str, year:int, commune_code:str) -> list[dict]:
    """Parser puro conservado para compatibilidad; no realiza solicitudes de red."""
    soup=BeautifulSoup(html_text or "","html.parser"); out=[]; code=str(commune_code).zfill(5)
    for table in soup.find_all("table"):
        raw=[]
        for tr in table.find_all("tr"):
            cells=[" ".join(c.get_text(" ",strip=True).split()) for c in tr.find_all(["th","td"])]
            if cells: raw.append(cells)
        if not raw: continue
        header_idx=None; headers=[]
        for i,row in enumerate(raw):
            low=[c.lower() for c in row]
            if sum(1 for m in MONTH_LOOKUP if m in low)>=3: header_idx=i; headers=row; break
        if header_idx is None: continue
        month_cols={i:MONTH_LOOKUP.get(str(h).strip().lower()) for i,h in enumerate(headers)}; month_cols={i:m for i,m in month_cols.items() if m}
        for row in raw[header_idx+1:]:
            if not row: continue
            label=row[0].strip()
            for col,month in month_cols.items():
                if col>=len(row): continue
                text=re.sub(r"[^0-9-]","",str(row[col] or ""))
                if not text or text=="-": continue
                out.append({"year":int(year),"month":int(month),"period":f"{int(year):04d}-{int(month):02d}","commune_code":code,"offense":label,"cases_policiales":int(text)})
    return out


def probe_cead_direct(year: int | None = None, commune_code: str = "01101") -> dict:
    started = datetime.now(timezone.utc).isoformat()
    try:
        r = requests.get(MANIFEST_URL, headers={"User-Agent": "RadarDelictual/0.5 CEAD-consumer"}, timeout=20); r.raise_for_status(); upstream=(r.json().get("primary_probe") or {})
        return {"source_id":"cead_primary_externalized","retrieved_at":started,"ok":False,"externalized":True,"producer_repo":PRODUCER_REPO,"upstream_primary_available":bool(upstream.get("ok")),"upstream_primary_status":upstream,"latest_nonzero_period":None,"note":"La adquisición primaria CEAD pertenece a CEAD-Data-Pipeline; Radar Delictual solo consume su dataset publicado."}
    except Exception as exc:
        return {"source_id":"cead_primary_externalized","retrieved_at":started,"ok":False,"externalized":True,"producer_repo":PRODUCER_REPO,"latest_nonzero_period":None,"error":f"{type(exc).__name__}: {exc}","note":"No se ejecuta POST a CEAD desde Radar Delictual."}


def collect_direct_year(year: int, communes, min_pause: float = 0.45):
    return [], [{"source_id":"cead_direct_disabled_in_radar","ok":True,"executed":False,"year":int(year),"note":"Extracción directa externalizada a CEAD-Data-Pipeline."}]


def annualize_direct(rows: list[dict]) -> list[dict]:
    return []
