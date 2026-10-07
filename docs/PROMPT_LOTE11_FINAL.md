Cierre del lote 11 con el proceso corregido el 2026-10-06. Eres el coordinador (CLAUDE.md).

## Qué quiero al final
Los 23 flujos del lote 11 con su cotejo de flujo y su cotejo por tabla en formato 2, completos y publicados, y el
acta del lote 11. Valida todo desde el comienzo: cada control con lo que midió cada lado, cada diferencia con
cifras y ejemplo, y cada flujo con su corrida, dependencias y cadena. Lo que no se pueda cerrar, dímelo tal cual.

Lee antes de empezar: `docs/PROMPTS.md`, `docs/RESUMEN_SESION_2026-10-06.md`, `.claude/agents/etl-validador.md` y
`.claude/agents/cotejador.md`. El formato 2 está en `pc/reportes/formato2.py`.

Son dos partes. La A no necesita VPN ni cookies: empieza por ella mientras te paso las cookies para la B.

## Parte A · Completar los 7 flujos ya medidos (trabajo `L11-complemento`, sin re-ejecutar ni descargar)
Están ejecutados, medidos y cotejados el 06-10, con los dos lados en la caché local. No abras ciclo nuevo
(`pc ciclo` borraría la caché): se completa la versión 2. `python -m pc v4 incompletos --trabajo L11-complemento`
da la lista exacta de lo que falta; al empezar era esto:

| FL | Flujo en Fabric | Flujo en Stratio | Grupo | Revalida lote | Tabla | Ruta Stratio | Ruta Fabric |
|---|---|---|---|---|---|---|---|
| FL-0155 | 06-landing-sappscd-zsub-p-det-apo | 06-landing-sappscd-zsub-p-det-apo | ingesta | 9 | sap_pscd_zsub_p_det_apo | `hdfs:/data/prod/landingraw/sap/pscd/ZSUB_P_DET_APO` | `files:Files/bronze/sap/pscd/ZSUB_P_DET_APO` |
| FL-0156 | 07-landing-sappscd-zsub-p-tab-ctrl | 07-landing-sappscd-zsub-p-tab-ctrl | ingesta | 8 | sap_pscd_zsub_p_tab_ctrl | `hdfs:/data/prod/landingraw/sap/pscd/ZSUB_P_TAB_CTRL` | `files:Files/bronze/sap/pscd/ZSUB_P_TAB_CTRL` |
| FL-0464 | origenes | 00-origenes | analitica | 7 | agrupadoras_origenes | `hdfs:/data/prod/trusted/agrupadoras/origenes` | `delta:silver.agrupadoras_origenes` |
| FL-0465 | destinos | 01-destinos | analitica | 7 | agrupadoras_destinos_agru | `hdfs:/data/prod/trusted/agrupadoras/destinos_agru` | `delta:silver.agrupadoras_destinos_agru` |
| FL-0465 | destinos | 01-destinos | analitica | 7 | agrupadoras_destinos_norm | `hdfs:/data/prod/trusted/agrupadoras/destinos_norm` | `delta:silver.agrupadoras_destinos_norm` |
| FL-0466 | moves | 03-moves | analitica | 6 | agrupadoras_historico_movimiento_alt | `hdfs:/data/prod/trusted/agrupadoras/historico_movimiento_alt` | `delta:silver.agrupadoras_historico_movimiento_alt` |
| FL-0466 | moves | 03-moves | analitica | 6 | agrupadoras_moves_agrup | `hdfs:/data/prod/trusted/agrupadoras/moves_agrup` | `delta:silver.agrupadoras_moves_agrup` |
| FL-0466 | moves | 03-moves | analitica | 6 | agrupadoras_historico_movimiento2 | `hdfs:/data/prod/trusted/agrupadoras/historico_movimiento2` | `delta:silver.agrupadoras_historico_movimiento2` |
| FL-0469 | tasas | 02-tasas | analitica | 6 | agrupadoras_tasa_empresas | `hdfs:/data/prod/trusted/agrupadoras/tasa_empresas` | `delta:silver.agrupadoras_tasa_empresas` |
| FL-0470 | sabana_pila | 03-sabana-pila | analitica | 6 | agrupadoras_movimiento_persona_alt | `hdfs:/data/prod/trusted/agrupadoras/movimiento_persona_alt` | `delta:silver.agrupadoras_movimiento_persona_alt` |

1. **Evidencia del flujo** de destinos, moves y sabana_pila: `pc etl evidencia` se quedó colgado en `destinos` el
   06-10 (más de 3 horas, sin error). Averigua en qué llamada se cuelga antes de repetirlo; no lo dejes corriendo a ciegas.
