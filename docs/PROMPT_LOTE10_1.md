Remedición del lote 10.1 con el proceso corregido. Eres el coordinador (CLAUDE.md).

## Qué quiero al final
Las 34 tablas del lote 10.1 (17 flujos) que el Reporte 10.1 marcó «🔁 VOLVER A REALIZAR PRUEBA», cada una con su
cotejo en formato 2 y una de dos salidas:
- cerrada con causa **medida** (ejemplo de los dos lados), o
- devuelta a desarrollo con la condición exacta que falta.

Lo que no se pueda cerrar, me lo dices tal cual. El criterio de cierre de cada tabla es el de la columna «Criterio para
cerrar» de `Hallazgos · Lote 10.1` (fuente: `ReporteReconciliacionDatos10.1.html`, 2026-10-05). No lo relajes.

Lee antes de empezar: `docs/PROMPTS.md`, `docs/RESUMEN_SESION_2026-10-07.md`, `.claude/agents/etl-validador.md` y
`.claude/agents/cotejador.md`. El formato 2 está en `pc/reportes/formato2.py`.

## Antes de nada: con qué cuentas y con qué no
- **Otro coordinador está activo** con `L11-complemento` y `L11-resto`. Comparten los **8 hilos de Rocket** y `pc` no
  los cuenta entre procesos. **No descargues de HDFS de Stratio mientras el otro esté descargando**: pregúntame primero.
  Postgres de Stratio (psycopg2 por VPN), SFTP y todo lo de Fabric/OneLake **sí** pueden ir en paralelo.
- **Cookies**: solo hacen falta para HDFS (Rocket). Revisa `pc stratio cookie`. Si quedan < 15 min, pídemelas.
- **`pc` no ejecuta flujos en Stratio.** Donde el criterio pide «corridas del mismo día», la corrida de Stratio es la
  programada de producción. Averigua su fecha de escritura y alinea la de Fabric a ese día. Si no se puede, dímelo.
- Las mediciones previas están en `~/Projects/validacion_lote9/{origen,destino,cotejos}/` (corridas 00602a89 y
  16911d90, medidas con DuckDB y etiquetadas «lote9»). Sirven de referencia, **no** como medición del 10.1.

## Trabajo nuevo `L10-1` · rutas (tomadas de las mediciones del lote 10; confírmalas con `pc roles --flujo F`)

