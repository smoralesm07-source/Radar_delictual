import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import CONFIG_DIR
from .sources import fetch_url

DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b")


def _watch_config() -> dict:
    return json.loads((CONFIG_DIR / "watchlist.json").read_text(encoding="utf-8"))


def _nearby_date(anchor) -> str | None:
    text = " ".join(anchor.parent.stripped_strings) if anchor.parent else ""
    m = DATE_RE.search(text)
    if not m:
        return None
    d, mth, y = m.groups()
    return f"{y}-{int(mth):02d}-{int(d):02d}"


def collect_osint_events() -> tuple[list[dict], list[dict]]:
    cfg = _watch_config()
    keywords = [k.lower() for k in cfg["keywords"]]
    events: dict[str, dict] = {}
    status = []
    now = datetime.now(timezone.utc).isoformat()
    for feed in cfg["feeds"]:
        try:
            r = fetch_url(feed["url"])
            soup = BeautifulSoup(r.text, "html.parser")
            count = 0
            for a in soup.find_all("a", href=True):
                title = " ".join(a.get_text(" ", strip=True).split())
                if len(title) < 18:
                    continue
                hits = sorted({k for k in keywords if k in title.lower()})
                if not hits:
                    continue
                url = urljoin(feed["url"], a["href"])
                if not url.startswith("http"):
                    continue
                events[url] = {"event_id":"url:"+hashlib.sha1(url.encode("utf-8")).hexdigest(),"source_id":feed["source_id"],"title":title[:500],"url":url,"published_date":_nearby_date(a),"retrieved_at":now,"matched_keywords":hits,"event_type":"official_publication_signal","data_status":"observed_publication"}
                count += 1
            status.append({"source_id":feed["source_id"],"ok":True,"events":count})
        except Exception as exc:
            status.append({"source_id":feed["source_id"],"ok":False,"error":f"{type(exc).__name__}: {exc}"})
    return list(events.values()), status
