from radar_delictual.aml import classify_category


def test_drogas_es_relevancia_alta():
    x = classify_category("DELITOS LEY DE DROGAS")
    assert x["aml_class"] == "base_19913"
    assert x["weight"] == 1.0


def test_categoria_desconocida_no_se_convierte_en_delito_base():
    x = classify_category("CATEGORIA INVENTADA")
    assert x["aml_class"] == "contexto_general"
