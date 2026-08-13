# Radar Delictual Chile · OSINT + AML · v0.4

Radar OSINT para estructurar antecedentes delictuales públicos de Chile desde 2020 y transformarlos en **features territoriales trazables** para análisis basado en riesgo LA/FT.

> **Regla central:** criminalidad general no es sinónimo de riesgo LA/FT. Un dato solo adquiere relevancia AML automática cuando existe un vínculo jurídico suficientemente preciso con los delitos del artículo 27 de la Ley 19.913. **Homicidios están fuera del core AML v0.4.**

## Objetivo de v0.4

La v0.4 resuelve el problema de adquisición CEAD separando claramente **origen del dato** de **método de adquisición**. El sitio CEAD es la fuente primaria, pero GitHub Actions puede ser bloqueado por su control de acceso. El radar no intenta eludir ese control.

Se implementa una arquitectura de adaptadores con precedencia explícita:

1. `primary_direct` — POST usado por la interfaz CEAD. Se sondea en cada corrida.
2. `mirror_of_primary` — réplica pública cuyo proceso documenta extracción directa desde CEAD. Se usa como puente cuando el POST primario está bloqueado y se valida por esquema, fechas, cobertura, blob/hash y licencia.
3. `official_secondary` — BCN/SIIT como control oficial secundario de estadísticas territoriales provenientes de SPD/CEAD.
4. `quarantined` — cualquier lote con duplicaciones, esquema inesperado o cobertura insuficiente. Nunca alimenta el maestro.

La precedencia es **directo → réplica → control secundario → cuarentena**. Para una misma comuna, año y categoría, el dato primario directo desplaza automáticamente a la réplica.

## Actualización futura sin intervención manual

El workflow restaura desde la rama `radar-data`:

```text
cead_update_manifest.json
cead_annual_master_v4.jsonl
cead_direct_annual_cache.jsonl
cead_official_secondary_control.jsonl
```

En cada corrida:

1. sondea el endpoint POST de CEAD;
2. compara el período observado con `last_primary_period`;
3. si aparece un período nuevo y el endpoint responde, ejecuta un refresco incremental por comuna;
4. el lote directo solo se acepta si alcanza cobertura nacional suficiente; un lote parcial no reemplaza datos buenos;
5. si CEAD sigue bloqueando el runner, refresca y verifica la réplica;
6. BCN/SIIT se mantiene como control independiente;
7. ausencia, HTTP 403 o timeout **nunca se convierten en cero delitos**.

## Backbone comunal CEAD

La salida principal es:

```text
data/processed/cead_annual_master_v4.jsonl
```

Grano:

```text
comuna × año × categoría delictual × casos_policiales
```

Campos de interoperabilidad y auditoría incluyen:

```text
territory_id
region_code
commune_code
commune_name
year
crime_category
metric
value
source_id
ultimate_source_id
source_tier
quality_status
article27_mapping_key
aml_class
score_eligible
aml_weight
mapping_confidence
```

Además, `cead_predicate_features_v4.jsonl` contiene únicamente observaciones homologadas como delitos/familias base elegibles para cruces posteriores con Radar SII y Radar UAF.

## Catálogo CEAD ↔ artículo 27

`config/cead_catalog_v4.json` modela familia → grupo → subgrupo y aplica la homologación al nivel más granular disponible.

Principios:

- **Drogas:** la familia CEAD asociada a Ley 20.000 es relevante; tráfico, microtráfico y elaboración/producción se consideran `predicate_direct`.
- **Otras infracciones a la Ley de Drogas:** permanecen como `predicate_candidate` hasta conocer el tipo penal exacto.
- **Armas:** la familia CEAD completa no se pondera. El artículo 27 remite específicamente al artículo 10 de Ley 17.798 y el catálogo CEAD es más amplio.
- **Delitos sexuales:** una familia amplia no hereda automáticamente la calidad de los tipos específicos incluidos en el artículo 27.
- **Homicidios/femicidios:** `context_only`, `score_eligible=false`, `aml_weight=0.0`.

## Homicidios

A diferencia de v0.2/v0.3, la v0.4 **ya no descarga homicidios durante la corrida AML**. El código histórico puede mantenerse para análisis separado, pero:

```text
homicides_in_aml_core = 0
aml_weight = 0.0
score_eligible = false
```

No participan en el maestro CEAD, el contrato de integración ni los indicadores AML.

## Fuente puente y trazabilidad

Mientras el POST CEAD esté bloqueado para GitHub Actions, el radar puede usar como puente el dataset público de `bastianolea/delincuencia_chile`, cuyo código documenta consultas directas a la interfaz CEAD y publica una serie comunal mensual procesada.

La v0.4 **no presenta esa réplica como fuente oficial**. Cada snapshot registra:

- repositorio y ruta upstream;
- blob SHA de GitHub cuando está disponible;
- SHA-256 del archivo descargado;
- tamaño;
- fecha mínima y máxima observada;
- número de comunas;
- número de categorías;
- licencia declarada (`GPL-3.0`);
- `ultimate_source_id = cead_estadisticas_delictuales`;
- `source_tier = mirror_of_primary`.

## Salidas principales v0.4

```text
data/processed/cead_annual_master_v4.jsonl
data/processed/cead_predicate_features_v4.jsonl
data/processed/cead_direct_annual_cache.jsonl
data/processed/cead_direct_probe.json
data/processed/cead_update_manifest.json
data/processed/cead_current_predicate_activity_v4.json
data/processed/cead_official_secondary_control.jsonl
data/processed/cead_catalog_art27_v4.json
data/processed/integration_ready.json
data/processed/source_status.json
data/evidence/source_evidence.jsonl
public/index.html
public/data.json
```

## Interpretación

`cead_current_predicate_activity_v4.json` muestra volumen reciente de **casos policiales** para categorías con relación defendible con delitos base. El conteo no se transforma automáticamente en tasa ni en “riesgo LA/FT”. Su función es ofrecer una feature territorial longitudinal, auditable y actualizable.

La presencia de delitos base en una comuna no permite atribuir conductas ilícitas a personas, empresas ni sectores económicos ubicados en ella.

## Ejecución

```bash
python -m pip install -r requirements.txt
pytest -q
python run.py
```

GitHub Actions ejecuta el radar diariamente, restaura el estado incremental desde `radar-data`, conserva snapshots técnicos sin persistir descargas raw y publica GitHub Pages.
