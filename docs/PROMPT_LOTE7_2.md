Trabajo nuevo: **L7.2** — re-prueba de las 56 tablas (46 flujos) marcadas 🔁 VOLVER A REALIZAR PRUEBA en el reporte 7.2 y respuesta a las 19 tablas «no justificadas en el acta» (documento `~/Projects/reportes/Hallazgos_Lote7.2.md`, ya guardado completo). Eres el coordinador (CLAUDE.md). El lote 7 se midió entre el 25 y el 30-09 con el formato anterior (reportes_v3, acta 7 v2.1) y no tiene trabajo propio en `trabajos/`; solo `origenes` (#1) y parte de la cadena de Agrupadoras se midieron después en formato 2 (sección «Ya medidos»). No toques `L8.2`, `L8.3`, `L9.2`, `L10-1`, `L11-*` ni `L12*` (solo lectura).

## Qué quiero al final
Cada flujo con su cotejo de flujo y sus cotejos de tabla en formato 2, completos y publicados, y **cada hallazgo # respondido con dato**: la columna «Prueba a realizar» ejecutada y la columna «Criterio para cerrar» evaluada tal como está escrita. En 50 de las 56 el problema es que «el acta no da la causa» («cargas de fechas distintas» sin demostrar, o «no se investigó fila a fila»): lo que se entrega esta vez es la **causa medida** (qué filas, por qué clave, de qué entrada o qué paso del código), o el hallazgo queda abierto diciendo qué falta y de quién depende. Prefiero un flujo devuelto con evidencia a uno aprobado «porque en analítica el conteo es informativo».

## Estado al escribir este prompt (2026-10-09 16:23 UTC)
- VPN arriba y sesión de Fabric iniciada. **Cookies de Rocket: 1 vigente de 2** (puesta 15:35 UTC, vence entre 17:35 y 18:35 UTC; la otra está vencida). Compruébalas con `pc stratio cookie` y `pc stratio vpn` al abrir y pídeme cookies nuevas antes de cualquier descarga de HDFS; avísame cuando queden menos de 15 min.
- Otros trabajos abiertos: `L8.3`, `L9.2`, `L12*`. Si hay otra sesión corriendo, comparten las cookies (8 hilos de Rocket en total) y la Postgres de Stratio (una sola cosa a la vez): dímelo antes de lanzar algo contra Stratio.
- Mejoras M-010 a M-013 SIN COMPARTIR (falta el push): pregúntame.

## Primer paso
1. Lee completo `~/Projects/reportes/Hallazgos_Lote7.2.md` (el documento del revisor, tal cual lo entregó).
2. Lee: `~/Projects/reportes/datos_acta_lote7.json` (acta 7 v2.1: de ahí salen las rutas de abajo y las justificaciones completas que en el .docx quedaron cortadas), `~/Projects/reportes/Links_Lote11_2026-10-07.md` y `Links_Lote6.2_2026-10-07.md` (cadena de Agrupadoras ya medida), `docs/RESUMEN_SESION_2026-10-06.md` (VBAP y fotos), `trabajos/_sesion_2026-10-08/RETOMAR.md` (lecciones de VPN y memoria), `.claude/agents/cotejador.md`, `pc/reportes/formato2.py`.
3. Lo de siempre: `pc mejora pendientes`, `fab auth status`, VPN y cookies de Rocket.
4. Antes de ejecutar nada, hazme una tabla, hallazgo por hallazgo: **# · tabla · prueba que pide el revisor · lo que ya está medido en formato 2 (trabajo, cifra, archivo) · lo que falta · última corrida en Fabric (estado, fecha, commit de la salida) y fecha del último dato en Stratio**. Con eso decido qué se re-ejecuta y qué se devuelve tal como está.

## Flujos (46) y tablas (56)
FL, nombres y rutas del acta 7 v2.1 (`pg:` = Postgres de Stratio; el lado Fabric de esas tablas es Delta en el lakehouse, salvo que `pc roles` diga que además hay Copy a Postgres: entonces solo por el agente postgres-fabric). **Confírmalas con `pc roles --flujo F`** antes de medir y dime cuál corriges y por qué. Las cifras de cada # están en el documento: son antecedente del 25 al 30-09, no resultado.

| # | FL | Flujo en Fabric | Flujo en Stratio | Tabla (clave) | Ruta Stratio | Ruta Fabric | Nota |
|---|---|---|---|---|---|---|---|
| 1 | FL-0464 | origenes | 00-origenes | `agrupadoras_origenes` | hdfs:/data/prod/trusted/agrupadoras/origenes (de `L11-complemento`) | silver.agrupadoras_origenes |  |
| 2 | FL-0394 | postulaciones_detalle_chequeo_fosfec_fovis | 48-postulaciones-detalle-chequeo-fosfec-fovis | `corporativo_fosfec_post_detalle_chequeo` | pg:corporativo.fosfec_post_detalle_chequeo | gold.corporativo_fosfec_post_detalle_chequeo |  |
| 3 | FL-0394 | postulaciones_detalle_chequeo_fosfec_fovis | 48-postulaciones-detalle-chequeo-fosfec-fovis | `corporativo_fovis_post_detalle_chequeo` | pg:corporativo.fovis_post_detalle_chequeo | gold.corporativo_fovis_post_detalle_chequeo |  |
| 4 | FL-0370 | tableros_vivienda_negocio_27 | 27-tableros-vivienda-negocio | `corporativo_vivienda_negocio` | pg:corporativo.vivienda_negocio | gold.corporativo_vivienda_negocio |  |
| 5 | FL-0418 | ra2_consulta_inspektor | 20-ra2-consulta-inspektor | `corporativo_inspektor_consulta` | pg:corporativo.inspektor_consulta | silver.corporativo_inspektor_consulta |  |
| 6 | FL-0434 | vivienda_reporte_acompaniamiento_02 | 02-vivienda-reporte-acompaniamiento | `corporativo_vivienda_acompanamiento_reporte` | pg:corporativo.vivienda_acompanamiento_reporte | gold.corporativo_vivienda_acompanamiento_reporte |  |
| 7 | FL-0533 | detalle_matriz_lealtad | 03-detalle_matriz_lealtad | `comercial_detalle_matriz_lealtad` | pg:Comercial.detalle_matriz_lealtad | gold.comercial_detalle_matriz_lealtad |  |
| 8 | FL-0534 | metas_puntos_corte_04 | 04-metas-puntos-corte | `comercial_puntos_corte_matriz_lealtad` | pg:Comercial.puntos_corte_matriz_lealtad | silver.comercial_puntos_corte_matriz_lealtad |  |
| 9 | FL-0355 | tableros_afiliados_pacs_04 | 04-tableros-afiliados-pacs | `corporativo_pacs` | pg:corporativo.pacs | silver.corporativo_pacs |  |
| 10 | FL-0361 | tableros_afiliados_trabajadores_fosfec_10 | 10-tableros-afiliados-trabajadores-fosfec | `cliente_afiliados_retirados_fosfec` | pg:Cliente.AfiliadosRetiradosFosfec | silver.cliente_afiliados_retirados_fosfec |  |
| 11 | FL-0414 | ra2_solicitudes_afiliaciones_sin_trazabilidad | 15-ra2-solicitudes-afiliaciones-(sin trazabilidad) | `corporativo_rep_afiliaciones_2_solicitudes_afiliaciones_st` | pg:corporativo.rep_afiliaciones_2_solicitudes_afiliaciones_st | silver.corporativo_rep_afiliaciones_2_solicitudes_afiliaciones_st |  |
| 12 | FL-0415 | ra2_consulta_afiliados_reporte_16 | 16-ra2-consulta-afiliados-reporte | `corporativo_rep_afiliaciones_2_consulta_afiliados` | pg:corporativo.rep_afiliaciones_2_consulta_afiliados | gold.corporativo_rep_afiliaciones_2_consulta_afiliados |  |
| 13 | FL-0419 | ra2_consulta_afiliados_beneficiarios_sin_info_contacto | 21-ra2-consulta-afiliados-beneficiarios-sin-info-contacto | `corporativo_rep_afiliaciones_2_consulta_afiliados_sin_info_contacto` | pg:corporativo.rep_afiliaciones_2_consulta_afiliados_sin_info_contacto | silver.corporativo_rep_afiliaciones_2_consulta_afiliados_sin_info_contacto |  |
| 14 | FL-0424 | ra2_reporte_historico_afiliaciones | 26-ra2-reporte-historico-afiliaciones | `corporativo_rep_afiliaciones_2_historico_afiliaciones` | pg:corporativo.rep_afiliaciones_2_historico_afiliaciones | silver.corporativo_rep_afiliaciones_2_historico_afiliaciones |  |
| 15 | FL-0427 | ra2_reporte_consulta_subsidio | 28-ra2-reporte-consulta-subsidio | `corporativo_beneficiarios_cm_prueba` | pg:corporativo.beneficiarios_cm_prueba | silver.corporativo_beneficiarios_cm_prueba |  |
| 16 | FL-0386 | riesgos_cambio_celular | 30-riesgos-cambio-celular | `corporativo_keycloak_cambio_celular` | pg:corporativo.keycloak_cambio_celular | gold.corporativo_keycloak_cambio_celular |  |
| 17 | FL-0376 | postulaciones_rechazadas_fosfec_fovis | 43-postulaciones-rechazadas-fosfec-fovis | `corporativo_fosfec_post_rechazadas` | pg:corporativo.fosfec_post_rechazadas | gold.corporativo_fosfec_post_rechazadas |  |
| 18 | FL-0376 | postulaciones_rechazadas_fosfec_fovis | 43-postulaciones-rechazadas-fosfec-fovis | `corporativo_fovis_post_rechazadas` | pg:corporativo.fovis_post_rechazadas | gold.corporativo_fovis_post_rechazadas |  |
| 19 | FL-0379 | reporte_log_admin_lista_chequeo | 47-reporte-log-admin-lista-chequeo | `corporativo_reporte_lista_chequeo` | pg:corporativo.reporte_lista_chequeo | gold.corporativo_reporte_lista_chequeo |  |
| 20 | FL-0379 | reporte_log_admin_lista_chequeo | 47-reporte-log-admin-lista-chequeo | `corporativo_reporte_lista_chequeo_rla` | pg:corporativo.reporte_lista_chequeo_rla | gold.corporativo_reporte_lista_chequeo_rla |  |
| 21 | FL-0459 | ape_repleg | 03-ape-repleg | `agrupadoras_ape_repleg` | hdfs:/data/prod/trusted/agrupadoras/ape_repleg | silver.agrupadoras_ape_repleg |  |
| 22 | FL-0702 | ape_repleg_fotos | 03-ape-repleg | `agrupadoras_fotos_ape_repleg` | hdfs:/data/prod/trusted/agrupadoras/fotos/ape_repleg/periodo_foto=202509 | silver.agrupadoras_fotos_ape_repleg | foto 202509 |
| 23 | FL-0525 | asignacion_empresas_jsol | asignacion_empresas_jsol | `comercial_asignacion_empresas_jsol` | pg:Comercial.asignacion_empresas_jsol | silver.comercial_asignacion_empresas_jsol |  |
| 24 | FL-0399 | composicion_periodo_cierre_pago | composicion_periodo_cierre_pago | `corporativo_composicion_cuenta_mayor` | pg:corporativo.composicion_cuenta_mayor | silver.corporativo_composicion_cuenta_mayor |  |
| 25 | FL-0432 | core_validaciones_alertas_cm_07 | 07-core-validaciones-alertascm | `corporativo_alertas_subsidio` | pg:corporativo.alertas_subsidio | gold.corporativo_alertas_subsidio |  |
| 26 | FL-0697 | destinos_fotos | 01-destinos | `agrupadoras_fotos_destinos_agru` | hdfs:/data/prod/trusted/agrupadoras/fotos/destinos_agru/periodo_foto=202509 | silver.agrupadoras_fotos_destinos_agru | foto 202509 |
| 27 | FL-0585 | educacion | 05_educacion | `familias_educacion` | ⚠ sin ruta en el acta | silver.familias_educacion |  |
| 28 | FL-0705 | info_agrupadoras_fotos | 04-info-agrupadoras | `agrupadoras_fotos_tabla_agrupadoras` | hdfs:/data/prod/trusted/agrupadoras/fotos/tabla_agrupadoras/periodo_foto=202509 | silver.agrupadoras_fotos_tabla_agrupadoras | foto 202509 |
| 29 | FL-0698 | info_rep_legal_fotos | 01-info-rep-legal | `agrupadoras_fotos_rep_legal` | hdfs:/data/prod/trusted/agrupadoras/fotos/rep_legal/periodo_foto=202509 | silver.agrupadoras_fotos_rep_legal | foto 202509 |
| 30 | FL-0708 | info_total_empresas_fotos | 07-info-total-empresas | `agrupadoras_fotos_var_agrupadoras_alt` | hdfs:/data/prod/trusted/agrupadoras/fotos/var_agrupadoras_alt/periodo_foto=202509 | silver.agrupadoras_fotos_var_agrupadoras_alt | foto 202509 |
| 31 | FL-0327 | keycloak_prod | 01-keycloak-prod | `servicios_keycloak_prod` | hdfs:/data/prod/trusted/keycloak-prod/KEYCLOAK_PROD | silver.servicios_keycloak_prod |  |
| 32 | FL-0327 | keycloak_prod | 01-keycloak-prod | `servicios_keycloak_prod_postgres` | pg:Servicios.KEYCLOAK_PROD_2 | silver.servicios_keycloak_prod_postgres |  |
| 33 | FL-0700 | last_partner_fotos | 02-last-partner | `agrupadoras_fotos_last_partner` | hdfs:/data/prod/trusted/agrupadoras/fotos/last_partner | silver.agrupadoras_fotos_last_partner |  |
| 34 | FL-0471 | master_data | 00-master-data | `agrupadoras_dc_envios_agrup` | hdfs:/data/prod/trusted/agrupadoras/dc_envios_agrup | gold.agrupadoras_dc_envios_agrup |  |
| 35 | FL-0471 | master_data | 00-master-data | `agrupadoras_dc_recep_agrup` | hdfs:/data/prod/trusted/agrupadoras/dc_recep_agrup | gold.agrupadoras_dc_recep_agrup |  |
| 36 | FL-0471 | master_data | 00-master-data | `agrupadoras_dc_var_agrup_gral` | hdfs:/data/prod/trusted/agrupadoras/dc_var_agrup_gral | gold.agrupadoras_dc_var_agrup_gral |  |
| 37 | FL-0695 | master_data_fotos | 00-master-data | `agrupadoras_fotos_dc_envios_agrup` | hdfs:/data/prod/trusted/agrupadoras/fotos/dc_envios_agrup/periodo_foto=202509 | gold.agrupadoras_fotos_dc_envios_agrup | foto 202509 |
| 38 | FL-0695 | master_data_fotos | 00-master-data | `agrupadoras_fotos_dc_recep_agrup` | hdfs:/data/prod/trusted/agrupadoras/fotos/dc_recep_agrup/periodo_foto=202509 | gold.agrupadoras_fotos_dc_recep_agrup | foto 202509 |
| 39 | FL-0695 | master_data_fotos | 00-master-data | `agrupadoras_fotos_dc_var_agrup_gral` | hdfs:/data/prod/trusted/agrupadoras/fotos/dc_var_agrup_gral/periodo_foto=202509 | gold.agrupadoras_fotos_dc_var_agrup_gral | foto 202509 |
| 40 | FL-0528 | pedidos_sin_cerrar_jsol | pedidos_sin_cerrar_jsol | `comercial_pedidos_sin_cerrar_ventas_jsol` | pg:Comercial.pedidos_sin_cerrar_ventas_jsol | gold.comercial_pedidos_sin_cerrar_ventas_jsol |  |
| 41 | FL-0526 | pedidos_ventas_jsol | pedidos_ventas_jsol | `comercial_pedidos_ventas_jsol` | pg:Comercial.pedidos_ventas_jsol | silver.comercial_pedidos_ventas_jsol |  |
| 42 | FL-0531 | dim_ventas_acum | 01-dim-ventas_acum | `comercial_dim_ventas_acum` | ⚠ sin ruta en el acta | gold.comercial_dim_ventas_acum |  |
| 43 | FL-0378 | reporte_credito_subsidio_saldo_periodo_46 | 46-reporte-credito-subsidio-saldo-periodo | `corporativo_credito_subsidio_saldo_periodo` | pg:corporativo.credito_subsidio_saldo_periodo | gold.corporativo_credito_subsidio_saldo_periodo |  |
| 44 | FL-0704 | sabana_pila_fotos | 03-sabana-pila | `agrupadoras_fotos_movimiento_persona_alt` | hdfs:/data/prod/trusted/agrupadoras/fotos/movimiento_persona_alt/periodo_foto=202509 | silver.agrupadoras_fotos_movimiento_persona_alt | foto 202509 |
| 45 | FL-0356 | tableros_aportes_aportes_05 | 05-tableros-aportes-aportes | `aportes_aportes` | ⚠ sin ruta en el acta | silver.aportes_aportes |  |
| 46 | FL-0354 | tableros_afiliados_trabajadores_03 | 03-tableros-afiliados-trabajadores | `afiliados_trabajadores` | hdfs:/data/prod/trusted/afiliados/TRABAJADORES | silver.afiliados_trabajadores |  |
| 47 | FL-0354 | tableros_afiliados_trabajadores_03 | 03-tableros-afiliados-trabajadores | `corporativo_trabajadores` | pg:corporativo.trabajadores | silver.corporativo_trabajadores |  |
| 48 | FL-0357 | tableros_aportes_mora_06 | 06-tableros-aportes-mora | `aportes_mora` | pg:corporativo.mora | silver.aportes_mora |  |
| 49 | FL-0357 | tableros_aportes_mora_06 | 06-tableros-aportes-mora | `corporativo_mora` | pg:corporativo.mora | silver.corporativo_mora |  |
| 50 | FL-0362 | tableros_aportes_pila_13 | 13-tableros-aportes-pila | `servicios_pila` | hdfs:/data/prod/trusted/servicios/PILA | silver.servicios_pila |  |
| 51 | FL-0360 | tableros_servicios_beneficios_fosfec_09 | 09-tableros-servicios-beneficios-fosfec | `servicios_beneficios_fosfec` | ⚠ sin ruta en el acta | silver.servicios_beneficios_fosfec |  |
| 52 | FL-0368 | tableros_servicios_beneficios_fovis_23 | 23-tableros-servicios-beneficiosfovis | `servicios_beneficios_fovis` | pg:corporativo.beneficios_fovis | silver.servicios_beneficios_fovis |  |
| 53 | FL-0358 | tableros_subsidios_subsidio_07 | 07-tableros-subsidios-subsidio | `subsidios_subsidio` | ⚠ sin ruta en el acta | silver.subsidios_subsidio |  |
| 54 | FL-0701 | tasas_fotos | 02-tasas | `agrupadoras_fotos_tasa_empresas` | hdfs:/data/prod/trusted/agrupadoras/fotos/tasa_empresas/periodo_foto=202509 | silver.agrupadoras_fotos_tasa_empresas | foto 202509 |
| 55 | FL-0411 | td_afiliaciones | 11-td-afiliaciones | `corporativo_afiliaciones_2` | ⚠ sin ruta en el acta | silver.corporativo_afiliaciones_2 |  |
| 56 | FL-0699 | vacaciones_fotos | 01-vacaciones | `agrupadoras_fotos_vacaciones_empresas` | hdfs:/data/prod/trusted/agrupadoras/fotos/vacaciones_empresas/periodo_foto=202509 | silver.agrupadoras_fotos_vacaciones_empresas | foto 202509 |

Todos son de analítica. 7 tablas no traen ruta de Stratio en el acta (#27, #42, #45, #51, #53, #55 y la de #1 ya resuelta): sácala del código del flujo y confírmamela. Un flujo se registra con **todas** sus salidas reales (lo que diga `pc roles`), no solo las marcadas; las que no están en los 56 se miden igual y se reportan aparte (p. ej. `afiliados_pacs` de FL-0355, `agrupadoras_fotos_destinos_norm` de FL-0697).

## Tablas «no justificadas en el acta» (19): el revisor pide el texto que sustenta la aprobación
| FL | Flujo en Fabric | Flujo en Stratio | Tabla | Ruta Stratio | Ruta Fabric | Estado en el acta |
|---|---|---|---|---|---|---|
| FL-0475 | subsidios_aportes_deficit_postgres | 05-subsidios-aportes-deficit-postgres | `agrupadoras_dc_score_agrupadoras_lista_aportes_subsidio_deficit` | pg:public.dc_score_agrupadoras_lista_aportes_subsidio_deficit | gold.agrupadoras_dc_score_agrupadoras_lista_aportes_subsidio_deficit | APROBADO |
| FL-0475 | subsidios_aportes_deficit_postgres | 05-subsidios-aportes-deficit-postgres | `agrupadoras_dc_score_agrupadoras_registro_aportes_subsidio_deficit` | pg:public.dc_score_agrupadoras_registro_aportes_subsidio_deficit | gold.agrupadoras_dc_score_agrupadoras_registro_aportes_subsidio_deficit | APROBADO |
| FL-0427 | ra2_reporte_consulta_subsidio | 28-ra2-reporte-consulta-subsidio | `corporativo_beneficiarios_endosados_prueba` | pg:corporativo.beneficiarios_endosados_prueba | silver.corporativo_beneficiarios_endosados_prueba | APROBADO |
| FL-0427 | ra2_reporte_consulta_subsidio | 28-ra2-reporte-consulta-subsidio | `corporativo_beneficiarios_pacs_bloqueados` | pg:corporativo.beneficiarios_pacs_bloqueados | silver.corporativo_beneficiarios_pacs_bloqueados | APROBADO |
| FL-0427 | ra2_reporte_consulta_subsidio | 28-ra2-reporte-consulta-subsidio | `corporativo_beneficiarios_sub_pign` | pg:corporativo.beneficiarios_sub_pign | silver.corporativo_beneficiarios_sub_pign | APROBADO |
| FL-0379 | reporte_log_admin_lista_chequeo | 47-reporte-log-admin-lista-chequeo | `corporativo_reporte_periodo_post_rla` | pg:corporativo.reporte_periodo_post_rla | gold.corporativo_reporte_periodo_post_rla | APROBADO |
| FL-0379 | reporte_log_admin_lista_chequeo | 47-reporte-log-admin-lista-chequeo | `corporativo_reporte_reapertura_post_rla` | pg:corporativo.reporte_reapertura_post_rla | gold.corporativo_reporte_reapertura_post_rla | APROBADO |
| FL-0580 | afiliados | 01_afiliados | `familias_afiliados` | ⚠ sin origen en Stratio según el acta | silver.familias_afiliados | ACREDITADO_POR_REGISTRO_DELTA |
| FL-0586 | educacion_estado | 06_educacion_estado | `familias_educacion_estado` | ⚠ sin origen en Stratio según el acta | silver.familias_educacion_estado | ACREDITADO_POR_REGISTRO_DELTA |
| FL-0583 | empresas | 03_empresas | `familias_empresas` | hdfs:/data/prod/trusted/familias/empresas/EMPRESAS_FINAL (HTTP 500 en Rocket) | silver.familias_empresas | ACREDITADO_POR_REGISTRO_DELTA |
| FL-0652 | flujo_control_ppto | 01-flujo-control-ppto | `corporativo_sub_especie_recreacion_control_ppto` | pg:corporativo.sub_especie_recreacion_control_ppto | silver.corporativo_sub_especie_recreacion_control_ppto | APROBADO |
| FL-0456 | info_cities | 00-info-cities | `agrupadoras_cities` | hdfs:/data/prod/trusted/agrupadoras/cities | silver.agrupadoras_cities | APROBADO |
| FL-0694 | info_cities_foto | 00-info-cities | `agrupadoras_fotos_cities` | hdfs:/data/prod/trusted/agrupadoras/fotos/cities/periodo_foto=202509 | silver.agrupadoras_fotos_cities | APROBADO |
| FL-0372 | prevalidador_2069_29 | 29-prevalidador-2069 | `cliente_prevalidador_vigentes` | pg:Cliente.PrevalidadorVigentes | gold.cliente_prevalidador_vigentes | APROBADO |
| FL-0597 | recreacion | 14_recreacion | `familias_recreacion` | ⚠ sin origen en Stratio según el acta | silver.familias_recreacion | ACREDITADO_POR_REGISTRO_DELTA |
| FL-0398 | rq1_bd_inicial_tt_afiliados | rq1_bd_inicial_tt_afiliados | `afiliados_pvs_prueba_afi` | ⚠ sin origen en Stratio según el acta | silver.afiliados_pvs_prueba_afi | ACREDITADO_POR_REGISTRO_DELTA |
| FL-0398 | rq1_bd_inicial_tt_afiliados | rq1_bd_inicial_tt_afiliados | `afiliados_pvs_prueba_ben` | ⚠ sin origen en Stratio según el acta | silver.afiliados_pvs_prueba_ben | ACREDITADO_POR_REGISTRO_DELTA |
| FL-0362 | tableros_aportes_pila_13 | 13-tableros-aportes-pila | `corporativo_pila` | pg:corporativo.pila | silver.corporativo_pila | APROBADO |
| FL-0591 | turismo | 10_turismo | `familias_turismo` | ⚠ sin origen en Stratio según el acta | silver.familias_turismo | ACREDITADO_POR_REGISTRO_DELTA |

- 6 de las 19 salen de flujos que ya están arriba (FL-0427, FL-0379, FL-0362): se miden con su flujo y quedan respondidas.
- Las 7 ACREDITADO_POR_REGISTRO_DELTA: comprueba hoy, con el código del flujo de Stratio y un listado de HDFS/Postgres, si de verdad no existe salida equivalente en Stratio (en `familias_empresas` el acta anotó HTTP 500 de Rocket, no «no existe»). Si existe, se coteja. Si no existe, dilo con la evidencia: «sin cotejo» no es «cumple», y la decisión es mía.
- Las 3 de `ra2_reporte_consulta_subsidio` con 0 → 0 filas y `corporativo_pila` / `cliente_prevalidador_vigentes` «con hallazgos»: dime qué hallazgo tienen y si 0 filas es lo esperado (entrada vacía o filtro).
- Las demás (conteo igual, Integridad OK): proponme si basta el cotejo con huella en formato 2 o si hay que re-ejecutar; no las corras sin mi «sí».

## Ya medidos en formato 2 (NO los vuelvas a ejecutar: tráelos y dime si el criterio se cumple)
Para cada uno lee `v4/flujos/<flujo>.json`, `v4/cotejos/<clave>.json` y `v4/diferencias.json` del trabajo y escribe «prueba a realizar → lo que ya se midió · criterio para cerrar → se cumple / no se cumple / falta X». Comprueba en Fabric que el flujo no corrió después de esa medición; si corrió, dímelo.

| # | Tabla | Trabajo | Estado que quedó | Ojo frente al criterio del revisor |
|---|---|---|---|---|
| 1 | `agrupadoras_origenes` | `L11-complemento`, ciclo v3 (07-10), publicado | APROBADO_CON_JUSTIFICACION | el revisor pide: conteo de **VBAP y VBAK en los dos lados**, cotejo por `VBELN`, **ID-02 medido en Fabric** y diferencia < 1 %. El bronze VBAP de Fabric se recargó el 05-10: dime con qué VBAP se escribió la versión medida en v3, las filas de cada lado en v3 y si ID-02 quedó exacto. Si la justificación del lote 11 no responde eso, preséntamelo para decidir si se reabre |
| — | `moves` (FL-0466: `moves_agrup`, `historico_movimiento_alt`, `historico_movimiento2`), `tasas`, `sabana_pila`, `destinos` | `L11-complemento`, v3 | APROBADO_CON_JUSTIFICACION | son la cadena que el revisor dice que hereda la pérdida de origenes (OR-02): de aquí sale si MOVES ya está completo, que es la condición de #34–#39, #44, #54 y #56 |
| — | `last_partner`, `vacaciones`, `info_general_empresas`, `info_salarial` | `L11-resto`, v1 | APROBADO_CON_JUSTIFICACION | bases de las fotos #33 y #56 |
| — | `agrupadoras_var_agrupadoras_alt` | `L8.2`, v1 | APROBADO_CON_JUSTIFICACION (reserva D11 en `L8.3`) | base de la foto #30 (5.081 empresas) |
| — | `agrupadoras_fotos_origenes`, `agrupadoras_fotos_last_partner` | `L12-insumos` (diagnóstico) | EN_REVISION | #33 es `fotos_last_partner`: ya hay nivel 2 de la foto 202509 con huella distinta; trae la cifra y la causa si se midió |
| — | `moves_fotos`, `info_salarial_fotos` | `L12` (06-10, formato anterior) | diferencia dentro de la foto PENDIENTE | QA decidió el 06-10 no re-ejecutar las fotos; si `L12.2` ya las midió, dímelo |

## Cómo se agrupan los hallazgos (para repartir a los cotejadores)
El documento trae por tabla la prueba y el criterio; no los repito. Lo que importa para ordenar el trabajo:

- **Cadena de Agrupadoras (heredan de #1):** #26, #30, #34–#39, #44, #54, #56 y, por empresas o socios que faltan, #22, #28, #33. El revisor condiciona todas a «corregir origenes y MOVES». Primero se responde #1 con lo ya medido; después se decide **una sola** corrida de las fotos (orquestador), no flujo por flujo. Mientras la base no esté completa, re-ejecutar una foto no cierra nada: mide la causa y dilo. #29 es distinto: la foto de Fabric es la tabla completa (filtro de foto), mira el código.
- **Faltan o sobran filas sin causa (cotejo por clave):** #2, #3, #4, #5, #14, #16, #19, #20, #23, #24, #27, #42, #43, #46, #55. Lista las filas sin pareja (o cuéntalas por periodo si son muchas), con la clave que proponga el cotejador y que yo confirme, y busca la causa en la entrada o en el paso del código. «Altas posteriores» (#4) solo si la fecha de creación lo demuestra.
- **Cruce que pierde dato (nulos que suben sin que bajen las filas):** #6, #7, #10, #12, #13, #41, #48, #49, #51, #52. No basta contar nulos: identifica en el código qué entrada llena la columna, mide esa entrada a cada lado (fecha y conteo) y dime si es entrada atrasada (corte) o cruce roto (defecto).
- **Regla distinta en Fabric (pensión):** #2, #17, #18 (`reqpagpension`, `fondopensiones`): compara la regla en el código de los dos lados. En #17 además se mide la versión Delta que escribió la corrida validada, no otra.
- **Defecto ya identificado en el acta y aun así aprobado:** #8 (un solo año de metas; arrastra #7), #40 (Copy en append, 4 corridas), #47 (filtro que solo aplica Fabric; arrastra los nulos de `tipo_posicion`), #11 (Fabric tiene el 1,25 % de las filas). Comprueba si desarrollo ya corrigió y re-ejecutó; si no, se devuelven con el archivo del código, el paso y la cifra. No se justifican.
- **Stratio duplicado, nombres en otra caja y tablas grandes:** #45 (474 M / 235 M), #53 (106 M / 53 M), #50 (97,7 M). Duplicados **exactos** en los dos lados, perfil comparando los nombres sin distinguir caja (dime si el motor ya lo hace o si es una mejora: no la apliques en silencio) y las filas distintas que faltan (1.496.283, 7.379, 25.051) ubicadas por clave o por periodo.
- **Referencia de Stratio vacía o no equivalente:** #25 (Stratio 0 filas), #31 (se cotejó la carpeta trusted contra la tabla final), #32. Antes de medir dime contra qué se debe cotejar cada una, con lo que diga el código de Stratio.
- **Sin cotejo o medición reducida:** #9 (`corporativo.pacs` de Stratio nunca terminó de bajar), #15 (23,8 M, Stratio sin perfil), #21 (ID-02 sin medir en Stratio; 23.867 duplicados en Fabric).
- **«Por decisión del usuario, no documentada»:** #10, #25, #33, #47. Esas decisiones no tienen registro: se vuelven a presentar con el expediente (`pc decision`) y decido yo, ahora por escrito.
- **Sello T-08 («las dos métricas tienen el mismo sello»):** en cada medición registra la fecha de **escritura** de cada lado (commit Delta, fecha de los archivos de HDFS, última carga de la Postgres), no la hora en que se procesó en local. «Cargas de fechas distintas» solo vale como causa si se demuestra con esas dos fechas y con el conteo dentro y fuera de la ventana.
- **Justificaciones cortadas (56 de 69 terminan en «…»):** es un defecto del acta, no de la medición. Dime dónde corta el generador para que el acta 7.2 lleve los textos completos; si hay que tocar código, es una mejora que se registra.
- **Documentos que el revisor cita y no están en `~/Projects`:** `Hallazgos_Lote7.md`, `Hallazgos_Preliminares_Lote7.xlsx`, `Solicitud_Evidencia_MOVES_Lote6.md`, `archivos_lote_7.1/`. Búscalos; si no aparecen, pídemelos (el tercero define el cotejo por `VBELN` de #1).

## Plan de ejecución (muéstramelo ordenado y espera mi «sí»; nada en paralelo dentro de Fabric)
0. **Cierre con lo ya medido:** #1 y el estado de la cadena de Agrupadoras. Sin ejecutar nada.
1. **Estado en Fabric de los 46 flujos** (última corrida, commit de cada salida) y cuáles re-entregó desarrollo. Si un flujo no se ha tocado desde septiembre, re-ejecutarlo solo refresca el corte: dímelo.
2. **Chicos y sin dependencia** (Postgres de Stratio pequeñas, una a la vez): #4, #6, #8 → #7, #16, #19, #20, #23, #24, #40, #41, #42, #43, #27, #5, #17, #18, #2, #3, #52, #51, #10, #12, #13, #14, #55, #11, #46, #47, #48, #49, #31, #32, #25.
3. **Medianas con descarga:** #9, #15, #21.
4. **Agrupadoras y fotos**, según lo que salga del paso 0 y lo que yo decida sobre el orquestador de fotos.
5. **Grandes**, cada una con su estimación y mi confirmación: #50, #53, #45.
6. Las 19 no justificadas que no hayan quedado cubiertas.
Si una entrada está vacía o vieja y su productor no está en el plan, dímelo antes: decido yo.

## Tamaños: avísame antes de descargar (tablas, MB, vía, tiempo) y espera confirmación en las grandes
`aportes_aportes` (474 M filas en Stratio, la mitad duplicados exactos), `subsidios_subsidio` (106 M), `servicios_pila` (97,7 M), `agrupadoras_origenes` (93 M; mira si su caché sigue en `cache/L11-complemento`), `corporativo_beneficiarios_cm_prueba` (23,8 M, Postgres). Para `aportes_aportes` proponme, con cifras, si se baja completo o si el hallazgo se responde con conteo, duplicados y huella por partición o periodo más la descarga de solo lo que difiere; lo decido yo. `silver.subsidios_subsidio` y `silver.servicios_pila` son además entradas de flujos del lote 8 (en L8.2 estaban con fecha 2026-09-29): mira si `L8.3` ya las re-ejecutó o midió y no las corras dos veces.

## Lecciones (aplícalas)
- La VPN se cae con tráfico sostenido contra la Postgres de Stratio: **una sola cosa a la vez contra esa base**; las tablas grandes se extraen por trozos de `ctid` reanudables (`trabajos/_sesion_2026-10-08/bajar_detalle_paralelo.py` con 1 o 2 conexiones, nunca 4) y se miden en local, no dentro de la base. Aquí hay unas 30 tablas Postgres de Stratio: ordénalas de menor a mayor.
- Rocket (HDFS) necesita VPN y cookies (1 a 3; duran 2–3 h; 8 hilos repartidos): prioriza Stratio mientras haya VPN.
- Procesos largos con `setsid`/`nohup` y log; matar solo por PID. 19 GB de RAM: más de 50 M de filas, un objeto a la vez (`trabajos/_sesion_2026-10-08/medir_ventas_1x1.sh`); cotejadores con DuckDB ≤ 4 GB. El ID-02 de `origenes` «excedió la memoria» en septiembre: mídelo por particiones, exacto.
- `pc ciclo` borra la caché de los dos lados del flujo: antes de abrir un ciclo dime qué caché se pierde y cuánto cuesta volver a bajarla.
- Un cotejador por tabla o por flujo, con el # del hallazgo, su «prueba a realizar» y su «criterio para cerrar» copiados del documento; comprueba tú lo que devuelva antes de registrarlo. Que no dejen datos personales en el scratchpad.

## Lo que no se negocia
- Se valida la corrida que escribió el dato que se mide; Fabric medido **después** de su última corrida; re-ejecución = versión nueva.
- Mismo motor y parámetros a cada lado (v15, SHA-256 completo y huella por columna). «Sin huella» no se repite: en analítica la huella informa, pero se mide.
- Fotos: la foto se coteja por partición (`periodo_foto`) y además me das el conteo por `periodo_foto` de los dos lados; el histórico que Fabric no guarda se registra con cifras, no se aplica como ventana en silencio.
- Toda diferencia se registra con conteo exacto, hasta 5 ejemplos y causa. ID-02 exacto en los dos lados, nunca `NO_EVALUABLE`. `pc v4 incompletos` en COMPLETO antes de publicar. Los devueltos no se publican sin mi «sí».
- Causa **medida** de fecha o corte de la entrada → propuesta JUSTIFICADA. Defecto del flujo de Fabric (append que duplica, filtro que Stratio no aplica, cruce roto, regla distinta, año sin cargar) o causa no medida → propuesta DEVUELTO o PENDIENTE. **Las decisiones son mías, una por una**, con el expediente (`pc decision --trabajo L7.2`). No cambies umbrales, exclusiones de columnas ni ventanas para que algo cumpla.
- «No se evaluó» nunca es «cumple».

## Qué me entregas
1. La tabla del primer paso (pide · ya medido · falta · última corrida) de los 56 hallazgos y las 19 no justificadas.
2. Por flujo: estado, corrida validada (hora, run), comprobaciones que no cumplen y por qué. Por tabla: resumen exacto y diferencias registradas con su propuesta.
3. `~/Projects/reportes/Lote7.2_<fecha>.md` (documento vivo): un bloque por hallazgo #1 a #56 con «prueba a realizar» → resultado en cifras, «criterio para cerrar» → se cumple / no se cumple / no se pudo evaluar (por qué), y los enlaces (1 por flujo y 3 por tabla: cotejo, métrica Stratio, métrica Fabric); un bloque aparte con las 19 no justificadas y el texto que sustenta cada una. Arriba, el resumen por grupo de causa y qué falta de cada flujo no aprobado.
4. Lo que haya que devolver a desarrollo, redactado por flujo con la evidencia (archivo del código, paso y cifra).
5. El acta 7.2 (.docx) solo cuando yo cierre las decisiones, con las justificaciones completas.
