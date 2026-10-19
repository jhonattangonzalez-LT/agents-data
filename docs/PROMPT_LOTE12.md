Trabajo nuevo: **L12.2**. Eres el coordinador (CLAUDE.md). Es la revalidación completa del lote 12 (15 flujos) en
formato 2. No retomes `trabajos/L12` ni `trabajos/L12-insumos`: son del 2026-10-06, anteriores al formato 2
(`pc v4 incompletos --trabajo L12` da INCOMPLETO en 51 archivos); úsalos solo como antecedente de lectura.
No toques `trabajos/L8.2`, `L11-*` ni `L10-1`.

## Qué quiero al final
Cada flujo con su cotejo de flujo y su cotejo por tabla en formato 2, completos y publicados, y cada diferencia
explicada con cifras de los dos lados y ejemplo. Prefiero un flujo honestamente «en revisión» o «devuelto» a uno
aprobado con un dato sin medir. Entregables: `~/Projects/reportes/Lote12_<fecha>.md` (documento vivo) y, cuando yo
cierre las decisiones, el acta 12 (solo lo aprobado).

## Flujos (15) · regístralos tal cual; confirma cada ruta con `pc roles --flujo F` y dime cuál no coincide
Las rutas de Fabric las propuso el coordinador del 06-10 desde el código (load.py): **confírmalas**. Postgres de
Fabric solo por el agente postgres-fabric. En las Postgres el nombre es el mismo a cada lado (`esquema.tabla`).

| FL | Flujo en Fabric | Flujo en Stratio | Grupo | Tabla (clave) | Ruta Stratio | Ruta Fabric |
|---|---|---|---|---|---|---|
| FL-0407 | td_fosfec_estadoPostulaciones_05 | 05-td-fosfec-estadopostulaciones | analitica | servicios_postulaciones_himalia | hdfs:/data/prod/trusted/servicios/postulaciones_himalia | silver.servicios_postulaciones_himalia |
| | | | | pg_cliente_estadopostulaciones | pg:Cliente.EstadoPostulaciones | pgfab:Cliente.EstadoPostulaciones |
| | | | | pg_corporativo_fosfec_novedades | pg:corporativo.fosfec_novedades | pgfab:corporativo.fosfec_novedades |
| FL-0490 | trusted_datamart_credito_niveles_fact | 06-trusted-datamart-credito-niveles(fact) | analitica | credito_niveles_historico | hdfs:/data/prod/trusted/credito/tablas_finales/niveles_historico | silver.credito_tablas_finales_niveles_historico |
| FL-0703 | moves_fotos | 03-moves (fotos) | analitica · orquestador orq_agrupadoras_fotos | agrupadoras_fotos_historico_movimiento_alt | hdfs:/data/prod/trusted/agrupadoras/fotos/historico_movimiento_alt | silver.agrupadoras_fotos_historico_movimiento_alt |
| | | | | agrupadoras_fotos_moves_agrup | hdfs:/data/prod/trusted/agrupadoras/fotos/moves_agrup | silver.agrupadoras_fotos_moves_agrup |
| | | | | agrupadoras_fotos_historico_movimiento2 | hdfs:/data/prod/trusted/agrupadoras/fotos/historico_movimiento2 (1.248 archivos, 16,3 GB: grande) | silver.agrupadoras_fotos_historico_movimiento2 |
| FL-0707 | info_salarial_fotos | 06-info-salarial (fotos) | analitica · orquestador orq_agrupadoras_fotos | agrupadoras_fotos_ingresos | hdfs:/data/prod/trusted/agrupadoras/fotos/ingresos | silver.agrupadoras_fotos_ingresos |
| | | | | agrupadoras_fotos_variacion_salarial | hdfs:/data/prod/trusted/agrupadoras/fotos/variacion_salarial | silver.agrupadoras_fotos_variacion_salarial |
| FL-0329 | familiar_recurrente_fecha | 02a-tableros-giass-familiarrecurrente_fecha | orquestador (TRIGGER, no escribe datos) | — | — | — (validar ejecución y que dispare grupo_familiar_recurrente, FL-0716 probable: confirmar) |
| FL-0385 | riesgos_token_otp | 29-riesgos-token_otp | analitica | corporativo_token_otp | hdfs:/data/prod/surface/corporativo/token_otp | silver.corporativo_token_otp |
| | | | | pg_corporativo_token_otp | pg:corporativo.token_otp | pgfab:corporativo.token_otp |
| FL-0401 | presupuesto_vs_real | presupuesto_vs_real | analitica | pg_corporativo_comparativa_presupuesto_aportes | pg:corporativo.comparativa_presupuesto_aportes | pgfab:corporativo.comparativa_presupuesto_aportes |
| | | | | pg_corporativo_reporte_aportes_pivot5 | pg:corporativo.reporte_aportes_pivot5 | pgfab:corporativo.reporte_aportes_pivot5 |
| FL-0403 | tablas_auxiliares_aportes | tablas-auxiliares-aportes | analitica | 10 tablas `pg_corporativo_reporte_aportes_pivot_{1,2,3,4,6,atrasado,adelantado,composicion,empresa_size,empresas_nuevas}` | pg:corporativo.reporte_aportes_pivot_<x> | pgfab:corporativo.reporte_aportes_pivot_<x> |
| FL-0409 | td_fosfec_postulaciones_aceptadas_07 | 07-td-fosfec-postulacionesaceptadas | analitica | pg_public_postulacionesaceptadas | pg:public.postulacionesAceptadas | pgfab:public.postulacionesAceptadas |
| FL-0416 | ra2_inspektor_afiliaciones_17 | 17-ra2-inspektor-afiliaciones | analitica | pg_corporativo_rep_afiliaciones_2_inspektor | pg:corporativo.rep_afiliaciones_2_Inspektor | pgfab:corporativo.rep_afiliaciones_2_Inspektor |
| FL-0442 | subsidio_en_especie_aforo | 35-subsidio-en-especie-aforo | analitica | pg_corporativo_subsidio_especie_aforo | pg:corporativo.subsidio_especie_aforo | pgfab:corporativo.subsidio_especie_aforo |
| FL-0521 | fomento_full | 01-fomento-full | analitica | fomento_cesantes · fomento_formaciones · fomento_orientados · fomento_talleres | hdfs:/data/prod/trusted/fomento/{CESANTES,FORMACIONES,ORIENTADOS,TALLERES} | silver.fomento_full_{cesantes,formaciones,orientados,talleres} |
| | | | | pg_fomento_{cesantes,formaciones,fosfec,orientados,talleres,validacioncitas} | pg:Fomento.{CESANTES,FORMACIONES,fosfec,ORIENTADOS,TALLERES,VALIDACIONCITAS} | pgfab: las mismas |
| | | | | pg_prueba_pdl | pg:prueba.pdl (esquema de prueba) | NO existe en Fabric: confirmar conmigo si debe migrarse |
| FL-0590 | ventas | 09_ventas | orquestador (decide por ejecución) | — | sin salida productiva en Stratio (solo un log temporal inexistente) | silver.familias_ventas (por indicación de QA 06-10 se valida solo por ejecución) |
| FL-0632 | limpieza_remediacion_tipo_documento | limpieza_remediacion_tipo_documento | analitica | sap_crm_contactabilidad_tipo_documento | hdfs:/data/prod/trusted/sap/crm/contactabilidad/TIPO_DOCUMENTO | silver.sap_crm_contactabilidad_tipo_documento |
| FL-0472 | model_excecution | 01-model-excecution | orquestador (TRIGGER) | — | — | — (llama la API de agrupadoras; validar que corran FL-0473 agrupadoras_trusted_empresasactivas y FL-0474 score_agrupadoras_activas_postgres) |

