# IGR · fuentes experimentales fuera de producción

## Objetivo

Explorar fuentes que puedan ampliar, en una etapa posterior, la caracterización territorial relevante para LA/FT sin modificar el IGR productivo ni Atlas.

Esta investigación **no cambia pesos, fórmulas, datasets productivos ni salidas consumidas por Atlas**. Cualquier incorporación futura exige primero disponibilidad estable, granularidad territorial suficiente, serie temporal comparable, trazabilidad metodológica y backtesting.

## Capa E1 · fraude, estafa y delitos económicos/financieros

**Fuente prioritaria:** Ministerio Público de Chile.  
**Sistema fuente:** SAF.  
**Interfaz pública:** Estadísticas Interactivas / Power BI.

### Diagnóstico exhaustivo de la fuente

La Fiscalía publica Estadísticas Interactivas con actualización diaria y permite descargar consultas a Excel después de seleccionar temática, filtros, filas y columnas. Metodológicamente distingue claramente los ámbitos **Casos**, **Delitos** y **Relaciones**. Para una señal territorial de amenaza delictual, el ámbito correcto es **Delitos ingresados**, cuya unidad de conteo es el identificador único de delito. No debe usarse el número de RUC como sustituto, porque un caso puede contener uno o más delitos.

La metodología pública establece que el período de los delitos ingresados se determina por la **fecha de recepción del caso** y que la cobertura de la consulta considera la o las **regiones seleccionadas**. En la interfaz documentada el filtro territorial visible es `Región Fiscalía`. Por ahora, la documentación pública revisada **no confirma que comuna o lugar de ocurrencia sea una dimensión descargable en el Power BI**.

Esto es decisivo: `Región Fiscalía` o una eventual `Fiscalía Local` no deben transformarse mecánicamente en comuna de ocurrencia. Una fiscalía es una unidad de persecución/gestión y puede conocer hechos ocurridos fuera de una correspondencia comunal uno-a-uno. Para una eventual incorporación al IGR comunal necesitamos **territorio de ocurrencia** o una variable geográfica equivalente, no solo unidad prosecutora.

### Taxonomía: muy buena para AML

El catálogo penal a diciembre de 2025 confirma una granularidad considerable. Para un primer piloto se proponen dos niveles:

**Núcleo de alta materialidad:**
- código 816 · Estafas y otras defraudaciones contra particulares;
- Uso malicioso de tarjeta, clave o dispositivo financiero, art. 7 Ley 20.009.

**Extensión económica/financiera:**
- 856 · Apropiación indebida art. 470 N°1;
- 863 · Administración desleal de persona natural art. 470 N°11;
- 865 · Administración desleal de persona jurídica art. 470 N°11;
- 866 · Apropiación indebida cometida por persona jurídica;
- 845 · Fraude de subvenciones;
- 5001 · delitos del Código Tributario, sujeto a revisión jurídica más fina.

La categoría `Delitos económicos y tributarios` es demasiado amplia para usarla directamente como señal IGR. El piloto debe conservar **código de delito** y construir familias analíticas explícitas.

### Ruptura estructural 2024-2025

La Fiscalía ha advertido que el fuerte aumento de `Uso malicioso de tarjeta, clave o dispositivo financiero` está influido por la Ley 21.673, que desde 2024 modificó requisitos asociados a denuncias por operaciones reclamadas. Por lo tanto, una serie temporal bruta puede mostrar una falsa aceleración de amenaza si se interpreta sin controlar este cambio normativo.

Regla experimental:
- no unir automáticamente la serie pre y post cambio legal;
- marcar `structural_break = 2024` para esta categoría;
- evaluar nivel e intensidad recientes por separado de tendencia histórica;
- no dejar que esta categoría domine una eventual capa solo por cambio de registro/denuncia.

### Piloto propuesto

Dataset objetivo, separado de producción:

`anio | periodo | codigo_delito | nombre_delito | familia_experimental | territorio | nivel_territorial | delitos_ingresados | tipo_imputado | fuente | fecha_extraccion | observaciones_metodologicas`

Prioridades de validación:
1. verificar si la descarga Excel del Power BI permite territorio de ocurrencia inferior a región;
2. si solo entrega `Región Fiscalía`, construir únicamente un laboratorio regional y **no promoverlo al IGR comunal**;
3. comprobar disponibilidad histórica comparable al menos desde 2020;
4. conservar códigos vigentes/no vigentes para evitar quiebres artificiales de taxonomía;
5. medir concentración territorial, estabilidad interanual y sensibilidad a cambios normativos;
6. comparar con CEAD sin mezclar ambas fuentes ni duplicar hechos.