| # | FL | Flujo en Fabric | Flujo en Stratio | Tabla (clave) | Ruta Stratio | Ruta Fabric |
|---|---|---|---|---|---|---|
| 1 | FL-0476 | calculo_trab_ben_cuota_monetaria | 06-calculo-trab-ben-cuota-monetaria | agrupadoras_dc_score_agrupadoras_lista_detalle_subsidios_trabajadores | `pg:public.dc_score_agrupadoras_lista_detalle_subsidios_trabajadores` | `pg:agrupadoras.dc_score_agrupadoras_lista_detalle_subsidios_trabajadores` |
| 2 | FL-0340 | ssf_afiliados_ssf_afiliados_02 | 02-ssf-afiliados-ssf-afiliados | ssf_sftp_ssf_afiliados_categoria | `sftp:/home/comfandi/SSF/SSF_AFILIADOS` · `SSF_AFILIADOS_CATEGORIA.csv` | `sftp:/home/comfandi/pruebas_escritura_migracion/dev/SSF/SSF_AFILIADOS` · mismo archivo |
| 3 | FL-0340 | ssf_afiliados_ssf_afiliados_02 | 02-ssf-afiliados-ssf-afiliados | ssf_sftp_ssf_afiliados_csv | `sftp:…/SSF/SSF_AFILIADOS` · `ssf_afiliados.csv` | `sftp:…/dev/SSF/SSF_AFILIADOS` · mismo archivo |
| 4 | FL-0340 | ssf_afiliados_ssf_afiliados_02 | 02-ssf-afiliados-ssf-afiliados | ssf_sftp_ssf_afiliados_rango | `sftp:…/SSF/SSF_AFILIADOS` · `SSF_AFILIADOS_RANGO.csv` | `sftp:…/dev/SSF/SSF_AFILIADOS` · mismo archivo |
| 5 | FL-0340 | ssf_afiliados_ssf_afiliados_02 | 02-ssf-afiliados-ssf-afiliados | ssf_sftp_ssf_afiliados_sin_salario | `sftp:…/SSF/SSF_AFILIADOS` · `SSF_AFILIADOS_SIN_SALARIO.csv` | `sftp:…/dev/SSF/SSF_AFILIADOS` · mismo archivo |
| 6 | FL-0340 | ssf_afiliados_ssf_afiliados_02 | 02-ssf-afiliados-ssf-afiliados | ssf_errores_afiliados | `sftp:/home/comfandi/SSF_ERRORES/SSF_AFILIADOS` · `ERRORES_CORREGIDOS_AFILIADOS.csv` | `sftp:…/dev/SSF_ERRORES/SSF_AFILIADOS` · mismo archivo |
| 7 | FL-0340 | ssf_afiliados_ssf_afiliados_02 | 02-ssf-afiliados-ssf-afiliados | ssf_afiliados | `pg:SSF.AFILIADOS` | `pg:SSF.AFILIADOS` |
| 8 | FL-0340 | ssf_afiliados_ssf_afiliados_02 | 02-ssf-afiliados-ssf-afiliados | afiliados_ssf_afiliados_hdfs | `hdfs:/data/prod/trusted/afiliados/SSF_AFILIADOS` | `delta:gold.afiliados_ssf_afiliados` |
| 9 | FL-0352 | tableros_afiliados_empresas_01 | 01-tableros-afiliados-empresas | corporativo_empresas | `pg:corporativo.empresas` | `pg:corporativo.empresas` |
| 10 | FL-0428 | core_validaciones_afiliados_02 | 02-core-validaciones-afiliados | core_validaciones_validacion_afiliado_hdfs | `hdfs:/data/prod/trusted/core/Validaciones/validacion_afiliado` | `delta:gold.core_validaciones_validacion_afiliado` |
| 16 | FL-0428 | core_validaciones_afiliados_02 | 02-core-validaciones-afiliados | corporativo_validacion_afiliado | `pg:corporativo.validacion_afiliado` | `pg:corporativo.validacion_afiliado` |
| 11 | FL-0375 | sabana_sub_especie_dinamico | 34-sabana-sub-especie-dinamico | corporativo_subsidio_especie_dinamico_integrantes | `pg:corporativo.subsidio_especie_dinamico_integrantes` | `pg:corporativo.subsidio_especie_dinamico_integrantes` |
| 12 | FL-0375 | sabana_sub_especie_dinamico | 34-sabana-sub-especie-dinamico | subsidios_subsidio_especie_dinamico_integrantes | `hdfs:/data/prod/trusted/subsidios/subsidio_especie_dinamico_integrantes` | `delta:silver.subsidios_subsidio_especie_dinamico_integrantes` |
| 13 | FL-0489 | trusted_datarmat_credito_cartera_fact | 05-trusted-datarmat-credito-cartera(fact) | credito_tablas_finales_cartera | `hdfs:/data/prod/trusted/credito/tablas_finales/cartera` | `delta:silver.credito_tablas_finales_cartera` |
| 14 | FL-0400 | periodo_contable_cierre | periodo-contable-cierre | corporativo_periodo_cierre_prueba | `pg:corporativo.periodo_cierre_prueba` | `pg:corporativo.periodo_cierre_prueba` |
| 35 | FL-0400 | periodo_contable_cierre | periodo-contable-cierre | corporativo_aporte_reportes_pivot_dian | `pg:corporativo.aporte_reportes_pivot_DIAN` | `pg:corporativo.aporte_reportes_pivot_DIAN` |
| 15 | FL-0133 | 15-landing-sappscd-dfkkop | 15-landing-sappscd-dfkkop | servicios_dfkkop | `pg:Servicios.DFKKOP` | `pg:Servicios.DFKKOP` |
| 17 | FL-0646 | core_validaciones_validador_subsidio_06b | 06B-core-validaciones-validador-subsidio | corporativo_log_liquidacion_subsidio | `pg:corporativo.log_liquidacion_subsidio` | `pg:corporativo.log_liquidacion_subsidio` |
| 18 | FL-0452 | envios | 04-envios | sat_envio_afiliacion_no_primeravez | `pg:sat.envio_afiliacion_no_primeravez` | `pg:sat.envio_afiliacion_no_primeravez` |
| 21 | FL-0452 | envios | 04-envios | sat_envio_afiliacion_primeravez | `pg:sat.envio_afiliacion_primeravez` | `pg:sat.envio_afiliacion_primeravez` |
| 23 | FL-0452 | envios | 04-envios | sat_envio_aportes | `pg:sat.envio_aportes` | `pg:sat.envio_aportes` |
| 24 | FL-0452 | envios | 04-envios | sat_envio_inicio_relacion_laboral | `pg:sat.envio_inicio_relacion_laboral` | `pg:sat.envio_inicio_relacion_laboral` |
| 25 | FL-0452* | reenvios | Reenvios | sat_re_envio_inicio_relacion_laboral | `pg:sat.re_envio_inicio_relacion_laboral` | `pg:sat.re_envio_inicio_relacion_laboral` |
| 26 | FL-0452* | reenvios | Reenvios | sat_re_envio_aportes | `pg:sat.re_envio_aportes` | `pg:sat.re_envio_aportes` |
| 19 | FL-0364 | tableros_web_service_16 | 16-tableros-web-service | subsidios_informeexperiencia | `pg:Subsidios.InformeExperiencia` | `pg:Subsidios.InformeExperiencia` |
| 20 | FL-0364 | tableros_web_service_16 | 16-tableros-web-service | subsidios_informeexperienciahistorico | `pg:Subsidios.InformeExperienciaHistorico` | `pg:Subsidios.InformeExperienciaHistorico` |
| 27 | FL-0341 | ssf_afiliados_ssf_pacs_03 | 03-ssf-afiliados-ssf-pacs | ssf_pacs | `pg:SSF.PACS` | `pg:SSF.PACS` |
| 28 | FL-0341 | ssf_afiliados_ssf_pacs_03 | 03-ssf-afiliados-ssf-pacs | afiliados_ssf_pac_hdfs | `hdfs:/data/prod/trusted/afiliados/SSF_PAC` | `delta:gold.afiliados_ssf_pac` |
| 29 | FL-0341 | ssf_afiliados_ssf_pacs_03 | 03-ssf-afiliados-ssf-pacs | ssf_sftp_ssf_pac_csv | `sftp:/home/comfandi/SSF/SSF_PACS` · `SSF_PAC.csv` | `sftp:…/dev/SSF/SSF_PACS` · mismo archivo |
| 30 | FL-0341 | ssf_afiliados_ssf_pacs_03 | 03-ssf-afiliados-ssf-pacs | ssf_errores_pacs | `sftp:/home/comfandi/SSF_ERRORES/SSF_PACS` · `ERRORES_CORREGIDOS_PACS.csv` | `sftp:…/dev/SSF_ERRORES/SSF_PACS` · mismo archivo |
| 31 | FL-0441 | ssf_facts_20 | 20-ssf-facts | ssf_pa_facts | `pg:SSF.pa_facts` | `pg:SSF.pa_facts` |
| 32 | FL-0494 | mdt_final | mdt_final | credito_mdt_final | `hdfs:/data/prod/trusted/credito/archivos_planos_datamart/MDT_final` | `delta:silver.credito_archivos_planos_datamart_mdt_final` |
| 33 | FL-0497 | predicciones_k_means | predicciones_k_means | credito_clusters_k_means_v3_nuevos | `hdfs:/data/prod/trusted/credito/archivos_planos_datamart/clusters_k_means_v3_nuevos` | `delta:silver.credito_archivos_planos_datamart_clusters_k_means_v3_nuevos` |
| 34 | FL-0388 | reporte_cuota_consolidado_ssf | 03-reporte-cuota-consolidado-ssf | corporativo_cuotas_pacs_consolidado_ssf | `pg:corporativo.cuotas_pacs_consolidado_ssf` | `pg:corporativo.cuotas_pacs_consolidado_ssf` |

