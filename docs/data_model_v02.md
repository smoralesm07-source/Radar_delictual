# Modelo de datos v0.2

La v0.2 mantiene el hecho `territorial_metric` y agrega dos salidas derivadas: `territorial_priority_v2` y `integration_signal`.

## Territorial metric

Campos principales: `year`, `period`, `territory_level`, `region_code`, `commune_code`, `territory_id`, `crime_category`, `metric`, `value`, `rate_100k`, `population`, `observation_unit`, `source_id`, `data_status`.

Las unidades se mantienen separadas: `delito_ingresado_en_SAF`, `victima_homicidio_consumado`, `caso_policial`, `denuncia`, `detencion`, etc.

## Prioridad regional v0.2

Componentes auditables: proxy AML Fiscalía, tasa de homicidios 2024, tasa H1 2025 y tendencia H1 interanual. El score es una señal de priorización y no una probabilidad de LA/FT.

## Presión comunal de homicidios

Se calcula solo sobre las 205 comunas con víctimas registradas en la tabla oficial 2024. La tasa se estabiliza por población y se combina con volumen y señal H1 2025. Su `aml_relevance` de integración es `context_only`.

## Mapeo jurídico

`legal_code_rules.json` versiona reglas sobre códigos del Catálogo de Delitos de Fiscalía y artículo 27 Ley 19.913. Clases: lavado, delito base directo, candidato, señal de crimen organizado, histórico no vigente y sin mapear.

## Interoperabilidad

`integration_ready.json` normaliza `territory_id`, `region_code`, `commune_code`, `period`, `signal_family`, `score`, `score_version`, `aml_relevance` y `source_families`, listo para uniones con Radar SII/UAF/CGR.
