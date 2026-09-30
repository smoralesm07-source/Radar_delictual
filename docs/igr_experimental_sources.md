# IGR · fuentes experimentales fuera de producción

## Objetivo

Explorar fuentes del Ministerio Público que puedan ampliar, en una etapa posterior, la caracterización territorial relevante para LA/FT sin modificar el IGR productivo ni Atlas.

Esta investigación **no cambia pesos, fórmulas, datasets productivos ni salidas consumidas por Atlas**. SIED queda fuera de alcance por ahora. Cualquier incorporación futura exige disponibilidad estable, granularidad territorial suficiente, serie temporal comparable, trazabilidad metodológica y backtesting.

## Hallazgo principal: el SAF sí contiene geografía de ocurrencia

La limitación de la interfaz pública no implica una limitación del SAF. Documentos oficiales del Ministerio Público muestran que el SAF ha sido explotado con `dirección de ocurrencia del delito` y posteriormente geocodificado para análisis territorial. Informes estadísticos institucionales también han publicado resultados por `comuna del delito`.

Por tanto, el problema queda reformulado:

- **Power BI público:** útil para taxonomía, series y validación regional; la metodología pública solo confirma selección de regiones y no acredita una dimensión comunal descargable.
- **SAF:** contiene información de ocurrencia suficiente para construir una extracción comunal, pero esa dimensión no está confirmada como salida pública estándar.
- **Decisión metodológica:** no sustituir comuna de ocurrencia con Región Fiscalía ni Fiscalía Local.

La vía prioritaria para resolver E1 es obtener un extracto agregado SAF por **comuna de ocurrencia × código de delito × período**. Esta es una extracción estadística agregada; no requiere datos personales ni RUC individuales para el propósito territorial.

## Capa E1 · fraude, estafa y delitos económicos/financieros

**Fuente prioritaria:** Ministerio Público de Chile.  
**Sistema fuente:** SAF.  
**Interfaz pública de contraste:** Estadísticas Interactivas / Power BI.

### Unidad de conteo

Debe utilizarse **Delitos ingresados**, cuya unidad es el identificador único de delito. No utilizar número de RUC como sustituto, porque un caso puede contener uno o más delitos.

Para delitos ingresados, el período público se define por la fecha de recepción del caso. El piloto conservará esa convención para ser comparable con las estadísticas institucionales, aunque la fecha de ocurrencia pueda existir como atributo del delito.

### Territorio

Orden de preferencia:

1. `comuna de ocurrencia del delito` / comuna derivada de la dirección de ocurrencia registrada en SAF;
2. región de ocurrencia, solo para validación agregada;
3. Región Fiscalía o Fiscalía Local, solo como atributos de gestión y **nunca** como proxy automático de comuna.

Un extracto que solo tenga Región Fiscalía puede alimentar un laboratorio regional, pero no puede ser candidato a IGR comunal.

### Taxonomía E1

**Núcleo:**
- 816 · Estafas y otras defraudaciones contra particulares;
- Uso malicioso de tarjeta, clave o dispositivo financiero, art. 7 Ley 20.009.

**Extensión económica/financiera:**
- 856 · Apropiación indebida art. 470 N°1;
- 863 · Administración desleal de persona natural art. 470 N°11;
- 865 · Administración desleal de persona jurídica art. 470 N°11;
- 866 · Apropiación indebida cometida por persona jurídica;
- 845 · Fraude de subvenciones;
- delitos tributarios/económicos adicionales solo después de revisión jurídica y de estabilidad de código.

No utilizar directamente la macro categoría `Delitos económicos y tributarios` como señal. La capa debe conservar código de delito y construir familias analíticas explícitas.

### Ruptura estructural en fraude financiero

La serie de `Uso malicioso de tarjeta, clave o dispositivo financiero` requiere tratamiento especial por el cambio normativo introducido por Ley 21.673 durante 2024, que alteró incentivos/requisitos de denuncia.

Reglas:
- `structural_break = 2024`;
- no interpretar el salto 2024-2025 como tendencia criminal pura;
- estimar nivel reciente y tendencia histórica por separado;
- comparar resultados E1 con y sin esta categoría;
- impedir que una alteración de registro domine la capa experimental.

## Contrato de datos solicitado al Ministerio Público

Granularidad mínima deseada:

`anio | mes(opcional) | codigo_delito | nombre_delito | comuna_ocurrencia_codigo | comuna_ocurrencia_nombre | delitos_ingresados`

Campos opcionales útiles:

`region_ocurrencia | region_fiscalia | fiscalia_local | tipo_imputado_conocido_desconocido`

No se requieren nombres, RUT, direcciones completas, RUC ni identificadores personales. El objetivo es una tabla agregada estadística.

Cobertura temporal inicial: **2020-2025 completos**, manteniendo 2026 YTD separado para no mezclar períodos incompletos.

## Criterio de éxito del piloto

El extracto será `communal_candidate` solo si:

- al menos 95% de las filas tienen comuna de ocurrencia válida;
- existe una serie de al menos cuatro años comparables;
- cada registro conserva código de delito trazable;
- las ausencias se distinguen de ceros observados;
- se documentan cambios legales/taxonómicos;
- los agregados nacionales/regionales cuadran razonablemente con publicaciones oficiales.

Incluso cumpliendo estas reglas, el extracto permanece **fuera del IGR** hasta ejecutar backtest.

## Validaciones propuestas

1. reconciliar suma comunal con total regional/nacional publicado por Fiscalía;
2. medir porcentaje de registros sin comuna de ocurrencia;
3. comprobar estabilidad de códigos entre años;
4. construir perfiles por 100 mil habitantes e intensidad absoluta por separado;
5. evaluar persistencia, tendencia y anomalía sin copiar automáticamente la fórmula IGR;
6. probar E1 con y sin fraude Ley 20.009;
7. medir correlación y señal incremental respecto de IGR 1.1;
8. identificar comunas cuyo cambio proviene de señal financiera y no de volumen general delictual.

## Capa E2 · corrupción

Se mantiene en espera hasta validar la infraestructura E1. El catálogo SAF permite estudiar malversación, cohecho/soborno, negociación incompatible, tráfico de influencias, enriquecimiento ilícito y fraude al Fisco, entre otros. Por su baja frecuencia, cualquier piloto posterior deberá utilizar ventanas plurianuales y estabilización.

## Decisión vigente

**Toda la investigación inmediata se concentra en Ministerio Público/SAF. SIED no se utilizará en esta fase.**

La hipótesis a probar ya no es si el Ministerio Público posee geografía comunal: existe evidencia institucional de que SAF registra dirección/comuna de ocurrencia. La tarea es obtener esa dimensión en un extracto agregado, reproducible y suficientemente completo para E1.

## Principio rector

IGR 1.1 y Atlas permanecen sin cambios. El laboratorio Ministerio Público se ejecuta en forma separada y solo podrá proponer una futura incorporación después de demostrar cobertura territorial, consistencia temporal, señal incremental y estabilidad metodológica.