`…/dev/` = `/home/comfandi/pruebas_escritura_migracion/dev/`. Grupo: todas analítica, salvo la #15 (ingesta: paridad
exacta y SHA-256 obligatorio). La #22 (`sat_envio_fin_relacion_laboral`) ya está en Integridad OK: **no entra**.

**Rutas que no doy por buenas sin que las confirmes:**
- #33 Fabric: en el lote 10 se midió una **copia parquet** (`Files/validador/lote10/delta_udt/…/v4`, KM-03). Hay que medir la
  Delta de arriba: es el valor de `clusters_k_means_v3_nuevos` en `vl_credito`, que escribe `predicciones_k_means`.
- #2–#6, #29, #30 Fabric: es una **ruta de pruebas**. Pregúntame en qué ruta SFTP se mide antes de registrar.
- #1: Stratio escribe en `public` y Fabric en `agrupadoras`. Confírmalo con el código y regístralo como hecho del contrato.
- #25 y #26: el inventario da a `reenvios` el mismo FL que a `envios` (FL-0452). Regístralo con ese FL, pero avísame.
- #13: unos 52 M de filas en Stratio. Avísame tamaño y tiempo antes de descargar.

## Cómo repartirlo (muéstramelo en una lista y espera mi «sí»)

**Bloque A · Solo análisis, sin re-ejecutar** (Postgres de los dos lados, sin Rocket; puede ir en paralelo con el otro coordinador):
#1 (cruce GPART_E y MES01–MES12 por empresa), #9 (ID-05 con llave compuesta `bp` + `fecha_inicio_estado`, y `desc_clase_empresa`),
#11 (edades por id), #14 (filas y `total_aportes` por fecha y periodo; el registro de 149.667.246.269), #21 (radicado 0012763665),
#23, #24 y #25 (cruce de radicados y documentos), #31 (corte 2026-08-01, duplicados, nulos de VALOR), #35 (las 11.206 filas sin municipio).

