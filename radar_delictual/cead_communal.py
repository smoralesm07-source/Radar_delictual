from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .config import CONFIG_DIR, USER_AGENT

ANNUAL_URL = "https://www.bcn.cl/siit/reportesdistritales/reporte_final.html?anno=2025&distrito={district}"
LATEST_URL = "https://www.bcn.cl/siit/reportesdistritales/reporte_final.html?anno=2026&distrito={district}"
TOPIC_DRUGS_URL = "https://www.bcn.cl/siit/estadisticasterritoriales/tema?id=262"
TOPIC_ARMS_URL = "https://www.bcn.cl/siit/estadisticasterritoriales/tema?id=263"
REQUEST_TIMEOUT = 25

DISTRICT_REGION = {
    1:("15","Arica y Parinacota"),2:("01","Tarapacá"),3:("02","Antofagasta"),4:("03","Atacama"),5:("04","Coquimbo"),
    6:("05","Valparaíso"),7:("05","Valparaíso"),8:("05","Valparaíso"),9:("13","Metropolitana de Santiago"),10:("13","Metropolitana de Santiago"),
    11:("13","Metropolitana de Santiago"),12:("13","Metropolitana de Santiago"),13:("13","Metropolitana de Santiago"),14:("13","Metropolitana de Santiago"),
    15:("06","Libertador General Bernardo O'Higgins"),16:("06","Libertador General Bernardo O'Higgins"),17:("07","Maule"),18:("07","Maule"),19:("16","Ñuble"),
    20:("08","Biobío"),21:("08","Biobío"),22:("09","La Araucanía"),23:("09","La Araucanía"),24:("14","Los Ríos"),25:("10","Los Lagos"),
    26:("10","Los Lagos"),27:("11","Aysén del General Carlos Ibáñez del Campo"),28:("12","Magallanes y de la Antártica Chilena")
}

ANNUAL_COLUMNS = [
    ("delitos_contra_vida_integridad","Delitos contra la vida o integridad de las personas"),
    ("delitos_asociados_drogas","Delitos asociados a drogas"),
    ("delitos_propiedad_no_violentos","Delitos contra la propiedad no violentos"),
    ("violencia_intrafamiliar","Violencia intrafamiliar")
]


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(value)).strip("-")


def _num(value: str) -> float | None:
    text = str(value).strip().replace("\xa0", "")
    if text in {"", "--", "-", "nan"}: return None
    text = text.replace(".", "").replace(",", ".")
    try: return float(text)
    except ValueError: return None


def load_catalog() -> dict:
    return json.loads((CONFIG_DIR / "cead_catalog_aml.json").read_text(encoding="utf-8"))


def _fetch(url: str) -> tuple[str, dict]:
    r = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    body = r.text
    return body, {"url":url,"retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":hashlib.sha256(r.content).hexdigest(),"bytes":len(r.content)}


def _find_table(soup: BeautifulSoup, needles: tuple[str, ...]):
    for tag in soup.find_all(["h4","h5","h6","strong"]):
        text = _norm(tag.get_text(" ", strip=True))
        if all(_norm(n) in text for n in needles):
            table = tag.find_next("table")
            if table is not None: return table
    return None


def _table_rows(table) -> list[list[str]]:
    if table is None: return []
    rows=[]
    for tr in table.find_all("tr"):
        cells=[" ".join(c.get_text(" ",strip=True).split()) for c in tr.find_all(["th","td"])]
        if cells: rows.append(cells)
    return rows


def _is_commune(name: str) -> bool:
    n=_norm(name)
    return bool(n) and not n.startswith("distrito") and not n.startswith("region") and n not in {"pais","nivel territorial"}