2. **Validador sobre la corrida aprobada**: en los 5 flujos de agrupadoras el validador corrió a las 05:55 UTC y la
   corrida aprobada es la del orquestador (11:10–12:32 UTC). Valídalos sin re-ejecutar (`pc etl lanzar --plan`) y
   comprueba que la evidencia siga diciendo que ninguna entrada ni salida cambió después. Es la primera vez que se
   valida así: si el veredicto no sirve para esto, para y cuéntame.
3. **Advertencias sin registrar** en las 10 tablas: ID-05 en todas, ID-02 en 6, ID-04 en 7, ID-03 en 2. Con el
   agente cotejador, sobre la caché: conteo exacto, ejemplo de los dos lados y explicación. Para ID-05 prueba la llave
   compuesta que tenga sentido; para duplicados y nulos, dime si son las mismas filas en los dos lados.
4. **Tres justificaciones de moves sin ejemplo** (la D2 de cada una de sus tres tablas): agrégales ejemplo medido.
5. **Ingestas**: el archivo de origen del SFTP no está medido (necesita VPN: déjalo para cuando la tenga) y TAB_CTRL
   tiene CP-05 sin evaluar.
6. Las causas de destinos y moves todavía dicen que la ingesta «falla»; se escribieron antes de la corrección de la
   tarde. Preséntame el texto corregido; no lo cambies sin que yo lo vea.

Las justificaciones que ya decidí el 06-10 siguen valiendo: no me las vuelvas a preguntar. Lo nuevo (los puntos 3 a 6)
sí me lo presentas, una diferencia a la vez, con lo que propones.

## Parte B · Los otros 16 flujos (trabajo nuevo `L11-resto`)
Se validaron el 02-10 con el proceso anterior y sus mediciones no están en este pipeline: hay que medirlos de nuevo.
Rutas tomadas del acta 11; confírmalas contra el código (`pc roles --flujo F`).

