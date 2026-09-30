# Especificación de extracto SAF para piloto territorial AML

## Propósito

Obtener una tabla estadística agregada del Ministerio Público para evaluar experimentalmente amenaza patrimonial/financiera territorial relevante para LA, sin datos personales y sin modificar IGR o Atlas.

## Cobertura solicitada

- Período: 2020-01-01 a 2025-12-31.
- Unidad territorial: comuna de ocurrencia del delito.
- Unidad de conteo: identificador único de delito (`ID_delito`), sin duplicar un delito por aparecer en más de una relación.
- Período de contabilización: fecha de recepción del caso, en concordancia con la metodología pública de `Delitos ingresados`.
- Salida agregada: una fila por año/mes, comuna y código de delito.

## Campos mínimos

1. `anio_recepcion`
2. `mes_recepcion` (deseable; si no es posible, año basta para primera prueba)
3. `codigo_delito`
4. `nombre_delito`
5. `codigo_comuna_ocurrencia` (CUT si está disponible)
6. `nombre_comuna_ocurrencia`
7. `cantidad_delitos_ingresados`

## Campos opcionales de control

- `region_ocurrencia`
- `region_fiscalia`
- `fiscalia_local`
- `tipo_imputado` agregado (`conocido` / `desconocido`)
- marca de registros sin dirección/comuna de ocurrencia

## Exclusiones de datos

No se solicitan:

- RUC;
- ID_delito individual;
- RUT o identificadores de imputados/víctimas;
- nombres de personas;
- direcciones completas;
- coordenadas precisas;
- relatos o antecedentes de causa.

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

## QA de recepción

Al recibir el extracto se validará:

- cobertura comunal >=95% para aspirar a piloto comunal;
- totales por año y delito contra publicaciones oficiales;
- coherencia de CUT/nombre de comuna;
- duplicados en clave `periodo + comuna + codigo_delito`;
- códigos no vigentes o recodificados;
- porcentaje de `sin_comuna` por año y delito;
- saltos estructurales por cambio normativo o de clasificación.

## Salida esperada del laboratorio

El dataset normalizado quedará con estado `research_only`. No será consumido por IGR, Radar productivo ni Atlas. Su primera finalidad es responder si la información del Ministerio Público aporta señal territorial nueva respecto del IGR 1.1 y si esa señal es suficientemente estable para justificar una etapa posterior de backtesting.