def parse_annual_2024(html: str, district: int, catalog: dict | None = None) -> list[dict]:
    catalog=catalog or load_catalog(); soup=BeautifulSoup(html,"html.parser")
    table=_find_table(soup,("tasas anuales denuncias","familia de delitos"))
    rows=_table_rows(table); out=[]; region_code,region_name=DISTRICT_REGION[district]
    for cells in rows:
        if len(cells)<5 or not _is_commune(cells[0]): continue
        values=[_num(x) for x in cells[1:5]]
        if all(v is None for v in values): continue
        for (family_key,label),rate in zip(ANNUAL_COLUMNS,values):
            if rate is None: continue
            mapping=catalog["families"][family_key]
            out.append({"year":2024,"period":"2024","period_type":"annual","territory_level":"commune","region_code":region_code,"region_name":region_name,"commune_code":None,"commune_name":cells[0],"commune_name_norm":_norm(cells[0]),"territory_id":f"CL-{region_code}-{_slug(cells[0])}","cead_family_key":family_key,"crime_category":label,"metric":"tasa_denuncias_100k","value":None,"rate_100k":float(rate),"population":None,"estimated_frequency":None,"source_id":"bcn_siit_cead_communal","ultimate_source_id":"cead_estadisticas_delictuales","source_url":ANNUAL_URL.format(district=district),"observation_unit":"denuncia_formal","data_status":"observed_rate","quality_status":"usable","article27_relation":mapping["article27_relation"],"score_eligible":bool(mapping["score_eligible"]),"aml_weight":float(mapping["aml_weight"]),"mapping_confidence":mapping["confidence"],"district":district})
    return out


def _parse_latest_section(html: str, district: int, heading: str) -> list[dict]:
    soup=BeautifulSoup(html,"html.parser"); table=_find_table(soup,(heading,"frecuencia","tasa")); rows=_table_rows(table); out=[]
    for cells in rows:
        if len(cells)<7 or not _is_commune(cells[0]): continue
        vals=[_num(x) for x in cells[1:7]]
        if any(v is None for v in vals): continue
        out.append({"commune_name":cells[0],"freq_2024":int(vals[0]),"freq_2025":int(vals[1]),"pop_2024":int(vals[2]),"pop_2025":int(vals[3]),"rate_2024":float(vals[4]),"rate_2025":float(vals[5])})
    return out


def _signature(rows:list[dict]) -> tuple:
    return tuple(sorted((r["commune_name"],r["freq_2024"],r["freq_2025"],r["pop_2024"],r["pop_2025"],r["rate_2024"],r["rate_2025"]) for r in rows))


def parse_latest_2025(html: str, district: int, catalog: dict | None = None) -> tuple[list[dict],dict[str,int],dict]:
    catalog=catalog or load_catalog(); drug=_parse_latest_section(html,district,"delitos asociados a drogas")
    life=_parse_latest_section(html,district,"delitos contra la vida")
    vif=_parse_latest_section(html,district,"violencia intrafamiliar")
    duplicated=bool(drug) and (_signature(drug)==_signature(life) or _signature(drug)==_signature(vif))
    quality="quarantined_duplicate_section" if duplicated else "usable"
    region_code,region_name=DISTRICT_REGION[district]; out=[]; pops={}
    mapping=catalog["families"]["delitos_asociados_drogas"]
    for r in drug:
        pops[_norm(r["commune_name"])]=r["pop_2024"]
        out.append({"year":2025,"period":"2025-Q3","period_type":"q3_ytd","territory_level":"commune","region_code":region_code,"region_name":region_name,"commune_code":None,"commune_name":r["commune_name"],"commune_name_norm":_norm(r["commune_name"]),"territory_id":f"CL-{region_code}-{_slug(r['commune_name'])}","cead_family_key":"delitos_asociados_drogas","crime_category":"Delitos asociados a drogas","metric":"denuncias","value":r["freq_2025"],"rate_100k":r["rate_2025"],"population":r["pop_2025"],"estimated_frequency":None,"source_id":"bcn_siit_cead_communal","ultimate_source_id":"cead_estadisticas_delictuales","source_url":LATEST_URL.format(district=district),"observation_unit":"denuncia_formal","data_status":"observed_secondary_official","quality_status":quality,"article27_relation":mapping["article27_relation"],"score_eligible":bool(mapping["score_eligible"] and not duplicated),"aml_weight":float(mapping["aml_weight"]) if not duplicated else 0.0,"mapping_confidence":mapping["confidence"],"district":district})
    return out,pops,{"district":district,"duplicated_sections":duplicated,"drug_rows":len(drug)}


