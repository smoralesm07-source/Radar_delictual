# Radar Delictual Chile · OSINT + AML

Radar OSINT para estructurar antecedentes policiales y delictuales de Chile desde 2020, con foco en su futura utilización como capa de riesgo territorial y sectorial LA/FT.

## Objetivo

Convertir publicaciones y estadísticas abiertas de CEAD, Ministerio Público, Carabineros, PDI y otras fuentes oficiales en señales trazables que puedan cruzarse posteriormente con Radar UAF, Radar SII, Radar CGR y otros módulos.

El radar **no califica personas ni entidades como vinculadas a delitos o LA/FT**. Sus scores son indicadores analíticos territoriales construidos sobre datos agregados y proxies explícitos.

## Principios de diseño

1. **Fuente antes que score**: todo registro conserva `source_id`, URL, período y evidencia.
2. **No mezclar unidades**: casos policiales CEAD, delitos ingresados a Fiscalía, víctimas de homicidio y procedimientos policiales son métricas distintas.
3. **AML por capas**: `base_19913`, `proxy_19913`, `crimen_organizado_proxy` y `contexto_general`.
4. **0 != sin dato**: la ausencia se representa como `null`/`no_disponible`, nunca como cero inventado.
5. **Geografía interoperable**: códigos y nombres normalizados de región/comuna preparados para cruces con SII/UAF/CGR.
6. **Histórico reproducible**: período objetivo 2020 a la fecha.

## Fuentes iniciales

- CEAD / Ministerio de Seguridad Pública: casos policiales, denuncias, detenciones, aprehendidos, frecuencia y tasa por 100.000 habitantes, región/comuna.
- Ministerio Público: boletines estadísticos SAF y Estadística Interactiva; backbone anual 2020-2025.
- Fiscalía Nacional / UCOD: informes de crimen organizado, drogas, armas, secuestros, extorsiones, trata y lavado de activos.
- Centro para la Prevención de Homicidios y Delitos Violentos: cifra oficial de víctimas de homicidio consumado.
- Carabineros de Chile y PDI: cuentas públicas, balances, procedimientos e incautaciones publicadas.
- SENDA: contexto de mercados de drogas y consumo.
- Servicio Nacional de Aduanas: contrabando, decomisos y fiscalización.
- BCN LeyChile: versión vigente de Ley 19.913 para versionar el mapeo de delitos base.

Ver `config/sources.json` y `docs/data_model.md`.

## Arquitectura

```text
.github/workflows/     actualización, tests y GitHub Pages
config/                fuentes y taxonomía AML
data/raw/               copias de trabajo (no se versionan archivos pesados)
data/processed/         métricas normalizadas generadas
data/evidence/          evidencia y trazabilidad
radar_delictual/        colectores, normalización, AML, riesgo, dashboard
schemas/                contratos de datos
tests/                  pruebas unitarias
public/                 sitio estático generado
run.py                  ejecución integral
```

## Ejecución local

```bash
python -m pip install -r requirements.txt
python run.py
pytest -q
```

Para ejecutar sin red y regenerar el dashboard con el último dato disponible:

```bash
python run.py --offline
```

## Salidas principales

- `data/processed/territorial_metrics.jsonl`
- `data/processed/risk_signals.json`
- `data/processed/osint_events.jsonl`
- `data/evidence/source_evidence.jsonl`
- `data/processed/source_status.json`
- `public/index.html`
- `public/data.json`

## Score v0.1

El índice principal se denomina **Presión delictual AML (proxy)**, no “riesgo LA/FT”. Se calcula separando:

- presión de delitos base/proxy Ley 19.913;
- presión de mercados de crimen organizado;
- tendencia reciente;
- diversificación de señales.

Mientras no exista una tasa territorial comparable para una fuente, el motor evita presentar el resultado como tasa de criminalidad o probabilidad de lavado.

## Automatización

GitHub Actions ejecuta el radar diariamente alrededor de las 07:10 hora de Santiago, además de cada `push` y ejecución manual. El dashboard se publica mediante GitHub Pages y la última salida generada se conserva en la rama técnica `radar-data`, evitando conflictos con `main`.

## Próximas capas previstas

- Ingesta automatizada completa de CEAD a nivel comunal y tasas por 100.000.
- Catálogo de delitos del Ministerio Público a nivel de código para mapear artículo 27 de Ley 19.913 sin depender de categorías amplias.
- Incautaciones/procedimientos de drogas, armas, contrabando y vehículos.
- Matriz `territorio × actividad SII × sujeto obligado UAF × señal delictual`.
- Cruce con proveedores/organismos de Radar CGR y personas jurídicas de Radar SII mediante identificadores estables, sin inferir culpabilidad.

## Advertencia metodológica

Este repositorio es una herramienta OSINT de apoyo analítico. Los scores son señales para priorizar análisis y deben ser corroborados con la fuente original y con contexto territorial, demográfico, económico y temporal. No sustituyen una investigación penal, un ROS, una evaluación formal de riesgo ni una conclusión sobre una persona natural o jurídica.