Total: 15 flujos · 36 tablas (11 Delta/HDFS, 25 Postgres; 1 sin lado Fabric).

## Antecedente del 2026-10-06 (trabajo L12, formato anterior): NO es resultado, es pista de dónde mirar
Todo debe volver a medirse sobre la corrida de hoy; si una cifra ya no se reproduce, dilo.

| FL | Corrida 06-10 | Qué se vio | Estado que quedó |
|---|---|---|---|
| FL-0632 | Completed 222 s | solo difiere `Fecha_carga` (fecha de ejecución) | APROBADO_CON_JUSTIFICACION (expediente v1) |
| FL-0590 | Completed 217 s | sin Stratio; salida silver.familias_ventas con commit en la corrida, 545.820 filas | APROBADO por ejecución (expediente v1) |
| FL-0329 | Completed 172 s | trigger; falta confirmar el disparo | APROBADO por ejecución (expediente v1) |
| FL-0442 | Completed 337 s | solo corte de entradas | APROBADO_CON_JUSTIFICACION (expediente v1) |
| FL-0385 | Completed 564 s | corte + 77.289 duplicados del bronze no depurados | EN_REVISION (2 dif. pendientes por tabla) |
| FL-0409 | Completed 227 s | ventanas sin solape (entradas del 17-09) + ruptura de tipos | EN_REVISION (1 VG-09 pendiente) |
| FL-0416 | Completed 236 s | Stratio congelado desde 2025-12-12; documento del titular nulo en Fabric; tipos | EN_REVISION (6 pendientes) |
| FL-0407 | Completed 527 s | columnas corridas, 30 columnas 100 % nulas, fecha de radicación errada; 26.786 filas solo Stratio sin explicar | EN_REVISION, propuesta DEVUELTO |
| FL-0490 | Completed 186 s | 100 % SIN_CATEGORIA por el insumo `prestamo`; histórico no migrado | EN_REVISION, propuesta DEVUELTO |
| FL-0703 | Completed 1.052 s | Fabric pierde 26–28 % de la historia de la foto | EN_REVISION |
| FL-0707 | Completed 233 s | diferencias de valor sin causa medida | EN_REVISION |
| FL-0401 | **Failed** 428 s | nunca ha corrido en Fabric (falla 20-09 y 06-10) | DEVUELTO |
| FL-0403 | **Failed** 646 s | nunca ha corrido en Fabric | DEVUELTO |
| FL-0521 | Completed 492 s | tablas silver creadas ese día (v0); ~1 % menos filas, columnas faltantes, tipos; prueba.pdl no migrada | EN_REVISION |
| FL-0472 | sin objeto ejecutable en QA | el score se encadena por orquestador | DEVUELTO / A_VERIFICAR |

