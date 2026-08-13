from __future__ import annotations

import re
import unicodedata
from .cead_external import collect_external


def _norm(value:str)->str:
    value=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+"," ",value).strip()


def collect_cead_bridge(start_year:int=2020):
    return collect_external(start_year)


def drug_family_rows(records:list[dict])->list[dict]:
    aliases={"delitos asociados a drogas","crimenes y simples delitos ley de drogas"}
    return [r for r in records if _norm(r.get("crime_category","")) in aliases]