**Bloque B · Con HDFS de Stratio (Rocket; en serie con el otro coordinador)**:
#12 (edades por id, pareja de la #11), #13 (hash por columna con el tope subido o por partición de periodo; conteo por `periodo_mensual`).

**Bloque C · Re-ejecución el mismo día que la corrida de Stratio** (primero `pc etl` en Fabric, luego medir los dos lados
inmediatamente, con la fecha de escritura de cada salida):
- `ssf_afiliados_ssf_afiliados_02` (#2–#8) → luego `ssf_afiliados_ssf_pacs_03` (#27–#30). Es una cadena: pacs depende de afiliados.
- `core_validaciones_afiliados_02` (#10, #16).
- `tableros_afiliados_empresas_01` (#9): confirma qué entrada lee Fabric y con qué fecha. Deja un solo resultado vigente (lote 9 o 10).

**Bloque D · Bloqueadas hasta que desarrollo corrija.** No re-ejecutes hasta que yo confirme la corrección; preséntamelas como devolución:

| # | Qué tiene que pasar antes |
|---|---|
| 7 | Retirar `ZZ_TEST_MARKER` de `SSF.AFILIADOS` en Fabric |
| 8 | Corregir o declarar el contrato (`ARE_GEOGRAFICA_RESIDENCIA`, `BP_AFILIADO` bigint → string) |
| 15 | Re-ingesta de DFKKOP sin limpieza manual (DK-01), con SHA-256 y CP-05, ID-03, ID-04 e ID-06 medidos |
| 16 | Poblar o retirar `ValHomonimo6` |
| 17 | Que `Sueldo`, `Discapacidad` y `Causa` lleguen con valor, y `ZSUB_INFORMETIPI` con todo el histórico |
| 18, 26 | Entradas SAT de Fabric a la misma fecha que Stratio (EN-01); la #26 necesita saber por qué Stratio queda vacía |
| 19, 20 | Ventana de QA en la Variable Library ajustada al mismo mes de `Fecha_Consumo` |
| 32, 33 | Corrida oficial de `mdt_final` (no de desarrollo), sin las 184 filas parciales del 24-09; luego `predicciones_k_means` sobre la Delta |
| 34 | `PERIODO_CLAVE` corregido en Fabric |

## Reglas para este lote
- Roles por el código del flujo y el `_delta_log`, no por el nombre del parámetro.
- Cada cifra exacta y con ejemplo de los dos lados. «No se evaluó» no es «cumple».
- No cambies ventanas, umbrales ni exclusiones para que una tabla pase. La #14 ya tiene la ventana ≤ 2026-06-30 del
  acta: úsala, no la amplíes. Si hace falta otra regla, propónmela como mejora.
- Tablas grandes (> 100 M filas o 5 GB): solo con mi confirmación. Un cotejador a la vez en tablas grandes.
- Cada diferencia nueva me la presentas de a una, con lo que propones, y esperas.

Arranca con lo de siempre (mejoras pendientes, `fab auth status`, VPN, cookies) y con `pc trabajo crear --trabajo L10-1`.
Primero el bloque A: no necesita Rocket.
