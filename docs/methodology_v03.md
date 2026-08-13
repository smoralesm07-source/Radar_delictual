# Metodología v0.3 · CEAD comunal y Ley 19.913

## Corrección conceptual

Los homicidios dejan de ser componente de cualquier score AML/LAFT. Se preservan como contexto de violencia con `aml_weight=0` y `score_eligible=false`.

## Jerarquía jurídica

1. `direct_family`: una familia agregada puede vincularse razonablemente con una ley o conjunto de delitos expresamente incorporado por el artículo 27. En v0.3, CEAD **Delitos asociados a drogas** cumple esta condición por la referencia del artículo 27 a Ley 20.000.
2. `partial_requires_subgroup_or_code`: la familia contiene una mezcla de conductas y solo una parte puede corresponder a delito base. CEAD **Delitos asociados a armas** se mantiene aquí porque artículo 27 remite específicamente al artículo 10 de Ley 17.798.
3. `context_only` / `mixed_context`: no pondera automáticamente AML.

## Ruta CEAD comunal

El endpoint CEAD directo está protegido por WAF frente a GitHub Actions. Para mantener automatización reproducible sin evadir controles, v0.3 utiliza una ruta oficial secundaria de BCN/SIIT cuyos reportes declaran como fuente los datos de la Subsecretaría de Prevención del Delito/CEAD. Se conserva la cadena `source_id=bcn_siit_cead_communal` y `ultimate_source_id=cead_estadisticas_delictuales`.

La capa anual 2024 extrae tasas comunales para familias disponibles en los reportes distritales 2025. La capa 2025-Q3 se captura únicamente como dato candidato y se somete a un control de duplicación entre secciones. Si la tabla de drogas coincide exactamente con vida/integridad o VIF, queda en `quarantined_duplicate_section` y su peso AML pasa a cero.

## Score comunal v0.3

Solo utiliza registros `score_eligible=true`, `quality_status=usable` y familia `delitos_asociados_drogas`.

- tasa publicada: observada;
- población 2024: tomada de la tabla territorial vigente cuando está disponible;
- frecuencia: derivada y marcada como estimación a partir de tasa × población;
- tasa estabilizada: shrinkage hacia la mediana comunal, con confiabilidad proporcional a población;
- score = 70% percentil de tasa estabilizada + 30% percentil de frecuencia estimada.

No equivale a probabilidad de lavado de activos ni implica que empresas, habitantes o actividades económicas de una comuna estén vinculados a delitos.
