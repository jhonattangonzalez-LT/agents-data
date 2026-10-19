Trabajo nuevo: **L9.2** — re-prueba de las 39 tablas (27 flujos) marcadas 🔁 VOLVER A REALIZAR PRUEBA en el reporte 9.2 (documento `~/Projects/reportes/Hallazgos_Lote9.2.md`, ya guardado completo). Eres el coordinador (CLAUDE.md). El lote 9 se midió el 25/26-09 con el formato anterior y no tiene trabajo propio en `trabajos/`; 9 de las 39 tablas ya se midieron en formato 2 en los lotes 11 y 10.1 (sección «Ya medidos»): esas se traen, el resto se mide de nuevo. No toques `L8.2`, `L8.3`, `L10-1`, `L11-*` ni `L12*` (solo lectura).

## Qué quiero al final
Cada flujo con su cotejo de flujo y sus cotejos de tabla en formato 2, completos y publicados, y **cada hallazgo # respondido con dato**: la columna «Prueba a realizar» ejecutada y la columna «Criterio para cerrar» evaluada tal como está escrita. En 34 de las 39 el problema es que «el acta no da la causa»: lo que se entrega esta vez es la **causa medida** (qué filas, de qué periodo, por qué entrada o qué paso del código), o el hallazgo queda abierto diciendo qué falta y de quién depende. Prefiero un flujo devuelto con evidencia a uno aprobado «porque el contrato se cumple».

## Estado al escribir este prompt (2026-10-09 02:46 UTC)
VPN arriba y **2 cookies de Rocket ya guardadas y vigentes** (puestas 02:45 UTC; duran ~2 h; el JWT vence 07:17 UTC). No me las pidas al abrir: compruébalas con `pc stratio cookie` y `pc stratio vpn` y avísame cuando queden menos de 15 min. Hay **otra sesión en paralelo** (lote 8, trabajos `L8.2` y `L8.3`: no los toques): comparten las 2 cookies (8 hilos de Rocket en total, no 8 cada una) y la Postgres de Stratio (una sola cosa a la vez contra esa base). Antes de lanzar una descarga o extracción de Stratio dímelo, para coordinar el turno con la otra ventana.

## Primer paso
1. Lee completo `~/Projects/reportes/Hallazgos_Lote9.2.md` (el documento del revisor, tal cual lo entregó).
2. Lee: `~/Projects/reportes/datos_acta_lote9.json` (acta 9 v2.1: de ahí salen las rutas de abajo y las justificaciones que el revisor rechaza), `~/Projects/reportes/Hallazgos_Lote10.1.md` y `docs/RESUMEN_SESION_2026-10-07_L10-1.md` (tablas repetidas), `~/Projects/reportes/Respuesta_Hallazgos_Reportes_6_y_9.md`, `trabajos/_sesion_2026-10-08/RETOMAR.md` (lecciones de VPN y memoria), `.claude/agents/cotejador.md`, `pc/reportes/formato2.py`.
3. Lo de siempre: mejoras pendientes (M-010 a M-013 SIN COMPARTIR: pregúntame), `fab auth status`, VPN y cookies de Rocket (ya están puestas: ver «Estado»).

## Flujos (27) y tablas (39)
Rutas del acta 9 v2.1 (`pgsql:`/`pg:` = Postgres de Stratio; `pgfab:` = Postgres de Fabric, solo por el agente postgres-fabric). **Confírmalas con `pc roles --flujo F`** antes de medir y dime cuál corriges y por qué. Las filas son las del 25/26-09: antecedente, no resultado.

