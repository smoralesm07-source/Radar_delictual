# Especificación de extracto SAF para piloto territorial AML

## Propósito

Obtener una tabla estadística agregada del Ministerio Público para evaluar experimentalmente amenaza patrimonial/financiera territorial relevante para LA, sin datos personales y sin modificar IGR o Atlas.

## Cobertura solicitada

- Período: 2020-01-01 a 2025-12-31.
- Unidad territorial: comuna de ocurrencia del delito.
- Unidad de conteo: identificador único de delito (`ID_delito`), sin duplicar un delito por aparecer en más de una relación.
- Conservar dos ejes temporales cuando estén disponibles: **fecha de recepción del caso** y **fecha de ocurrencia del delito**.
- La fecha de recepción se usará para reconciliar con las Estadísticas Interactivas oficiales; la fecha de ocurrencia se evaluará como eje analítico potencial para amenaza territorial.
- Salida agregada: una fila por período, comuna y código de delito.

## Campos mínimos

1. `anio_recepcion`
2. `mes_recepcion` (deseable)
3. `anio_ocurrencia` (deseable y de alta prioridad)
4. `mes_ocurrencia` (deseable)
5. `codigo_delito`
6. `nombre_delito`
7. `codigo_comuna_ocurrencia` (CUT si está disponible)
8. `nombre_comuna_ocurrencia`
9. `cantidad_delitos_ingresados`

## Campos opcionales de control

- `region_ocurrencia`
- `region_fiscalia`
- `fiscalia_local`
- `tipo_imputado` agregado (`conocido` / `desconocido`)
- marca de registros sin dirección/comuna de ocurrencia

## Exclusiones de datos

No se solicitan RUC, ID_delito individual, RUT, identificadores de imputados o víctimas, nombres de personas, direcciones completas, coordenadas precisas, relatos ni antecedentes de causa.

## Delitos núcleo E1

- 816 · Estafas y otras defraudaciones contra particulares.
- Uso malicioso de tarjeta, clave o dispositivo financiero, art. 7 Ley 20.009 (usar el código SAF vigente correspondiente y conservar su historial de vigencia).
- 856 · Apropiación indebida.
- 863 · Administración desleal de persona natural.
- 865 · Administración desleal de persona jurídica.
- 866 · Apropiación indebida por persona jurídica.
- 845 · Fraude de subvenciones.

Solicitar además el catálogo/código vigente por año para poder detectar altas, bajas o recodificaciones.

## Reglas metodológicas

- Si un `ID_delito` está asociado a múltiples relaciones, contabilizarlo una sola vez.
- La comuna debe corresponder al lugar/dirección de ocurrencia registrada para el delito/caso, no a la ubicación de la Fiscalía que lo tramita.
- Registros sin comuna deben quedar identificados como `sin_comuna` y no imputarse a una comuna por inferencia.
- No convertir ausencia de registros en cero sin comprobar cobertura.
- 2026 debe tratarse como YTD separado hasta contar con año completo.
- Para Ley 20.009, marcar ruptura estructural desde 2024 por modificación legal y cambios en el proceso de denuncia.
- Si existe discrepancia entre año de recepción y año de ocurrencia, conservar ambos; no reasignar artificialmente uno al otro.

## QA de recepción

Al recibir el extracto se validará cobertura comunal >=95% para aspirar a piloto comunal, totales por año y delito contra publicaciones oficiales, coherencia CUT/nombre de comuna, duplicados en clave territorial-temporal, códigos no vigentes o recodificados, porcentaje `sin_comuna`, diferencias entre fecha de recepción y fecha de ocurrencia, y saltos estructurales por cambio normativo o de clasificación.

## Salida esperada del laboratorio

El dataset normalizado quedará con estado `research_only`. No será consumido por IGR, Radar productivo ni Atlas. Su primera finalidad es responder si la información del Ministerio Público aporta señal territorial nueva respecto del IGR 1.1 y si esa señal es suficientemente estable para justificar una etapa posterior de backtesting.