| FL | Flujo en Fabric | Flujo en Stratio | Grupo | Revalida lote | Tabla | Ruta Stratio | Ruta Fabric |
|---|---|---|---|---|---|---|---|
| FL-0039 | ingesta-novar | ingesta-novar | ingesta | 6 | novar_saenlinea_comfandi_reporte_197_competencias_desempenos | `hdfs:/data/prod/landingraw/novar/saenlinea_comfandi_reporte_197_competencias_desempenos` | `files:Files/bronze/novar/saenlinea_comfandi_reporte_197_competencias_desempenos` |
| FL-0039 | ingesta-novar | ingesta-novar | ingesta | 6 | novar_saenlinea_comfandi_reporte_468_observador | `hdfs:/data/prod/landingraw/novar/saenlinea_comfandi_reporte_468_observador` | `files:Files/bronze/novar/saenlinea_comfandi_reporte_468_observador` |
| FL-0039 | ingesta-novar | ingesta-novar | ingesta | 6 | novar_siga_comfandi_reporte_432_estudiantes_retiro_registrado | `hdfs:/data/prod/landingraw/novar/siga_comfandi_reporte_432_estudiantes_retiro_registrado` | `files:Files/bronze/novar/siga_comfandi_reporte_432_estudiantes_retiro_registrado` |
| FL-0039 | ingesta-novar | ingesta-novar | ingesta | 6 | novar_saenlinea_comfandi_reporte_315_dane | `hdfs:/data/prod/landingraw/novar/saenlinea_comfandi_reporte_315_dane` | `files:Files/bronze/novar/saenlinea_comfandi_reporte_315_dane` |
| FL-0458 | last_partner | 02-last-partner | analitica | 6 | agrupadoras_last_partner | `hdfs:/data/prod/trusted/agrupadoras/last_partner` | `delta:silver.agrupadoras_last_partner` |
| FL-0461 | info_general_empresas | 05-info-general-empresas | analitica | 6 | agrupadoras_info_general_empresas | `hdfs:/data/prod/trusted/agrupadoras/info_general_empresas` | `delta:silver.agrupadoras_info_general_empresas` |
| FL-0462 | info_salarial | 06-info-salarial | analitica | 6 | agrupadoras_ingresos | `hdfs:/data/prod/trusted/agrupadoras/ingresos` | `delta:silver.agrupadoras_ingresos` |
| FL-0462 | info_salarial | 06-info-salarial | analitica | 6 | agrupadoras_variacion_salarial | `hdfs:/data/prod/trusted/agrupadoras/variacion_salarial` | `delta:silver.agrupadoras_variacion_salarial` |
| FL-0468 | vacaciones | 01-vacaciones | analitica | 6 | agrupadoras_vacaciones_empresas | `hdfs:/data/prod/trusted/agrupadoras/vacaciones_empresas` | `delta:silver.agrupadoras_vacaciones_empresas` |
| FL-0468 | vacaciones | 01-vacaciones | analitica | 6 | agrupadoras_vacaciones_empresas_2026_09_22 | `hdfs:/data/prod/trusted/agrupadoras/vacaciones_empresas` | `delta:silver.agrupadoras_vacaciones_empresas` |
| FL-0473 | agrupadoras_trusted_empresasactivas | 03-agrupadoras-trusted-empresasactivas | analitica | 6 | agrupadoras_dcen_empresas_trabajadores_activos_agrupa | `pg:public.dcen_empresas_trabajadores_activos_agrupa` | `delta:gold.agrupadoras_dcen_empresas_trabajadores_activos_agrupa` |
| FL-0473 | agrupadoras_trusted_empresasactivas | 03-agrupadoras-trusted-empresasactivas | analitica | 6 | agrupadoras_dcen_empresas_trabajadores_activos_agrupa_pg | `pg:public.dcen_empresas_trabajadores_activos_agrupa` | `pgfab:agrupadoras.dcen_empresas_trabajadores_activos_agrupa` |
| FL-0474 | score_agrupadoras_activas_postgres | 04-score-agrupadoras-activas-postgres | analitica | 6 | agrupadoras_dc_score_agrupadoras_activas | `pg:public.dc_score_agrupadoras_activas` | `delta:gold.agrupadoras_dc_score_agrupadoras_activas` |
| FL-0474 | score_agrupadoras_activas_postgres | 04-score-agrupadoras-activas-postgres | analitica | 6 | agrupadoras_dc_score_agrupadoras_activas_pg | `pg:public.dc_score_agrupadoras_activas` | `pgfab:agrupadoras.dc_score_agrupadoras_activas` |
| FL-0477 | calculo_pila | 07-calculo-pila | analitica | 6 | agrupadoras_dc_calculos_pila_agrupadoras | `pg:public.dc_calculos_PILA_agrupadoras` | `delta:gold.agrupadoras_dc_calculos_pila_agrupadoras` |
| FL-0477 | calculo_pila | 07-calculo-pila | analitica | 6 | agrupadoras_dc_calculos_pila_agrupadoras_pg | `pg:public.dc_calculos_PILA_agrupadoras` | `pgfab:agrupadoras.dc_calculos_PILA_agrupadoras` |
| FL-0478 | subsidio_vivienda | 08-subsidio_vivienda | analitica | 6 | agrupadoras_dc_subsidios_vivienda_agrupadoras | `hdfs:/data/prod/trusted/agrupadoras/dc_subsidios_vivienda_agrupadoras` | `delta:gold.agrupadoras_dc_subsidios_vivienda_agrupadoras` |
| FL-0478 | subsidio_vivienda | 08-subsidio_vivienda | analitica | 6 | agrupadoras_dc_subsidios_vivienda_agrupadoras_pg | `pg:public.dc_subsidios_vivienda_agrupadoras` | `pgfab:agrupadoras.dc_subsidios_vivienda_agrupadoras` |
| FL-0540 | transformacion_formulario_comercial | transformacion_formulario_comercial | analitica | 6 | globales_contactabilidad_formulario_comercial | `hdfs:/data/prod/trusted/globales/contactabilidad/formulario_comercial/registrosValidos` | `delta:silver.globales_contactabilidad_formulario_comercial` |
| FL-0540 | transformacion_formulario_comercial | transformacion_formulario_comercial | analitica | 6 | globales_contactabilidad_formulario_comercial_rechazados | `hdfs:/data/prod/trusted/globales/contactabilidad/formulario_comercial/registrosRechazados` | `delta:silver.globales_contactabilidad_formulario_comercial_rechazados` |
| FL-0565 | homologacion_direcciones | homologacion_direcciones | analitica | 6 | contactabilidad_homologaciondirecciones | `hdfs:/data/prod/trusted/contactabilidad/homologacionDirecciones` | `delta:silver.contactabilidad_homologacion_direcciones` |
| FL-0566 | homologacion_ciudades | homologacion_ciudades | analitica | 6 | contactabilidad_homologacionciudades | `hdfs:/data/prod/trusted/contactabilidad/homologacionCiudades` | `delta:silver.contactabilidad_homologacion_ciudades` |
| FL-0691 | limpieza_remediacion_adr2 | limpieza_remediacion_adr2 | analitica | 6 | sap_crm_contactabilidad_adr2 | `hdfs:/data/prod/trusted/sap/crm/contactabilidad/ADR2/registrosValidos` | `delta:silver.sap_crm_contactabilidad_adr2` |
| FL-0342 | ssf_afiliados_ssf_empresas_historico_04 | 04-ssf-afiliados-ssf-empresas-historico | analitica | 9 | afiliados_ssf_empresas_historico | `hdfs:/data/prod/trusted/afiliados/ssf_empresas_historico` | `delta:gold.afiliados_ssf_empresas_historico` |
| FL-0342 | ssf_afiliados_ssf_empresas_historico_04 | 04-ssf-afiliados-ssf-empresas-historico | analitica | 9 | gold_ssf_empresas_historico | `pg:SSF.EMPRESAS_HISTORICO` | `delta:gold.ssf_empresas_historico` |
| FL-0342 | ssf_afiliados_ssf_empresas_historico_04 | 04-ssf-afiliados-ssf-empresas-historico | analitica | 9 | ssf_empresas_historico | `pg:SSF.EMPRESAS_HISTORICO` | `pgfab:SSF.EMPRESAS_HISTORICO` |
| FL-0342 | ssf_afiliados_ssf_empresas_historico_04 | 04-ssf-afiliados-ssf-empresas-historico | analitica | 9 | ssf_empresas_historico_corte_2026_08 | `pg:SSF.EMPRESAS_HISTORICO` | `pgfab:SSF.EMPRESAS_HISTORICO` |
| FL-0343 | ssf_afiliados_ssf_afiliados_historico_05 | 05-ssf-afiliados-ssf-afiliados-historico | analitica | 9 | afiliados_ssf_afiliados_historico | `hdfs:/data/prod/trusted/afiliados/ssf_afiliados_historico` | `delta:gold.afiliados_ssf_afiliados_historico` |
| FL-0343 | ssf_afiliados_ssf_afiliados_historico_05 | 05-ssf-afiliados-ssf-afiliados-historico | analitica | 9 | gold_ssf_afiliados_historico | `pg:SSF.AFILIADOS_HISTORICO` | `delta:gold.ssf_afiliados_historico` |
| FL-0343 | ssf_afiliados_ssf_afiliados_historico_05 | 05-ssf-afiliados-ssf-afiliados-historico | analitica | 9 | ssf_afiliados_historico | `pg:SSF.AFILIADOS_HISTORICO` | `pgfab:SSF.AFILIADOS_HISTORICO` |
| FL-0343 | ssf_afiliados_ssf_afiliados_historico_05 | 05-ssf-afiliados-ssf-afiliados-historico | analitica | 9 | ssf_afiliados_historico_corte_2026_08 | `pg:SSF.AFILIADOS_HISTORICO` | `pgfab:SSF.AFILIADOS_HISTORICO` |
| FL-0344 | ssf_afiliados_ssf_pacs_historico_06 | 06-ssf-afiliados-ssf-pacs-historico | analitica | 9 | afiliados_ssf_pacs_historico | `hdfs:/data/prod/trusted/afiliados/ssf_pacs_historico` | `delta:gold.afiliados_ssf_pacs_historico` |
| FL-0344 | ssf_afiliados_ssf_pacs_historico_06 | 06-ssf-afiliados-ssf-pacs-historico | analitica | 9 | gold_ssf_pac_historico | `pg:SSF.PAC_HISTORICO` | `delta:gold.ssf_pac_historico` |
| FL-0344 | ssf_afiliados_ssf_pacs_historico_06 | 06-ssf-afiliados-ssf-pacs-historico | analitica | 9 | ssf_pac_historico | `pg:SSF.PAC_HISTORICO` | `pgfab:SSF.PAC_HISTORICO` |
| FL-0344 | ssf_afiliados_ssf_pacs_historico_06 | 06-ssf-afiliados-ssf-pacs-historico | analitica | 9 | ssf_pac_historico_corte_2026_08 | `pg:SSF.PAC_HISTORICO` | `pgfab:SSF.PAC_HISTORICO` |