| # | FL | Flujo en Fabric | Flujo en Stratio | Grupo | Tabla (clave) | Ruta Stratio | Ruta Fabric | Filas 09-26 (S / F) |
|---|---|---|---|---|---|---|---|---|
| 1 | FL-0476 | calculo_trab_ben_cuota_monetaria | 06-calculo-trab-ben-cuota-monetaria | analitica | agrupadoras_dc_score_agrupadoras_lista_detalle_subsidios_trabajadores | `pgsql:public.dc_score_agrupadoras_lista_detalle_subsidios_trabajadores` | `pgfab:agrupadoras.dc_score_agrupadoras_lista_detalle_subsidios_trabajadores` | 36.652 / 36.643 |
| 2 | FL-0352 | tableros_afiliados_empresas_01 | 01-tableros-afiliados-empresas | analitica | corporativo_empresas | `pgsql:corporativo.empresas` | `pgfab:corporativo.empresas` | 552.980 / 552.562 |
| 3 | FL-0523 | cliente_servicios | cliente_servicios | analitica | cliente_cliente_360 | `pgsql:Cliente.cliente_360` | `pgfab:Cliente.cliente_360` | 2.005.954 / 1.897.075 |
| 4 | FL-0523 | 〃 | 〃 | analitica | cliente_cliente_360_pacs | `pgsql:Cliente.cliente_360_pacs` | `pgfab:Cliente.cliente_360_pacs` | 1.451.587 / 1.278.841 |
| 5 | FL-0523 | 〃 | 〃 | analitica | cliente_cliente_360_recreacion | `pgsql:Cliente.cliente_360_recreacion` | `pgfab:Cliente.cliente_360_recreacion` | 3.669.116 / 3.668.288 |
| 6 | FL-0523 | 〃 | 〃 | analitica | cliente_cliente_360_credito | `pgsql:Cliente.cliente_360_credito` | `pgfab:Cliente.cliente_360_credito` | 110.491 / 110.802 |
| 7 | FL-0010 | 01-landing-feco-tpos-header | 01-landing-feco-tpos-header | ingesta | feco_sgdatos_tpos_header | `hdfs:/data/prod/landingraw/feco/sgdatos/TPOS_HEADER` | `Files/bronze/feco/sgdatos/TPOS_HEADER` | 210.263 / 210.263 |
| 8 | FL-0155 | 06-landing-sappscd-zsub-p-det-apo | 06-landing-sappscd-zsub-p-det-apo | ingesta | sap_pscd_zsub_p_det_apo | `hdfs:/data/prod/landingraw/sap/pscd/ZSUB_P_DET_APO` | `Files/bronze/sap/pscd/ZSUB_P_DET_APO` | 97.687.315 / 97.686.728 |
| 9 | FL-0146 | 21-landing-sappscd-zsub-bi-empresas | 21-landing-sappscd-zsub-bi-empresas | ingesta | afiliaciones_zsub_bi_empresas | `pg:Afiliaciones.ZSUB_BI_EMPRESAS` | `pgfab:Afiliaciones.ZSUB_BI_EMPRESAS` | 3.410.275 / 3.410.275 |
| 10 | FL-0645 | reporte_ya_preinscriptos_cm_27B | 27b-reporte-ya-preinscriptos-cm | analitica | corporativo_subsidios_prescritos | `pgsql:corporativo.subsidios_prescritos` | `pgfab:corporativo.subsidios_prescritos` | 855.181 / 147.655 |
| 11 | FL-0251 | 30-trusted-sappscd-zsub-informetipi | 30-trusted-sappscd-zsub-informetipi | ingesta | sap_pscd_zsub_informetipi | `hdfs:/data/prod/trusted/sap/pscd/ZSUB_INFORMETIPI` | `silver.sap_pscd_zsub_informetipi` | 3.402.735 / 3.402.248 (solo PERIODO 202609) |
| 12 | FL-0035 | ingesta_educacion | ingesta_educacion | ingesta | credito_educacion_formal | `hdfs:/data/prod/trusted/credito/archivos_planos_datamart/educacion_formal` | `silver.credito_educacion_formal` | 4.845 / 4.848 |
| 13 | FL-0035 | 〃 | 〃 | ingesta | microdato_educacion_formal | `pg:microdato.educacion_formal` | `pgfab:microdato.educacion_formal` | 4.845 / 4.848 |
| 14 | FL-0020 | spool-corbanco-consumo | spool-corbanco-consumo | ingesta | globales_corbanco_spool_saldo_cartera | `hdfs:/data/prod/landingraw/globales/corbanco_spool_saldo_cartera` | `Files/bronze/globales/corbanco_spool_saldo_cartera` | 110.491 / 110.802 |
| 15 | FL-0020 | 〃 | 〃 | ingesta | corporativo_credito_saldo_cartera | `pg:corporativo.credito_saldo_cartera` | `pgfab:corporativo.credito_saldo_cartera` | 110.491 / 110.802 |
| 16 | FL-0247 | 06-trusted-sappscd-dfkkop | 06-trusted-sappscd-dfkkop | ingesta | sap_pscd_dfkkop_trusted | `hdfs:/data/prod/trusted/sap/pscd/DFKKOP` | `silver.sap_pscd_DFKKOP` | 342.780.202 / 342.678.462 |
| 17 | FL-0618 | exogena_ingresos | exogena-ingresos | analitica | mercadeo_exogena_ingresos | `pgsql:mercadeo.exogena_ingresos` | `pgfab:mercadeo.exogena_ingresos` | 1.425.851 / 896.466 |
| 18 | FL-0532 | ingesta_cobertura | 02_ingesta_cobertura | analitica | comercial_cobertura_matriz_lealtad | `hdfs:/data/prod/raw-files/matriz_lealtad/cobertura` | `silver.comercial_cobertura_matriz_lealtad` | 9.420.348 / 11.182.353 |
| 19 | FL-0619 | medios_pago | medios_pago | analitica | mercadeo_medios_pago | `pgsql:mercadeo.medios_pago` | `pgfab:mercadeo.medios_pago` | 40.262.246 / 343.694 |
| 20 | FL-0391 | reporte_cuota_detalle_ssf | 01-reporte-cuota-detalle-ssf | analitica | corporativo_cuotas_pacs_ssf | `pgsql:corporativo.cuotas_pacs_ssf` | `pgfab:corporativo.cuotas_pacs_ssf` | 47.205.193 / 10.887.639 |
| 21 | FL-0389 | reporte_cuota_anulados_ssf | 02-reporte-cuota-anulados-ssf | analitica | corporativo_cuotas_pacs_anulados_ssf | `pgsql:corporativo.cuotas_pacs_anulados_ssf` | `pgfab:corporativo.cuotas_pacs_anulados_ssf` | 42.123 / 39.277 |
| 22 | FL-0343 | ssf_afiliados_ssf_afiliados_historico_05 | 05-ssf-afiliados-ssf-afiliados-historico | analitica | ssf_afiliados_historico | `pgsql:SSF.AFILIADOS_HISTORICO` | `pgfab:SSF.AFILIADOS_HISTORICO` | 37.401.057 / 3.368.484 |
| 23 | FL-0343 | 〃 | 〃 | analitica | afiliados_ssf_afiliados_historico | `hdfs:/data/prod/trusted/afiliados/ssf_afiliados_historico` | `gold.afiliados_ssf_afiliados_historico` | 29.539.715 / 29.410.699 |
| 24 | FL-0339 | ssf_afiliados_ssf_empresas_01 | 01-ssf-afiliados-ssf-empresas | analitica | ssf_empresast | `pgsql:SSF.EMPRESAST` | `pgfab:SSF.EMPRESAST` | 81.380 / 76.416 |
| 25 | FL-0339 | 〃 | 〃 | analitica | ssf_sftp_ssf_empresas_csv | `sftp:/home/comfandi/SSF/SSF_EMPRESAS` | `sftp:/home/comfandi/pruebas_escritura_migracion/dev/SSF/SSF_EMPRESAS` | 81.380 / 76.416 |
| 26 | FL-0339 | 〃 | 〃 | analitica | ssf_errores_empresas | `sftp:/home/comfandi/SSF_ERRORES/SSF_EMPRESAS` | `sftp:/home/comfandi/pruebas_escritura_migracion/dev/SSF_ERRORES/SSF_EMPRESAS` | 196 / 186 |
| 27 | FL-0342 | ssf_afiliados_ssf_empresas_historico_04 | 04-ssf-afiliados-ssf-empresas-historico | analitica | afiliados_ssf_empresas_historico | `hdfs:/data/prod/trusted/afiliados/ssf_empresas_historico` | `gold.afiliados_ssf_empresas_historico` | 3.753.288 / 3.748.324 |
| 28 | FL-0342 | 〃 | 〃 | analitica | ssf_empresas_historico | `pgsql:SSF.EMPRESAS_HISTORICO` | `pgfab:SSF.EMPRESAS_HISTORICO` | 1.908.911 / 1.008.393 |
| 29 | FL-0344 | ssf_afiliados_ssf_pacs_historico_06 | 06-ssf-afiliados-ssf-pacs-historico | analitica | afiliados_ssf_pacs_historico | `hdfs:/data/prod/trusted/afiliados/ssf_pacs_historico` | `gold.afiliados_ssf_pacs_historico` | 26.831.600 / 26.683.260 |
| 30 | FL-0344 | 〃 | 〃 | analitica | ssf_pac_historico | `pgsql:SSF.PAC_HISTORICO` | `pgfab:SSF.PAC_HISTORICO` | 25.023.737 / 3.112.543 |
| 31 | FL-0367 | tableros_fovis_prevalidadorFovis_21 | 21-tableros-fovis-prevalidadorfovis | analitica | cliente_prevalidadorfovis | `pgsql:Cliente.PrevalidadorFovis` | `pgfab:Cliente.PrevalidadorFovis` | 900.614 / 705.099 |
| 32 | FL-0524 | empresa_servicios | empresa_servicios | analitica | cliente_empresa_360 | `pgsql:Cliente.empresa_360` | `pgfab:Cliente.empresa_360` | 112.944 / 112.880 |
| 33 | (sin FL: no lo inventes) | metricas_td | metricas_td | analitica | cliente_metricastd | `pgsql:Cliente.metricasTD` | `pgfab:Cliente.metricasTD` | 839.095 / 838.513 |
| 34 | FL-0649 | reporte_proximos_preinscribir_cm_27a | 27a-reporte-proximos-preinscribir-cm | analitica | corporativo_subsidios_proximos_a_prescribir | `pgsql:corporativo.subsidios_proximos_a_prescribir` | `pgfab:corporativo.subsidios_proximos_a_prescribir` | 724.182 / 739.768 |
| 35 | FL-0369 | tableros_cartera_26 | 26-tableros-cartera | analitica | corporativo_cartera | `pgsql:corporativo.cartera` | `pgfab:corporativo.cartera` | 3.502.782 / 3.527.160 |
| 36 | FL-0369 | 〃 | 〃 | analitica | corporativo_cartera_retiros | `pgsql:corporativo.cartera_retiros` | `pgfab:corporativo.cartera_retiros` | 10.884 / 12.394 |
| 37 | FL-0541 | transformacion_contact_comercial | transformacion_contact_comercial | analitica | globales_contactabilidad_comercial | `hdfs:/data/prod/trusted/globales/contactabilidad/contactabilidad_comercial/registrosValidos` | `silver.globales_contactabilidad_comercial` | 982.752 / 978.241 |
| 38 | FL-0485 | trusted_datarmat_credito_clientes | 01-trusted-datarmat-credito-clientes | analitica | credito_clientes | `pgsql:credito.clientes` | `pgfab:credito.clientes` | 2.176.414 / 2.089.265 |
| 39 | FL-0485 | 〃 | 〃 | analitica | credito_pacs | `pgsql:credito.pacs` | `pgfab:credito.pacs` | 1.641.808 / 1.635.342 |

