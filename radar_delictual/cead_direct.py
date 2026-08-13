from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import datetime, timezone
from typing import Iterable

import requests
from bs4 import BeautifulSoup

CURRENT_ENDPOINT = "https://cead.minsegpublica.gob.cl/wp-content/themes/gobcl-wp-master/data/get_estadisticas_delictuales.php"
LANDING_URL = "https://cead.minsegpublica.gob.cl/estadisticas-delictuales/"
MONTHS = [(1,"Enero"),(2,"Febrero"),(3,"Marzo"),(4,"Abril"),(5,"Mayo"),(6,"Junio"),(7,"Julio"),(8,"Agosto"),(9,"Septiembre"),(10,"Octubre"),(11,"Noviembre"),(12,"Diciembre")]
MONTH_LOOKUP = {name.lower(): number for number,name in MONTHS}


def _num(value: str) -> int | None:
    text = re.sub(r"[^0-9-]", "", str(value or ""))
    if text in {"", "-"}: return None
    try: return int(text)
    except ValueError: return None


def drug_payload(year:int, commune_code:str) -> list[tuple[str,str]]:
    """Formulario equivalente al usado por la interfaz pública CEAD para la familia drogas.

    No usa cookies de evasión, CAPTCHA ni técnicas de bypass. Si el servidor rechaza
    el request, el adaptador informa el bloqueo y el orquestador usa una fuente puente.
    """
    data:list[tuple[str,str]]=[("medida","1"),("tipoVal","1,2"),("anio[]",str(year))]
    data += [("trimestre[]",str(q)) for q in (4,3,2,1)]
    data += [("mes[]",str(m)) for m,_ in MONTHS]
    data += [("mes_nombres[]",name) for _,name in MONTHS]
    data += [
        ("comuna[]",str(commune_code).zfill(5)),
        ("familia[]","4"),("familia_nombres[]","Delitos asociados a drogas"),
        ("grupo[]","401"),("grupo_nombres[]","Crímenes y simples delitos ley de drogas"),
    ]
    for sid,name in [
        ("40101","Tráfico de sustancias"),("40102","Microtráfico de sustancias"),
        ("40103","Elaboración o producción de sustancias"),("40104","Otras infracciones a la ley de drogas")]:
        data.append(("subgrupo[]",sid)); data.append(("subgrupo_nombres[]",name))
    data += [("seleccion","2"),("descarga","false")]
    return data


def _headers() -> dict[str,str]:
    return {
        "User-Agent":"Mozilla/5.0 (compatible; RadarDelictual/0.4; public-data research)",
        "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
        "Accept":"text/html, */*; q=0.01",
        "X-Requested-With":"XMLHttpRequest",
        "Referer":LANDING_URL,
    }


def post_cead(year:int, commune_code:str, timeout:int=35) -> requests.Response:
    return requests.post(CURRENT_ENDPOINT,data=drug_payload(year,commune_code),headers=_headers(),timeout=timeout,allow_redirects=True)


def parse_cead_html(html_text:str, year:int, commune_code:str) -> list[dict]:
    soup=BeautifulSoup(html_text or "","html.parser")
    table=soup.find("table")
    if table is None: return []
    raw=[]
    for tr in table.find_all("tr"):
        cells=[" ".join(c.get_text(" ",strip=True).split()) for c in tr.find_all(["th","td"])]
        if cells: raw.append(cells)
    if not raw: return []
    header_idx=None; headers=[]
    for i,row in enumerate(raw):
        low=[c.lower() for c in row]
        if sum(1 for m in MONTH_LOOKUP if m in low)>=3:
            header_idx=i; headers=row; break
    # CEAD históricamente ha usado una segunda fila como encabezado; fallback conservador.
    if header_idx is None and len(raw)>=2:
        headers=raw[1]; header_idx=1
    month_cols={i:MONTH_LOOKUP.get(str(h).strip().lower()) for i,h in enumerate(headers)}
    month_cols={i:m for i,m in month_cols.items() if m}
    if not month_cols: return []
    out=[]
    for row in raw[header_idx+1:]:
        if not row: continue
        label=row[0].strip()
        if not label or label.lower() in {"total","nivel territorial"}: continue
        for col,month in month_cols.items():
            if col>=len(row): continue
            value=_num(row[col])
            if value is None: continue
            out.append({
                "year":int(year),"month":int(month),"period":f"{int(year):04d}-{int(month):02d}",
                "commune_code":str(commune_code).zfill(5),"offense":label,"cases_policiales":value,
                "source_id":"cead_direct_post","source_tier":"primary_direct","quality_status":"usable"
            })
    return out


