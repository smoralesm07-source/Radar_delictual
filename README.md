# Radar Delictual Chile · OSINT + AML · v0.3

Radar OSINT para estructurar antecedentes delictuales públicos de Chile desde 2020 y transformarlos en señales territoriales trazables para análisis basado en riesgo LA/FT.

> **Regla central v0.3:** criminalidad general no es sinónimo de riesgo LA/FT. Un dato solo pondera el score AML cuando existe un vínculo jurídico/metodológico defendible con delitos base del artículo 27 de la Ley 19.913. Homicidios tienen peso AML **0**.

## Qué cambia en v0.3

- **CEAD a nivel comunal:** colector automatizado sobre la ruta oficial BCN/SIIT, que declara como fuente estadísticas de la Subsecretaría de Prevención del Delito/CEAD.
- **Cobertura territorial esperada:** las 346 comunas mediante los 28 reportes distritales, con control de completitud y deduplicación.
- **Cadena de procedencia:** `BCN/SIIT → SPD/CEAD`; no se presenta un dato intermediado como descarga directa de CEAD.
- **Catálogo CEAD ↔ artículo 27:** `config/cead_catalog_aml.json` separa familia directa, candidata parcial y contexto.
- **Drogas sí pondera:** la familia CEAD “Delitos asociados a drogas” comprende tráfico, microtráfico, elaboración/producción y otras infracciones a la Ley de Drogas; se asocia a Ley 20.000, expresamente incluida por el artículo 27.
- **Armas no pondera agregadamente:** artículo 27 remite específicamente al artículo 10 de Ley 17.798 y la familia CEAD es más amplia; requiere subgrupo/código antes de incorporarse.
- **Homicidios fuera del score:** se conservan únicamente como contexto de violencia con `aml_weight=0.0` y `score_eligible=false`.
- **Control de calidad 2025:** las tablas territoriales más recientes se comparan entre secciones. Una duplicación exacta se preserva como evidencia pero pasa a `quarantined_duplicate_section` y no alimenta el score.
- **Score comunal v0.3:** basado exclusivamente en datos CEAD utilizables de familias vinculadas a delitos base; en esta versión inicial, la familia drogas.
- **Integración SII/UAF:** `integration_ready.json` expone territorio, comuna normalizada, relación artículo 27, score y procedencia sin usar homicidios.

## Fuentes prioritarias

1. **CEAD / Ministerio de Seguridad Pública:** fuente última de casos policiales, denuncias, detenciones, aprehendidos, frecuencias y tasas.
2. **BCN SIIT:** ruta automatizable oficial para series territoriales CEAD cuando el WAF de CEAD bloquea GitHub Actions.
3. **Ministerio Público:** histórico 2020–2025 de delitos ingresados a SAF y Catálogo de Delitos.
4. **BCN LeyChile:** texto vigente del artículo 27 de Ley 19.913.
5. **Centro para la Prevención de Homicidios:** contexto separado, sin ponderación AML.
6. Carabineros, PDI, Aduanas, SENDA y Fiscalía/UCOD: expansión OSINT y mercados criminales.

## Modelo CEAD ↔ artículo 27

| Familia CEAD | Tratamiento v0.3 | Pondera AML |
|---|---|---:|
| Delitos asociados a drogas | Relación directa a nivel de familia → Ley 20.000 | Sí |
| Delitos asociados a armas | Parcial; requiere subgrupo/código | No |
| Delitos contra vida/integridad | Familia mixta | No |
| Robos violentos | Contexto | No |
| Violencia intrafamiliar | Contexto | No |
| Propiedad no violentos | Contexto/mercado criminal | No |
| Incivilidades | Contexto | No |
| Homicidios | Contexto independiente | **No, peso 0** |

La clasificación puede ampliarse cuando el CEAD entregue granularidad de subgrupo compatible con una asociación jurídica precisa. Una coincidencia temática nunca basta para promover un delito a `predicate_direct`.

## Salidas v0.3

```text
data/processed/cead_communal_metrics.jsonl
data/processed/cead_aml_commune_priority_v3.json
data/processed/cead_catalog_art27.json
data/processed/cead_topic_availability.jsonl
data/processed/region_aml_proxy_v3.json
data/processed/homicide_context.json
data/processed/integration_ready.json
data/processed/source_status.json
data/evidence/source_evidence.jsonl
public/index.html
public/data.json
```

## Score comunal CEAD v0.3

La señal se calcula solo con registros `score_eligible=true` y `quality_status=usable`.

Para la familia drogas:

- tasa de denuncias comunal: dato observado;
- población: dato territorial oficial cuando está disponible;
- frecuencia: estimación explícita `tasa × población / 100.000` cuando la fuente no publica directamente frecuencia anual;
- tasa estabilizada: reduce volatilidad de comunas pequeñas;
- score: 70% percentil de tasa estabilizada + 30% percentil de frecuencia estimada.

El resultado se denomina **prioridad comunal CEAD–artículo 27**, no “probabilidad de lavado”.

## Homicidios

Los archivos de homicidio siguen disponibles para caracterización criminal y análisis de contexto, pero:

```text
aml_weight = 0.0
score_eligible = false
```

No participan en `cead_aml_commune_priority_v3`, en el proxy regional AML ni en el contrato de integración de riesgo LA/FT.

## Calidad y cuarentena

La v0.3 no confía automáticamente en que una tabla publicada sea correcta. Para las tablas BCN 2026 que reproducen información CEAD se comparan las secciones de vida/integridad, VIF y drogas. Si los registros son exactamente idénticos, la tabla de drogas queda en cuarentena. La información se conserva para auditoría, pero su `aml_weight` pasa a cero.

Un HTTP 403, timeout o ausencia de extracción nunca se convierte en cero delitos.

## Ejecución

```bash
python -m pip install -r requirements.txt
pytest -q
python run.py
```

GitHub Actions ejecuta el radar diariamente, mantiene el snapshot generado en `radar-data` y publica el dashboard en GitHub Pages.

## Próximo desarrollo

La arquitectura ya deja preparado un colector para ampliar CEAD desde familia → grupo → subgrupo. La prioridad para v0.4 será obtener de forma reproducible más subgrupos comunales que puedan mapearse individualmente al artículo 27 —por ejemplo, componentes específicos de armas, secuestro/trata u otros delitos incluidos en la ley— antes de incorporarlos al scoring.
