# IGR · fuentes experimentales fuera de producción

## Objetivo

Explorar fuentes que puedan ampliar, en una etapa posterior, la caracterización territorial relevante para LA/FT sin modificar el IGR productivo ni Atlas.

Esta investigación **no cambia pesos, fórmulas, datasets productivos ni salidas consumidas por Atlas**. Cualquier incorporación futura exige primero disponibilidad estable, granularidad territorial suficiente, serie temporal comparable, trazabilidad metodológica y backtesting.

## Capa E1 · fraude, estafa y delitos económicos/financieros

**Fuente prioritaria:** Ministerio Público de Chile.

### Evidencia de disponibilidad

- La Fiscalía mantiene una plataforma pública de **Estadísticas Interactivas** basada en el Sistema de Apoyo a los Fiscales (SAF).
- La metodología 2026 documenta descarga a Excel y construcción de tablas con filtros, filas y columnas configurables.
- La propia documentación muestra desagregaciones territoriales subregionales en consultas de ejemplo y una clasificación de delitos suficientemente granular para estudiar estafas, defraudaciones y delitos económicos/tributarios.
- Los boletines 2025-2026 destacan explícitamente `Estafas y otras defraudaciones contra particulares` y `Uso malicioso de tarjeta, clave o dispositivo financiero` como fenómenos de alta materialidad estadística.

### Variables candidatas

- delitos ingresados por territorio y periodo;
- estafas y otras defraudaciones contra particulares;
- uso malicioso de tarjeta, clave o dispositivo financiero;
- apropiación indebida;
- administración desleal;
- delitos tributarios/económicos seleccionados;
- tipo de imputado conocido/no conocido, solo como atributo contextual y nunca como riesgo por sí mismo.

### Estado

**Alta prioridad para piloto experimental.** La principal tarea pendiente es verificar de manera reproducible el nivel territorial más fino disponible en la descarga masiva y su estabilidad histórica antes de diseñar cualquier score.

## Capa E2 · corrupción

**Fuente prioritaria:** Ministerio Público.  
**Fuentes complementarias a evaluar:** Consejo de Defensa del Estado, Poder Judicial y Contraloría General de la República.

### Variables candidatas

- cohecho;
- soborno;
- malversación de caudales públicos;
- fraude al Fisco;
- negociación incompatible;
- delitos funcionarios relacionados.

### Consideraciones metodológicas

La baja frecuencia y alta complejidad investigativa hacen poco recomendable utilizar conteos anuales simples. Un eventual indicador debe probar ventanas plurianuales, persistencia, materialidad y estabilidad, evitando interpretar ausencia de causas como ausencia de riesgo.

### Estado

**Exploratorio.** Ministerio Público parece ser la fuente más prometedora para una primera prueba reproducible. Las demás fuentes se consideran de contraste o enriquecimiento y no deben incorporarse mientras no exista una extracción territorial estable.

## Capa E3 · contrabando y mercados ilícitos fronterizos

**Fuente prioritaria:** Servicio Nacional de Aduanas.

### Evidencia de disponibilidad

Aduanas publica resultados institucionales y balances de fiscalización con información sobre denuncias de contrabando, incautaciones, mercancías, drogas, cigarrillos, armas y propiedad intelectual. También existen resultados asociados a aduanas y puntos de control específicos.

### Variables candidatas

- número de procedimientos o denuncias por contrabando;
- valor de mercancía incautada;
- cajetillas de cigarrillos incautadas;
- drogas incautadas por tipo;
- armas/municiones incautadas;
- mercancía falsificada o infractora de propiedad intelectual;
- aduana/paso fronterizo/punto de control;
- periodo.

### Limitación principal

La información pública identificada no constituye todavía una base comunal longitudinal homogénea. Una aduana o paso fronterizo tampoco equivale necesariamente a la comuna donde se materializa el riesgo económico asociado.

### Estado

**Prometedor a nivel territorial funcional, no listo para IGR comunal.** Antes de construir una capa debe resolverse una unidad espacial coherente y una serie histórica estructurada.

## Capa E4 · señales de crimen organizado

**Enfoque recomendado:** señal compuesta, no una variable `crimen_organizado = casos`.

El fenómeno debe estudiarse por convergencia de mercados y facilitadores, por ejemplo:

- narcotráfico;
- armas;
- homicidios y violencia grave vinculada;
- secuestros;
- robo violento de vehículos;
- contrabando;
- trata de personas y tráfico ilícito de migrantes;
- fraude organizado;
- mercados ilícitos específicos.

La documentación oficial sobre crimen organizado reconoce expresamente la naturaleza multifenómeno y la relevancia de mercados ilícitos, frontera y corrupción. También advierte que determinadas dimensiones, como control territorial, todavía no cuentan con mediciones nacionales suficientemente consolidadas.

### Estado

**No construir score todavía.** Primero levantar un catálogo de señales observables, su unidad territorial, temporalidad y fuente primaria. Solo después evaluar un indicador independiente (por ejemplo, un futuro ICO) y recién entonces medir su relación empírica con IGR.

## Reglas de promoción a piloto

Una fuente experimental solo puede pasar a construcción de dataset si cumple simultáneamente:

1. fuente oficial o trazable;
2. extracción reproducible;
3. definición estable de categorías;
4. serie temporal mínima suficiente para persistencia/tendencia;
5. territorio comparable o geocodificable sin inferencias débiles;
6. ausencia no interpretada como cero;
7. documentación de cambios de clasificación;
8. validación separada del IGR productivo;
9. backtest antes de cualquier ponderación;
10. ninguna dependencia de Atlas para ejecutar la prueba.

## Orden de trabajo propuesto

1. **CEAD ampliado:** agotar recuperación de categorías ya definidas en su catálogo, manteniendo el backbone productivo sin cambios.
2. **Ministerio Público:** construir un piloto descargable para fraude/estafa y delitos económicos, idealmente 2020-2026.
3. **Aduanas:** evaluar si es posible formar una serie estructurada por aduana/paso/territorio y año.
4. **Corrupción:** piloto plurianual solo después de verificar granularidad y estabilidad.
5. **Crimen organizado:** catálogo de señales y convergencias; sin score en esta etapa.

## Principio rector

Estas capas son **experimentales y externas al IGR vigente**. El IGR 1.1 continúa siendo la referencia productiva hasta que una fuente candidata demuestre, con evidencia empírica, que agrega señal útil sin introducir sesgos, duplicaciones ni inestabilidad territorial.
