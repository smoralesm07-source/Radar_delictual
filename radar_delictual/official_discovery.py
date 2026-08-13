from __future__ import annotations
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .sources import fetch_url

TRASPASO_URL="https://traspaso.digital.gob.cl/ministerio-de-seguridad-publica/subsecretaria-de-prevencion-del-delito/"
TERMS=("homicid","casos policiales","enusc","trata","tráfico","trafico","seguridad ciudadana","sitia","delict")

def discover_official_publications() -> tuple[list[dict],dict]:
    now=datetime.now(timezone.utc).isoformat()
    try:
        r=fetch_url(TRASPASO_URL); soup=BeautifulSoup(r.text,"html.parser"); out=[]; seen=set()
        for a in soup.find_all("a",href=True):
            title=" ".join(a.get_text(" ",strip=True).split())
            href=urljoin(TRASPASO_URL,a["href"])
            combined=(title+" "+href).lower()
            if not any(t in combined for t in TERMS): continue
            if href in seen: continue
            seen.add(href)
            out.append({"source_id":"gobierno_traspaso_spd","title":title or href.rsplit('/',1)[-1],"url":href,"retrieved_at":now,"publication_type":"official_discovery","data_status":"observed_link"})
        return out,{"source_id":"gobierno_traspaso_spd_discovery","ok":True,"publications":len(out)}
    except Exception as exc:
        return [],{"source_id":"gobierno_traspaso_spd_discovery","ok":False,"error":f"{type(exc).__name__}: {exc}"}
