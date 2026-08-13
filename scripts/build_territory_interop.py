from __future__ import annotations

import json
from pathlib import Path

from radar_delictual.territory import canonical_commune_code, commune_territory_id

SOURCE = Path("data/processed/cead_annual_master_v4.jsonl")
OUTPUT = Path("data/processed/territory_interop_v1.jsonl")
STATUS = Path("data/processed/territory_interop_status_v1.json")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def adapt(row: dict) -> dict:
    out=dict(row)
    code=canonical_commune_code(out.get("commune_code"))
    if code:
        out["commune_code"]=code
        out["territory_id"]=commune_territory_id(code)
        out["territory_mapping_method"]="CODE_EXACT"
        out["territory_mapping_confidence"]=1.0
    else:
        out["territory_id"]=None
        out["territory_mapping_method"]="UNRESOLVED"
        out["territory_mapping_confidence"]=0.0
    out["interop_version"]="1.0"
    out["radar_id"]="RADAR_DELICTUAL"
    return out


def main() -> None:
    rows=[adapt(x) for x in read_jsonl(SOURCE)]
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
    status={
        "interop_version":"1.0",
        "radar_id":"RADAR_DELICTUAL",
        "rows":len(rows),
        "resolved":sum(bool(x.get("territory_id")) for x in rows),
        "unresolved":sum(not bool(x.get("territory_id")) for x in rows),
        "territory_id_format":"CL-COM-{CUT}"
    }
    STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(status,ensure_ascii=False))


if __name__ == "__main__":
    main()