Un flujo se registra con **todas** sus salidas reales (lo que diga `pc roles`), no solo las marcadas: `cliente_servicios` tiene 6 (educación y hoteles se cerraron con salvedad), `ingesta_educacion` 11, `metricas_td` tiene salidas intermedias silver sin cotejar, `transformacion_contact_comercial` tiene la salida de **rechazados** (PENDIENTE desde el lote 6: esta vez se coteja). Dime cuáles agregas. Las que no están en los 39 se miden igual y se reportan aparte.

## Ya medidos en formato 2 en los lotes 11 y 10.1 (NO los vuelvas a ejecutar: tráelos y ciérralos si el criterio se cumple)
Están publicados (`v4/publicado.json` de cada trabajo; enlaces en `~/Projects/reportes/Links_Lote11_2026-10-07.md`) salvo `L10-1`. Es lo primero que haces, antes de cualquier ejecución: para cada # de abajo lee `v4/flujos/<flujo>.json`, `v4/cotejos/<clave>.json` y las diferencias de `v4/diferencias.json`, y escribe en el Markdown **«prueba a realizar» → lo que ya se midió · «criterio para cerrar» → se cumple / no se cumple / falta X**. Si se cumple, queda cerrado con esos enlaces. Si la justificación del lote 11 no responde lo que el revisor pide, dímelo: decido yo si se reabre (re-decidir no cambia la versión; re-ejecutar sí).

