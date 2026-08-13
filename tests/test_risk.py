from radar_delictual.risk import build_region_risk


def rec(year, code, name, cat, value, cls, weight):
    return {"year":year,"region_code":code,"region_name":name,"territory_level":"region","metric":"delitos_ingresados","crime_category":cat,"value":value,"aml_class":cls,"weight":weight}


def test_score_no_trata_criminalidad_general_como_aml():
    rows = [rec(2025,"01","A","DROGAS",100,"base_19913",1.0),rec(2025,"01","A","HURTOS",10,"contexto_general",0.15),rec(2025,"02","B","DROGAS",10,"base_19913",1.0),rec(2025,"02","B","HURTOS",10000,"contexto_general",0.15)]
    out = build_region_risk(rows)
    scores = {r["region_code"]:r["pressure_score"] for r in out}
    assert scores["01"] > scores["02"]


def test_score_tiene_disclaimer():
    out = build_region_risk([rec(2025,"01","A","DROGAS",1,"base_19913",1.0)])
    assert "no es probabilidad" in out[0]["interpretation"].lower()
