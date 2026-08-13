import json
from datetime import datetime, timezone
from typing import Iterable
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

from .config import CONFIG_DIR, TIMEOUT_SECONDS, USER_AGENT

MP_ANNUAL_URLS = {
    2025: "https://www.fiscaliadechile.cl/sites/default/files/documentos/Bolet%C3%ADn_Anual_2025-20260101_v1.xlsx",
    2024: "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_Anual__2024.xls",
    2023: "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_Anual_enero_diciembre_2023.xls",
    2022: "https://www.fiscaliadechile.cl/sites/default/files/documentos/BoletIn_Anual_202220.xls",
    2021: "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_anual_enero_diciembre_2021.xls",
    2020: "https://www.fiscaliadechile.cl/sites/default/files/documentos/Boletin_institucional_enero_diciembre_2020.xls"
}


def load_sources() -> dict:
    return json.loads((CONFIG_DIR / "sources.json").read_text(encoding="utf-8"))


def fetch_url(url: str, *, session: requests.Session | None = None) -> requests.Response:
    s = session or requests.Session()
    response = s.get(url, timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response


def snapshot_source_page(source_id: str, url: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    try:
        r = fetch_url(url)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        return {"source_id":source_id,"url":url,"retrieved_at":now,"http_status":r.status_code,"ok":True,"title":title[:300]}
    except Exception as exc:
        return {"source_id":source_id,"url":url,"retrieved_at":now,"ok":False,"error":f"{type(exc).__name__}: {exc}"}


def probe_sources(sources: Iterable[dict]) -> list[dict]:
    items = list(sources)
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(items)))) as pool:
        return list(pool.map(lambda s: snapshot_source_page(s["source_id"], s["url"]), items))