Plan de ejecución (muéstramelo en una lista y espera mi «sí»; nada en paralelo):
1. **`ingesta-novar`** primero: me pidieron revalidar estas cuatro tablas y son pequeñas. Sirve de prueba de
   `pc etl ejecutar`, que nunca ha corrido en Fabric. El 02-10 la corrida terminó Failed por una tabla fuera de
   alcance (saenlinea_691): mira si vuelve a fallar y por qué.
2. **Seis de agrupadoras que ya corrieron el 06-10 dentro de `orq_agrupadoras`** (Succeeded): last_partner,
   info_general_empresas, info_salarial, vacaciones, agrupadoras_trusted_empresasactivas,
   score_agrupadoras_activas_postgres. No los re-ejecutes si sus tablas no cambiaron desde entonces: valídalos sin
   ejecutar y mide. Si ya pasó el día o algo cambió, dímelo y decidimos si se corre el orquestador otra vez.
3. **Sueltos**, uno por uno: calculo_pila, subsidio_vivienda, transformacion_formulario_comercial,
   homologacion_direcciones, homologacion_ciudades, limpieza_remediacion_adr2. Confirma antes si calculo_pila y
   subsidio_vivienda están dentro de `orq_agrupadoras`.
4. **Históricos SSF**, encadenados: empresas_historico_04, afiliados_historico_05, pacs_historico_06.

