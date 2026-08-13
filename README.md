# Radar Delictual Chile · OSINT + AML · v0.2

Radar OSINT que estructura antecedentes delictuales y policiales de Chile desde 2020 para producir señales territoriales trazables que puedan incorporarse posteriormente a modelos de riesgo sectorial LA/FT.

> El radar no determina culpabilidad, no imputa delitos a territorios, personas o sectores y no calcula probabilidad de lavado de activos. Los scores son señales analíticas para priorizar revisión de evidencia pública.

## Novedades v0.2

- **Capa comunal oficial:** 205 comunas con víctimas de homicidio consumado en 2024, con frecuencia, tasa por 100.000 habitantes y población publicada.
- **Actualidad 2025:** señal regional y comunal del primer semestre de 2025, preservada separadamente del dato anual.
- **Unidad correcta de homicidio:** se usa la víctima validada interinstitucionalmente, no el caso policial CEAD ni el delito ingresado a SAF.
- **Score territorial v0.2:** combina el proxy AML del Ministerio Público con presión de homicidios anual y reciente, manteniendo los componentes auditables.
- **Score comunal estabilizado:** reduce la volatilidad de tasas en comunas pequeñas mediante shrinkage poblacional y combina tasa, volumen y señal reciente.
- **Mapeo jurídico por código:** reglas versionadas contra el artículo 27 de la Ley 19.913 y el Catálogo de Delitos del Ministerio Público a diciembre de 2025.
- **Clases jurídicas separadas:** `laundering_offense`, `predicate_direct`, `predicate_candidate`, `organized_crime_signal`, `historical_nonvigent`, `unmapped`.
- **Contrato de integración:** salida normalizada para cruces posteriores por `territory_id`, `region_code` y `commune_code` con Radar SII/UAF.
- **Descubrimiento oficial:** catálogo automático de publicaciones desde la Plataforma de Traspaso del Gobierno como fallback de CEAD.
- **Evidencia reforzada:** los CSV auditados de referencia y los archivos fuente descargables se registran con SHA-256.

## Fuentes principales

1. Ministerio Público: boletines estadísticos SAF 2020-2025 y Estadística Interactiva para información vigente.
2. Centro para la Prevención de Homicidios y Delitos Violentos / Observatorio de Homicidios: informe 2024 e informe primer semestre 2025.
3. CEAD / Ministerio de Seguridad Pública: casos policiales, denuncias, detenciones y tasas; actualmente protegido por WAF frente a GitHub Actions.
4. Plataforma de Traspaso del Gobierno: catálogo oficial alternativo de publicaciones de la Subsecretaría de Prevención del Delito.
5. Fiscalía Nacional: Catálogo de Delitos y publicaciones de crimen organizado.
6. BCN LeyChile: Ley 19.913 vigente para versionar el mapeo jurídico.
7. SUBDERE CUT 2018: normalización de códigos territoriales cuando el archivo es accesible.
8. Carabineros, PDI, Aduanas y SENDA: fuentes catalogadas para expansión de procedimientos, incautaciones y mercados ilícitos.

## Salidas v0.2

- `data/processed/territorial_metrics.jsonl`
- `data/processed/territorial_priority_v2.json`
- `data/processed/commune_homicide_pressure.json`
- `data/processed/legal_mapping_summary.json`
- `data/processed/integration_ready.json`
- `data/processed/osint_events.jsonl`
- `data/processed/official_publications.jsonl`
- `data/processed/source_status.json`
- `data/evidence/source_evidence.jsonl`
- `public/index.html`
- `public/data.json`

## Modelo regional v0.2

`territorial_priority_score` = 60% presión delictual AML proxy del Ministerio Público + 20% percentil de tasa regional de homicidio 2024 + 15% percentil de tasa regional H1 2025 + 5% variación H1 2025 vs H1 2024.

El resultado es **prioridad territorial AML/OSINT**: no una probabilidad de LA/FT.

## Modelo comunal

La tasa de homicidios 2024 se estabiliza hacia 6,0 por 100.000 mediante un factor dependiente de población y luego se combina con volumen 2024 y víctimas H1 2025. Así una comuna pequeña no domina el ranking por una sola víctima. Este score es contexto territorial, no AML.

## Mapeo Ley 19.913

`config/legal_code_rules.json` enlaza códigos del Catálogo de Delitos del Ministerio Público con el artículo 27 de la Ley 19.913. Las reglas directas se aplican solo cuando el código permite asociar el ilícito a una norma expresamente comprendida. Categorías agrupadas permanecen como `predicate_candidate`. Extorsión, asociaciones criminales, receptación y mercados de vehículos se mantienen como `organized_crime_signal` y no se convierten automáticamente en delito base.

## Interoperabilidad

`integration_ready.json` entrega `territory_id`, nivel geográfico, período, familia de señal, score, relevancia AML y llaves `region_code`/`commune_code`, permitiendo cruces futuros con presencia de actividades económicas SII y sujetos obligados UAF sin inferir conducta ilícita.

## Ejecución

```bash
python -m pip install -r requirements.txt
pytest -q
python run.py
```

Una falla 403, timeout o ausencia de extracción nunca se transforma en valor cero. La herramienta apoya análisis OSINT y priorización basada en riesgo; no sustituye investigación penal, ROS ni evaluación formal de riesgo LA/FT.