def enrich_annual_population(records:list[dict], population_map:dict[tuple[str,str],int]) -> list[dict]:
    for r in records:
        pop=population_map.get((r["region_code"],r["commune_name_norm"]))
        if pop:
            r["population"]=pop
            r["estimated_frequency"]=int(round(r["rate_100k"]*pop/100000.0))
            r["frequency_status"]="derived_from_published_rate_and_2024_population"
        else:
            r["frequency_status"]="unavailable"
    return records


def _topic_metadata() -> tuple[list[dict],list[dict]]:
    rows=[]; status=[]
    for source_id,url,family in [("bcn_siit_topic_drugs",TOPIC_DRUGS_URL,"delitos_asociados_drogas"),("bcn_siit_topic_arms",TOPIC_ARMS_URL,"delitos_asociados_armas")]:
        try:
            html,ev=_fetch(url); soup=BeautifulSoup(html,"html.parser"); text=" ".join(soup.stripped_strings)
            years=sorted({int(y) for y in re.findall(r"\b20(?:1[8-9]|2[0-9])\b",text) if 2018<=int(y)<=2026})
            rows.append({"source_id":source_id,"cead_family_key":family,"url":url,"available_years":years,"territorial_levels":["country","region","commune"],"retrieved_at":ev["retrieved_at"],"sha256":ev["sha256"]})
            status.append({"source_id":source_id,"ok":True,"available_years":years})
        except Exception as exc: status.append({"source_id":source_id,"ok":False,"error":f"{type(exc).__name__}: {exc}"})
    return rows,status


def collect_cead_communal() -> tuple[list[dict],list[dict],list[dict],list[dict]]:
    catalog=load_catalog(); annual=[]; latest=[]; evidence=[]; status=[]; population_map={}; anomaly_districts=[]
    def job(district:int):
        result={"district":district}
        for kind,url in [("annual",ANNUAL_URL.format(district=district)),("latest",LATEST_URL.format(district=district))]:
            try: result[kind]=_fetch(url)
            except Exception as exc: result[kind+"_error"]=f"{type(exc).__name__}: {exc}"
        return result
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(job,d) for d in range(1,29)]
        for f in as_completed(futures):
            res=f.result(); d=res["district"]
            if "annual" in res:
                html,ev=res["annual"]; rows=parse_annual_2024(html,d,catalog); annual.extend(rows); ev.update({"evidence_id":f"bcn:cead:annual2024:d{d}","source_id":"bcn_siit_cead_communal","district":d,"observation_unit":"tabla_tasa_denuncias_comunal"}); evidence.append(ev)
            else: status.append({"source_id":"bcn_siit_cead_annual_2024","district":d,"ok":False,"error":res.get("annual_error")})
            if "latest" in res:
                html,ev=res["latest"]; rows,pops,diag=parse_latest_2025(html,d,catalog); latest.extend(rows)
                for name,pop in pops.items(): population_map[(DISTRICT_REGION[d][0],name)]=pop
                if diag["duplicated_sections"]: anomaly_districts.append(d)
                ev.update({"evidence_id":f"bcn:cead:q3_2025:d{d}","source_id":"bcn_siit_cead_communal","district":d,"observation_unit":"tabla_denuncias_comunal_q3","quality_check":diag}); evidence.append(ev)
            else: status.append({"source_id":"bcn_siit_cead_latest_2025","district":d,"ok":False,"error":res.get("latest_error")})
    annual=enrich_annual_population(annual,population_map)
    annual_communes={r["territory_id"] for r in annual if r["cead_family_key"]=="delitos_asociados_drogas"}
    usable_latest={r["territory_id"] for r in latest if r["quality_status"]=="usable"}
    status.extend([
        {"source_id":"bcn_siit_cead_annual_2024","ok":len(annual_communes)>=340,"communes":len(annual_communes),"records":len(annual),"note":"Tasas comunales 2024; procedencia declarada BCN→SPD/CEAD."},
        {"source_id":"bcn_siit_cead_latest_2025","ok":True,"records":len(latest),"usable_communes":len(usable_latest),"quarantined_districts":sorted(anomaly_districts),"note":"La v0.3 detecta tablas repetidas entre secciones y las excluye del score."}
    ])
    topic_rows,topic_status=_topic_metadata(); status.extend(topic_status)
    return annual+latest,evidence,status,topic_rows