Casos especiales del acta anterior; no los apliques en silencio:
- Las tablas `…_corte_2026_08` y `vacaciones_empresas_2026_09_22` eran la misma tabla medida con una ventana de
  fechas. Dime qué ventana propones y con qué cifras antes de usarla.
- FL-0344: `gold_ssf_pac_historico` y `ssf_pac_historico` quedaron en REVISAR (25.023.737 filas en Stratio frente a
  1.133.846 en Fabric) a la espera de un arreglo de desarrollo. Comprueba si ya está aplicado.
- FL-0474: sus dos tablas tenían 30.668 filas en Stratio y 40.003 en Fabric. Explícalo con dato, no con el texto anterior.

## Agentes
Usa los agentes de `.claude/agents/`, uno por paso, y pásale a cada uno el trabajo, el flujo y lo que debe devolver:
etl-validador (plan, veredicto y evidencia) → medidor-rapido-fabric y medidor-rapido-stratio en paralelo → semaforo →
gestor-descargas → medidor-completo → cotejador → publicador-reportes. Postgres de Fabric solo por postgres-fabric.
Los agentes no se llaman entre sí ni deciden por mí; lo que devuelvan lo compruebas tú antes de contármelo.

## Lo que no se negocia
- Se valida la corrida que escribió el dato que se mide.
- Un control que cumple su regla pero queda en alerta en los dos lados, o con medición distinta entre lados, se
  registra como diferencia con conteo exacto, ejemplo y explicación. Una comprobación del flujo que no cumple deja
  el flujo en revisión.
- `pc v4 incompletos` debe decir COMPLETO antes de publicar. Si falta un dato, dime cuál y por qué; no lo rellenes.
- Las decisiones nuevas son mías. Solo se justifica con causa medida; un defecto de código no se justifica.
- No toques `trabajos/L12`.

## Cómo trabajar
Arranca con lo de siempre (mejoras pendientes, `fab auth status`, VPN, cookies). Yo te paso las cookies de Rocket;
pídemelas cuando empieces la parte B. Avísame antes de descargar (tablas, MB, tiempo); los históricos SSF (25–37 M
de filas) necesitan mi confirmación. Avanza sin detenerte en todo lo que no dependa de mí y acumula las decisiones.
Nunca mates procesos por patrón, solo por PID. La publicación es lenta, no colgada.

## Qué me entregas
1. Por flujo: estado, corrida validada (hora y quién la lanzó), comprobaciones que no cumplen y por qué.
2. Por tabla: resumen exacto (100 % igual, o la diferencia con cifras) y las diferencias registradas.
3. `~/Projects/reportes/Links_Lote11_<fecha>.md`: 1 enlace por flujo y 3 por tabla, con FL y nombre del JSON.

## El acta (cuando yo cierre las decisiones)
Acta del lote 11 con el agente `acta-entrega`, en su formato normal, local y sin publicar, con toda la información
completa de los 23 flujos. Lo único especial de este lote: reúne flujos ya entregados en los lotes 6, 7, 8 y 9 que se
revalidaron para mejorar el resultado. Dilo en la presentación del acta y agrega la columna «Revalidación del lote»
por flujo, buscada en `datos_acta_lote6/7/8/9.json`, no supuesta. Solo entran flujos APROBADO o
APROBADO_CON_JUSTIFICACION; lo demás va a pendientes con su motivo. Verifica cada cifra contra su JSON hasta dar 0
discrepancias. El generador del acta todavía lee el formato anterior de los JSON: adáptalo al formato 2 primero.