Diagnóstico aparte (`L12-insumos`, no entregable): entradas de las fotos `agrupadoras_fotos_origenes` y
`agrupadoras_fotos_last_partner` (hdfs:/data/prod/trusted/agrupadoras/fotos/{origenes,last_partner} ↔
silver.agrupadoras_fotos_{origenes,last_partner}); misma foto 202509 en los dos lados. Vuelve a medirlas si la
causa de FL-0703/FL-0707 depende de ellas.

Hallazgos de hoy (L8.2, 08-10) que afectan a este lote, para que los midas, no para que los asumas:
- `silver.credito_tablas_finales_prestamo` de Fabric (v6) no tiene desembolsos de septiembre 2026 y le faltan 495
  créditos; la cartera llega al 2026-08-31 → relevante para FL-0490.
- `silver.mercadeo_transacciones_en_linea_ventas` se re-ejecutó hoy 04:38 UTC (57.646.470 filas; `medio_Pago`
  sin 2023 porque medios_pago de Fabric empieza 2024-01-01) → entrada de FL-0590.
- `silver.subsidios_subsidio` y `silver.servicios_pila` de Fabric son del 2026-09-29 → mira si alguna entrada de
  FL-0442, FL-0407 o FL-0409 depende de ellas.

## Plan de ejecución (muéstramelo ordenado y espera mi «sí»)
Nada corre en paralelo en Fabric: cada paso espera al anterior.
1. FL-0401 y FL-0403: comprueba primero en Fabric si desarrollo ya los corrigió (última corrida y su estado). Si
   siguen fallando, se devuelven con el error exacto y no se mide nada.
2. FL-0472: comprueba si ya existe el ejecutable en QA. Si no, queda devuelto/por verificar con ese dato.
3. Triggers y por ejecución: FL-0329, FL-0590.
4. Analíticos sueltos: FL-0632, FL-0442, FL-0385, FL-0409, FL-0416, FL-0407, FL-0490, FL-0521.
5. Orquestador `orq_agrupadoras_fotos` una vez, y validar FL-0703 y FL-0707 sin re-ejecutarlos
   (`pc etl ejecutar --validar moves_fotos,info_salarial_fotos --orquestador orq_agrupadoras_fotos`).
Si al leer el código encuentras una entrada vacía o vieja, dímelo antes de ejecutar: decido yo si se corre su productor.

## Lecciones de L8.2 (aplícalas)
- Lanza los procesos largos con `setsid`/`nohup` y un log; mata solo por PID. La VPN se cae: la extracción de una
  Postgres de Stratio es un solo COPY y **no se reanuda**; para tablas grandes pártela por rangos y avísame antes.
- La máquina tiene 19 GB: tablas de más de 50 M de filas se miden de a un objeto (ver
  `trabajos/_sesion_2026-10-08/medir_ventas_1x1.sh`). A los cotejadores pásales límite de memoria (DuckDB ≤ 4 GB).
- Rocket (HDFS) necesita VPN y cookies (1 a 3; duran 2–3 h): pídemelas antes de descargar y prioriza Stratio
  mientras haya VPN. Avísame siempre tablas, MB y tiempo; las grandes solo con mi confirmación
  (`historico_movimiento2` son 16,3 GB).
- Un cotejador por tabla o por flujo, con el hallazgo a responder, y comprueba tú lo que devuelva. Que no dejen
  datos personales en el scratchpad; si bajan algo, que lo avisen antes.
- Mejoras M-010, M-011 y M-012 están en el código local sin compartir (commit + push pendiente): pregúntame.

## Lo que no se negocia
- Se valida la corrida que escribió el dato que se mide; re-ejecución = versión nueva.
- Advertencia en los dos lados o medición distinta = diferencia registrada con conteo exacto, ejemplo y causa.
- Comprobación del flujo que no cumple = flujo en revisión. `pc v4 incompletos` en COMPLETO antes de publicar.
- Las decisiones (justificar, verificar, devolver) son mías. Un defecto de código no se justifica.

## Qué me entregas
1. Por flujo: estado, corrida validada (hora y quién), comprobaciones que no cumplen y por qué.
2. Por tabla: resumen exacto y diferencias registradas con su propuesta.
3. Lo que no se pudo evaluar, dicho tal cual.
4. El expediente de decisión (`pc decision --trabajo L12.2`) para que yo decida una por una.
5. Enlaces: 1 por flujo y 3 por tabla. Y el Markdown `~/Projects/reportes/Lote12_<fecha>.md`.