### Conclusión E1

**La fuente es muy atractiva por contenido y taxonomía, pero aún no está validada para el IGR comunal por granularidad territorial.** El próximo cuello de botella no es encontrar delitos relevantes: ya existen y están bien codificados. Es demostrar que podemos extraerlos con un territorio de ocurrencia compatible con comuna.

## Capa E2 · corrupción

**Fuente prioritaria:** Ministerio Público.

El catálogo vigente confirma, entre otros:
- 406 · Malversación de caudales públicos;
- 410 · Cohecho cometido por empleado público;
- 411 · Cohecho o soborno cometido por particular;
- 415 · Negociación incompatible;
- 416 · Tráfico de influencias;
- 418 · Enriquecimiento ilícito;
- 419 · Fraudes al Fisco y organismos del Estado;
- 422/423/424 · distintas figuras de soborno.

La taxonomía es suficiente para un laboratorio, pero la baja frecuencia vuelve poco razonable usar conteos anuales simples. Se propone ventana móvil plurianual, persistencia y estabilización. Igual que en E1, no debe utilizarse Región Fiscalía como proxy de lugar de ocurrencia.

**Estado:** taxonomía validada; granularidad territorial pendiente.

## Hallazgo complementario relevante: SIED/CEAD

La revisión detectó que el SIED Estadístico y el SIED Territorial permiten consultar casos policiales desde 2005, con cobertura regional, provincial y comunal; el SIED Territorial trabaja además con hechos georreferenciados. Existen planes comunales que utilizan datos de `estafas y otras defraudaciones` aportados por Fiscalía y/o visualizados territorialmente en SIED.

Esto abre una segunda vía que debemos investigar en paralelo: determinar si **SIED posee categorías económicas más amplias que las 45 categorías públicas actualmente explotadas por nuestro pipeline CEAD**. Si SIED permite extraer estafas u otros delitos económicos a nivel comunal de manera estable, podría resolver el problema territorial antes que el Power BI público de Fiscalía.

Esta vía queda como investigación de fuente, sin modificación del IGR.

## Capa E3 · contrabando y mercados ilícitos fronterizos

**Fuente prioritaria:** Servicio Nacional de Aduanas.

Variables candidatas: procedimientos/denuncias de contrabando, valor de mercancía incautada, cigarrillos, drogas, armas, mercancía falsificada y aduana/paso fronterizo.

La información pública identificada todavía no constituye una base comunal longitudinal homogénea. Una aduana o paso fronterizo tampoco equivale necesariamente a la comuna donde se materializa el riesgo económico asociado.

**Estado:** prometedor a nivel territorial funcional, no listo para IGR comunal.

## Capa E4 · señales de crimen organizado

No construir una variable `crimen_organizado = casos`. El fenómeno debe estudiarse mediante convergencia de narcotráfico, armas, violencia grave, secuestros, contrabando, trata, tráfico ilícito de migrantes, fraude organizado y mercados ilícitos específicos.

**Estado:** investigación; sin score.

## Reglas de promoción a piloto

Una fuente experimental solo puede avanzar si cumple simultáneamente:

1. fuente oficial o trazable;
2. extracción reproducible;
3. definición estable de categorías;
4. serie temporal suficiente;
5. **territorio de ocurrencia comparable**, no solo unidad administrativa de gestión;
6. ausencia nunca interpretada como cero;
7. control de cambios legales y taxonómicos;
8. validación separada del IGR productivo;
9. backtest antes de cualquier ponderación;
10. ninguna dependencia de Atlas para ejecutar la prueba.

## Orden de trabajo actualizado

1. **CEAD ampliado:** continuar agotando categorías ya definidas en catálogo.
2. **Ministerio Público E1:** probar descarga y granularidad efectiva para estafas/fraude financiero.
3. **SIED económico:** comprobar si ofrece estafas/delitos económicos con nivel comunal exportable.
4. Si E1 logra territorio compatible: construir dataset 2020-2026 y medir estabilidad.
5. **Corrupción:** usar la misma infraestructura solo después de resolver territorio.
6. **Aduanas:** evaluar unidad territorial funcional.
7. **Crimen organizado:** catálogo de señales, sin score.

## Principio rector

Estas capas son **experimentales y externas al IGR vigente**. El IGR 1.1 continúa siendo la referencia productiva hasta que una fuente candidata demuestre, con evidencia empírica, que agrega señal útil sin introducir sesgos, duplicaciones ni inestabilidad territorial.
