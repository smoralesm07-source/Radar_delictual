from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .config import CONFIG_DIR, RAW_DIR


def load_rules() -> dict:
    return json.loads((CONFIG_DIR / "legal_code_rules.json").read_text(encoding="utf-8"))


def classify_mp_code(code: int | str, rules: dict | None = None) -> dict:
    rules = rules or load_rules()
    key = str(int(code)) if str(code).strip().isdigit() else str(code).strip()
    if key in rules["exact"]:
        out = dict(rules["exact"][key]); out.update({"code":key,"rule_type":"exact","rules_version":rules["version"]}); return out
    if key.isdigit():
        number = int(key)
        if number in set(rules.get("drug_nonvigent", [])):
            return {"code":key,"class":"historical_nonvigent","confidence":"high","basis":"Código marcado no vigente en catálogo","rule_type":"exclusion","rules_version":rules["version"]}
        for rule in rules.get("ranges", []):
            lo, hi = rule["codes"]
            if lo <= number <= hi:
                out={k:v for k,v in rule.items() if k!="codes"}; out.update({"code":key,"rule_type":"range","rules_version":rules["version"]}); return out
    out=dict(rules["default"]); out.update({"code":key,"rule_type":"default","rules_version":rules["version"]}); return out


def legal_summary(rules: dict | None = None) -> dict:
    rules=rules or load_rules(); counts={}
    for value in rules["exact"].values(): counts[value["class"]]=counts.get(value["class"],0)+1
    return {"version":rules["version"],"legal_basis":rules["legal_basis"],"catalog":rules["catalog"],"exact_rules":len(rules["exact"]),"range_rules":len(rules["ranges"]),"classes":counts}


def collect_legal_evidence() -> tuple[list[dict], list[dict]]:
    from .sources import fetch_url
    rules=load_rules(); evidence=[]; status=[]
    targets=[("fiscalia_catalogo_delitos",rules["catalog"]["source"],"Catalogo_de_delitos.pdf","catalogo_codigos_delito"),("bcn_ley_19913",rules["legal_basis"]["source"],"ley_19913_art27.html","norma_juridica")]
    for source_id,url,filename,unit in targets:
        try:
            response=fetch_url(url); path=RAW_DIR/filename; path.write_bytes(response.content); sha=hashlib.sha256(response.content).hexdigest()
            evidence.append({"evidence_id":f"legal:{source_id}:v0.2","source_id":source_id,"url":url,"retrieved_at":datetime.now(timezone.utc).isoformat(),"sha256":sha,"bytes":len(response.content),"observation_unit":unit,"rules_version":rules["version"]})
            status.append({"source_id":source_id,"ok":True,"evidence_sha256":sha})
        except Exception as exc:
            status.append({"source_id":source_id,"ok":False,"error":f"{type(exc).__name__}: {exc}","static_rules_available":True})
    return evidence,status
