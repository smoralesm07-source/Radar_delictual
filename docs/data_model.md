# Modelo de datos · Radar Delictual v0.1

## 1. Hecho principal: `territorial_metric`

| Campo | Tipo | Regla |
|---|---|---|
| `year` | int | Año de observación, no año de descarga |
| `territory_level` | enum | `national`, `region`, `province`, `commune` |
| `region_code` | string | Código estable; `CL` para nacional |
| `region_name` | string | Nombre normalizado |
| `commune_code` | string/null | Código comunal cuando exista |
| `commune_name` | string/null | Comuna cuando exista |
| `crime_category` | string | Categoría original normalizada |
| `metric` | string | `casos_policiales`, `delitos_ingresados`, `victimas_homicidio`, etc. |
| `value` | int/float/null | 0 solo cuando la fuente informa cero |
| `rate_100k` | float/null | Solo si la fuente publica/permite calcular tasa comparable |
| `observation_unit` | string | Evita mezclar casos, delitos, víctimas, denuncias o detenciones |
| `source_id` | string | FK a catálogo de fuentes |
| `source_year` | int | Año del documento/dataset |
| `data_status` | enum | `observed`, `derived_sum`, `no_disponible` |
| `aml_class` | enum | `base_19913`, `proxy_19913`, `crimen_organizado_proxy`, `contexto_general` |
| `weight` | float | Peso metodológico versionado |
| `confidence` | enum | Confianza del mapeo, no del hecho penal |
| `legal_mapping_version` | string | Versión de taxonomía AML |

## 2. Evidencia

`source_evidence.jsonl` preserva URL, fecha de recuperación, hash SHA-256, tamaño y unidad de observación del archivo descargado.

## 3. Identificadores interoperables futuros

- `territory_id`: región/comuna oficial.
- `economic_activity_code`: código SII.
- `uaf_sector_id`: actividad/sujeto obligado Ley 19.913.
- `organization_id`, `provider_id`, `person_id`: solo cuando otra fuente pública permita una entidad estable y jurídicamente pertinente.
- `evidence_id`: referencia inmutable a evidencia pública.

Nunca se crea una relación persona/empresa-delito a partir de una mera coincidencia territorial.

## 4. Capas de riesgo

### A. Criminalidad general
Contexto del territorio, sin inferencia AML.

### B. Crimen organizado
Mercados/fenómenos como drogas, armas, secuestro, extorsión, trata, contrabando, receptación y violencia instrumental.

### C. Relevancia Ley 19.913
El mapeo exacto debe hacerse por código/tipo penal contra la versión vigente del artículo 27. Una categoría estadística amplia se etiqueta `proxy_19913`, nunca `base_19913`, salvo cuando la cobertura jurídica sea suficientemente directa.

### D. Exposición sectorial futura

`territorial_risk_signal × economic_activity × UAF_sector × density/exposure`

La exposición sectorial no se interpreta como conducta ilícita. Sirve para priorizar análisis y diseñar controles basados en riesgo.