| # | Tabla | Trabajo (corrida 2026-10-07) | Lo que ya está medido — verifícalo en el archivo | Ojo frente al criterio del revisor |
|---|---|---|---|---|
| 8 | `sap_pscd_zsub_p_det_apo` | `L11-complemento`, ciclo v3 · APROBADO_CON_JUSTIFICACION | 97.906.903 / 97.903.789 (−3.114); 145 periodos en los dos lados: 18 con el mismo conteo y 127 históricos (1412 a 2603) con menos filas en Fabric; 70 columnas con el mismo perfil; llave compuesta de 7 columnas única por periodo en los dos lados | el revisor pide **duplicados exactos a cada lado**, el diagnóstico por periodo y ubicar las copias por llave y `PERIODO_PAGO`. El diagnóstico por periodo ya existe (D1). Las 587 «copias» del 26-09 ya no son la cifra: responde con las 3.114 y comprueba si D1 dice **por qué** faltan en los periodos históricos (si solo dice dónde, la causa sigue sin medir) |
| 22 | `ssf_afiliados_historico` (Postgres publicada) | `L11-resto`, v1 · APROBADO_CON_JUSTIFICACION | 38.075.446 en 57 cortes / 1.197.200 en 2 cortes (2026-08 y 2026-09); duplicados exactos 330 / 23 | **el 79 % de duplicados del Copy ya no existe** (23). Pero el criterio es «mismos cortes y conteo por corte»: Fabric publica 2 de 57 cortes y en los comunes 2026-08 da 668.756 / 539.740. Justificado en el lote 11 como diferencia de cortes; el revisor lo llama defecto del Copy → preséntamelo para decidir |
| 23 | `afiliados_ssf_afiliados_historico` (Delta gold) | 〃 | 38.075.443 en 57 cortes / 30.068.159 en 45; **43 cortes con el mismo conteo (2023-01 a 2026-07; 28.870.959 filas)**; 12 cortes solo en Stratio (2022; 7.861.339); las 3 columnas ausentes son nombres antiguos que solo existen en 2022 | responde el criterio («conteo por corte o diferencia ubicada»): la diferencia queda en 2022 (fuera del periodo oficial) y en los cortes 2026-08/09. Candidato a cerrar |
| 27 | `afiliados_ssf_empresas_historico` (Delta gold) | `L11-resto`, v1 · APROBADO_CON_JUSTIFICACION | 4.653.481 en 57 cortes / 3.824.740 en 45; 43 cortes iguales (3.671.908); 12 solo en Stratio (2022; 817.903); duplicados 326.117 = 326.117 en los cortes comunes | hereda la #24: las empresas que faltan en el corte 2026-08 (81.380 / 76.416) se explican allí |
| 28 | `ssf_empresas_historico` (Postgres publicada) | 〃 | 1.991.201 en 22 cortes / 76.416 en 1 corte (2026-08); duplicados 246.615 / **0** | los duplicados del Copy ya no existen; sigue un solo corte de 22 → igual que la #22 |
| 29 | `afiliados_ssf_pacs_historico` (Delta gold) | `L11-resto`, v1 · APROBADO_CON_JUSTIFICACION | 35.319.185 en 57 cortes / 27.379.258 en 45; 43 cortes iguales (26.259.817); 12 solo en Stratio (2022; 7.913.809); `SECT_PRIMARIO` solo existe en Stratio desde 2026-09 | el revisor pide además **parentesco completo y columnas étnicas iguales**: busca en D1 (ID-04, 21 columnas) la cifra de `PAR_PERSONA_A_CARGO` y de las étnicas por corte; si no está, falta medirla (con la caché, sin re-ejecutar) |
| 30 | `ssf_pac_historico` (Postgres publicada) | 〃 | 25.597.513 en 42 cortes / 1.119.441 en 2; duplicados 75 / 0; `SECT_PRIMARIO` 100 % vacía en Fabric; `PERTENENCIA_ETNICA`, `COD_RESGUARDO`, `COD_PUB_INDIGENA` **constantes en Fabric** (11.663 filas de Stratio con etnia distinta de 8) | D7 (ID-06) quedó JUSTIFICADA y el revisor lo trata como pérdida de información (PH-03): **es una columna que colapsa; revísala conmigo**. Falta la cifra de `PAR_PERSONA_A_CARGO` (PH-02) |
| 1 | `agrupadoras_dc_score_…_subsidios_trabajadores` | `L10-1` · APROBADO_CON_VERIFICACION (sin publicar) | ver `trabajos/L10-1/v4` y `docs/RESUMEN_SESION_2026-10-07_L10-1.md` | el documento dice que hereda la decisión del lote 10.1 (#1): trae el resultado y dime si la verificación ya se cerró (`pc verificar`) |
| 2 | `corporativo_empresas` | `L10-1` · APROBADO_CON_VERIFICACION (sin publicar) | 〃 | hereda la #9 del 10.1; comprueba si ID-05 se evaluó con llave compuesta (bp + fecha_inicio_estado) |

Con esto, de entrada quedan **9 de las 39 con medición vigente** y el trabajo nuevo `L9.2` arranca con los otros 22 flujos. No registres en `L9.2` los flujos de esta tabla salvo que yo decida reabrir alguno (entonces `pc ciclo` en su trabajo de origen). Antes de dar un resultado del 07-10 por vigente, comprueba en Fabric que el flujo no volvió a correr después (commit de la salida): si corrió, dímelo.
Sirven además como entrada ya medida: `ssf_afiliados_ssf_empresas_01` (#24–#26) alimenta al histórico 04 (corte 2026-08: 81.380 / 76.416, las mismas 4.964), y `ZSUB_P_TAB_CTRL` (`L11-complemento`) es la pareja de DET_APO.

## Cómo se agrupan los hallazgos (para repartir a los cotejadores)
El documento trae por tabla la prueba y el criterio; no los repito. Lo que sí importa para ordenar el trabajo:

- **Periodo oficial desde 2023 (📅):** #3, #9, #10, #11, #17, #19, #20. Mide el mínimo y el máximo de la fecha/periodo en cada lado y **cuenta por año o periodo en los dos lados**. Si a Fabric le falta 2023, eso es un hallazgo que se registra con cifras; no recortes la ventana de Stratio para que cuadre. La ventana común se coteja aparte (conteo y huella), y me presentas las dos cifras: con y sin ventana.
- **Copy en append defectuoso (un solo corte + duplicados exactos):** #22, #28, #30 (Postgres publicadas `SSF.*_HISTORICO`). Conteo por `FECHA_CORTE_REPORTE` y duplicados exactos a cada lado; mira la actividad Copy en la definición del pipeline (modo de escritura, pre-copy script).
- **Faltan filas sin causa, mismo corte:** #24–#27 (4.964 empresas: se ubican con el cruce de `NUM_IDENTIFICACION` en la #24 y las demás heredan), #4, #31, #37, #23, #29.
- **Cruce que pierde dato (nulos que suben sin que bajen las filas):** #3, #4, #20, #32–#36, #38, #39. No basta contar nulos: identifica en el código qué entrada llena la columna, mide esa entrada a cada lado (fecha y conteo) y dime si es entrada atrasada (corte) o cruce roto (defecto).
- **Duplicados distintos:** #8 (587 copias), #16 (5.466 filas de más e ID-02), #18 (julio 2026), #10, #21. **Duplicados exactos, no estimados** (nada de HLL ni `NO_EVALUABLE`).
- **Columnas que el origen actualiza tras la extracción:** #7 (`IL_ESTADO`, `IL_WORK_DATE`): cotejo por llave de transacción de las filas que difieren; registra qué corrida escribió el archivo medido.
- **Ingesta = paridad exacta** (#7, #8, #9, #11–#16): SHA-256 obligatorio. Si los dos lados no leen el mismo insumo al mismo corte, la paridad no se puede demostrar: dímelo antes de medir (ver #14/#15: Stratio no procesa el spool desde el 15-09).
- **Repetidas en el lote 10.1:** #1 y #2 heredan la decisión de las #1 y #9 de `Hallazgos_Lote10.1.md`; mira qué midió `L10-1` y no dupliques ejecuciones: dime si basta traer ese resultado. Relacionadas: #16 ↔ `servicios_dfkkop`, #20 ↔ `cuotas_pacs_consolidado_ssf` (`PERIODO_CLAVE`), #24 ↔ `ssf_afiliados_02`/`ssf_pacs`, #11 ↔ `log_liquidacion_subsidio`.
- **Cruce con el lote 8:** `ssf_afiliados_ssf_empresas_01` (#24–#26) es el #30 del lote 8; `medios_pago` (#19) es la entrada que deja `medio_Pago` vacío en ventas y recaudos. Lo que midas aquí lo reutiliza la sesión del lote 8.3.
- **Documentos que el revisor echa de menos:** `diagnosticos/sap_pscd_zsub_p_det_apo_periodos.json` (#8), `diagnosticos/valor_mercadeo_medios_pago.json` (#19), `REPORTE_PG_ANALITICA.md` (#34). Búscalos en disco (`~/Projects`); si existen, van al anexo; si no, se rehace la medición.

## Plan de ejecución (muéstramelo ordenado y espera mi «sí»; nada en paralelo dentro de Fabric)
Antes de ejecutar, por cada flujo: última corrida en Fabric (estado, fecha) y fecha del último dato en Stratio. Si desarrollo no ha tocado un flujo desde el 26-09, re-ejecutarlo solo refresca el corte: dímelo, porque varios hallazgos (Copy en append, cruces rotos, falta 2023) seguirán igual y lo que toca es medir la causa y devolver.

0. **Cierre con lo ya medido** (lotes 11 y 10.1): #8, #22, #23, #27–#30, #1, #2. Sin ejecutar nada.
1. **Ingestas primero** (son entradas de lo demás): spool-corbanco-consumo (pregúntame primero qué archivo del spool hay en cada lado), 01-landing-feco-tpos-header, 21-landing-sappscd-zsub-bi-empresas, ingesta_educacion, 30-trusted-sappscd-zsub-informetipi, 06-trusted-sappscd-dfkkop.
2. **Analítica sin dependencia en el lote:** exogena_ingresos, ingesta_cobertura, medios_pago, reporte_cuota_anulados_ssf, reporte_cuota_detalle_ssf, reporte_ya_preinscriptos_cm_27B, reporte_proximos_preinscribir_cm_27a, tableros_cartera_26, tableros_fovis_prevalidadorFovis_21, transformacion_contact_comercial, trusted_datarmat_credito_clientes, metricas_td.
3. **Cadenas:** ssf_afiliados_ssf_empresas_01 (los históricos 04, 05 y 06 ya están medidos: no se re-ejecutan). Después de spool-corbanco: cliente_servicios y empresa_servicios (comparten entradas de fosfec, vivienda y mercadeo: mide esas entradas una sola vez).
Si una entrada está vacía o vieja y su productor no está en el plan, dímelo antes: decido yo.

## Tamaños: avísame antes de descargar (tablas, MB, vía, tiempo) y espera confirmación en las grandes
`sap_pscd_dfkkop_trusted` (342 M filas), `corporativo_cuotas_pacs_ssf` (47 M), `mercadeo_medios_pago` (40 M), `comercial_cobertura_matriz_lealtad` (11 M). (DET_APO y los históricos SSF ya están medidos; mira si su caché sigue en `cache/L11-*` antes de pensar en volver a bajar algo.) Para DFKKOP proponme, con cifras, si se baja completo o si el hallazgo se responde con conteo y huella por partición (día `BUDAT`) más la descarga de solo las particiones que difieren; lo decido yo. No es cambiar el criterio: el SHA-256 completo sigue siendo obligatorio para aprobar una ingesta.

## Lecciones de L8.2 (aplícalas)
- La VPN se cae con tráfico sostenido contra la Postgres de Stratio (cinco caídas el 08-10). **Una sola cosa a la vez contra esa base**; las tablas grandes se extraen por trozos de `ctid` reanudables (`trabajos/_sesion_2026-10-08/bajar_detalle_paralelo.py` con 1 o 2 conexiones, nunca 4) y se miden en local, **no dentro de la base**. La extracción en un solo COPY no se reanuda. Si la sesión del lote 8.3 está bajando `public_detalle_aportes`, coordina conmigo los turnos.
- Rocket (HDFS) necesita VPN y cookies (1 a 3; duran 2–3 h; 8 hilos repartidos): prioriza Stratio mientras haya VPN.
- Procesos largos con `setsid`/`nohup` y log; matar solo por PID. 19 GB de RAM: más de 50 M de filas, un objeto a la vez (`medir_ventas_1x1.sh`); cotejadores con DuckDB ≤ 4 GB.
- Postgres de Fabric grande: nivel 0/1 troceado por `ctid` (M-010, ya en el código local).
- Un cotejador por tabla o por flujo, con el # del hallazgo, su «prueba a realizar» y su «criterio para cerrar» copiados del documento; comprueba tú lo que devuelva antes de registrarlo. Que no dejen datos personales en el scratchpad.

## Lo que no se negocia
- Se valida la corrida que escribió el dato que se mide; Fabric medido **después** de la última corrida; los dos lados el mismo día cuando el hallazgo lo pide (#1, #2, #11, #16) — si no se puede, dilo con las dos fechas.
- Mismo motor y parámetros a cada lado (v15, SHA-256 completo y huella por columna). Stratio «sin huella» no se repite.
- Advertencia o medición distinta = diferencia registrada con conteo exacto, hasta 5 ejemplos y causa. `pc v4 incompletos` en COMPLETO antes de publicar.
- Causa **medida** de fecha/corte del insumo, ventana, o representación sin pérdida (p. ej. vacío ↔ NULL en #17) → propuesta JUSTIFICADA. Defecto del flujo de Fabric (Copy que duplica, cruce roto, columna que colapsa, histórico sin cargar dentro del periodo oficial) o causa no medida → propuesta DEVUELTO o PENDIENTE. **Las decisiones son mías, una por una**, con el expediente (`pc decision --trabajo L9.2`). No cambies umbrales, exclusiones de columnas ni ventanas para que algo cumpla (en #7 el revisor ofrece excluir `IL_ESTADO`/`IL_WORK_DATE` de la huella: eso es decisión mía, preséntame las dos huellas).
- «No se evaluó» nunca es «cumple».

## Qué me entregas
1. Por flujo: estado, corrida validada (hora, run), comprobaciones que no cumplen y por qué.
2. Por tabla: resumen exacto y diferencias registradas con su propuesta.
3. `~/Projects/reportes/Lote9.2_<fecha>.md` (documento vivo): un bloque por hallazgo #1 a #39 con «prueba a realizar» → resultado en cifras, «criterio para cerrar» → se cumple / no se cumple / no se pudo evaluar (por qué), y los enlaces (1 por flujo y 3 por tabla: cotejo, métrica Stratio, métrica Fabric). Arriba, el resumen por grupo de causa del documento y qué falta de cada flujo no aprobado.
4. Lo que haya que devolver a desarrollo, redactado por flujo con la evidencia (archivo del código, paso y cifra).
5. El acta 9.2 (.docx) solo cuando yo cierre las decisiones.

