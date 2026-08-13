import json

from .config import CONFIG_DIR


def load_taxonomy() -> dict:
    return json.loads((CONFIG_DIR / "crime_taxonomy.json").read_text(encoding="utf-8"))


def classify_category(category: str, taxonomy: dict | None = None) -> dict:
    taxonomy = taxonomy or load_taxonomy()
    return dict(taxonomy["categories"].get(category, taxonomy["default"]))


def annotate_aml(records: list[dict], taxonomy: dict | None = None) -> list[dict]:
    taxonomy = taxonomy or load_taxonomy()
    out = []
    for r in records:
        x = dict(r)
        x.update(classify_category(x.get("crime_category", ""), taxonomy))
        x["legal_mapping_version"] = taxonomy["version"]
        out.append(x)
    return out