def probe_cead_direct(year:int|None=None, commune_code:str="01101") -> dict:
    year=year or datetime.now().year
    started=datetime.now(timezone.utc).isoformat()
    try:
        r=post_cead(year,commune_code)
        rows=parse_cead_html(r.text,year,commune_code) if r.ok else []
        nonzero=[x for x in rows if (x.get("cases_policiales") or 0)>0]
        periods=sorted({x["period"] for x in nonzero})
        return {
            "source_id":"cead_direct_post","endpoint":CURRENT_ENDPOINT,"retrieved_at":started,
            "ok":bool(r.ok and rows),"http_status":r.status_code,"bytes":len(r.content),
            "response_sha256":hashlib.sha256(r.content).hexdigest(),"parsed_rows":len(rows),
            "latest_nonzero_period":periods[-1] if periods else None,
            "blocking_message":re.sub(r"\s+"," ",r.text[:160]).strip() if not r.ok else None,
            "note":"Sonda primaria sin bypass; si falla, se activa la ruta puente verificada."
        }
    except Exception as exc:
        return {"source_id":"cead_direct_post","endpoint":CURRENT_ENDPOINT,"retrieved_at":started,"ok":False,"error":f"{type(exc).__name__}: {exc}"}


def collect_direct_year(year:int, communes:Iterable[dict], min_pause:float=0.45) -> tuple[list[dict],list[dict]]:
    """Actualización incremental y respetuosa: una petición por comuna para un año.

    Solo se invoca cuando la sonda primaria funciona y el orquestador detecta un
    período nuevo respecto del manifiesto persistido. El ritmo puede ajustarse con
    CEAD_DIRECT_MIN_PAUSE; no se ejecuta para backfills masivos diarios.
    """
    pause=max(min_pause,float(os.getenv("CEAD_DIRECT_MIN_PAUSE",str(min_pause))))
    records=[]; status=[]
    for c in communes:
        code=str(c.get("commune_code") or "").zfill(5)
        if len(code)!=5 or not code.isdigit(): continue
        t0=time.monotonic()
        try:
            r=post_cead(year,code)
            rows=parse_cead_html(r.text,year,code) if r.ok else []
            for row in rows:
                row.update({
                    "commune_name":c.get("commune_name"),"region_code":c.get("region_code"),
                    "region_name":c.get("region_name"),"territory_id":f"CL-{code}"
                })
            records.extend(rows)
            status.append({"commune_code":code,"ok":bool(r.ok and rows),"http_status":r.status_code,"records":len(rows)})
            if not r.ok and r.status_code in {403,429}: break
        except Exception as exc:
            status.append({"commune_code":code,"ok":False,"error":f"{type(exc).__name__}: {exc}"})
        elapsed=time.monotonic()-t0
        time.sleep(max(0.0,pause-elapsed))
    return records,status


def annualize_direct(rows:list[dict]) -> list[dict]:
    grouped={}
    for r in rows:
        key=(int(r["year"]),r["commune_code"],r.get("commune_name"),r.get("region_code"),r.get("region_name"),r["offense"])
        grouped[key]=grouped.get(key,0)+int(r.get("cases_policiales") or 0)
    out=[]
    for (year,code,cname,rcode,rname,offense),value in grouped.items():
        out.append({"year":year,"period":str(year),"territory_level":"commune","territory_id":f"CL-{code}","commune_code":code,"commune_name":cname,"region_code":rcode,"region_name":rname,"crime_category":offense,"metric":"casos_policiales","value":value,"source_id":"cead_direct_post","ultimate_source_id":"cead_estadisticas_delictuales","source_tier":"primary_direct","quality_status":"usable","observation_unit":"caso_policial"})
    return out
