# Resumen de la sesión 2026-10-07 · trabajo L10-1 (remedición lote 10.1) · para retomar

Se interrumpe a las ~12:15 UTC: la VPN de Comfandi cayó a las ~11:05 UTC y se apaga el equipo para recuperarla.
Todo el estado está en `trabajos/L10-1/`. Los scripts de apoyo de la sesión y sus registros están en `trabajos/L10-1/sesion_2026-10-07/{scripts,logs}/`; se corren con `PYTHONPATH=. python <script>`.
Prompt del trabajo: `docs/PROMPT_LOTE10_1.md`. Al apagar no queda ningún proceso vivo: la descarga de la #13 se corta y se retoma.

## Decisiones de QA tomadas en la sesión
- Rutas confirmadas contra la pipeline y la Variable Library. SFTP de Fabric: se mide en `/home/comfandi/pruebas_escritura_migracion/dev/…`, que es la ruta que escribe el código. `reenvios` lleva FL-0452.
- Bloque C: se ejecuta hoy y **la diferencia de fecha con Stratio queda justificada**. La última corrida de Stratio fue el 03-10 (SSF afiliados a las 17:03 UTC, pacs a las 17:23 UTC).
- Bloque D: devoluciones a desarrollo listadas en `trabajos/L10-1/devolucion_bloque_D.md`.
- Mensajes al grupo de analítica en `trabajos/L10-1/mensajes_devolucion.md`, con las tablas #1, #9, #24 y #25.
- Las SSF del 10.1 sí se miden aquí. Los históricos 04, 05 y 06 no: van en el lote 11.

## Estado por tabla
| # | Estado |
|---|---|
| 1 | **DEVUELTO** (analítica). D1 y D2 JUSTIFICADAS: la ventana MES01–MES12 está corrida un mes. D3, D4 y D5 DEVUELTAS. La Copy Delta→Postgres de Fabric tiene paridad exacta. La re-ejecución de hoy falló porque `Files/bronze/sap/pscd/DFKKKO` tiene una subcarpeta `DFKKKO/DFKKKO` desde el 30-09 |
| 9 | **DEVUELTO** (analítica). Está en v2 tras la re-ejecución de las 10:37: siguen 14.150 filas con distinto contacto, 6 llaves repetidas y `desc_clase_empresa` nula en los dos lados |
| 24, 25 | **DEVUELTO** (analítica). En la ventana del 18-08 al 27-08, Fabric tiene 10.000 radicados de más en envío; 3.160 de ellos Stratio los tiene en reenvío |
| 11, 12 | Medidas. La HDFS y la Postgres son idénticas dentro de cada lado. Diferencias: 745 filas de 695 `id` solo en Stratio, y edades +1 en 5.344 filas (cumpleaños del 30-09 al 07-10). **Falta registrar y presentar** |
| 14 | Medida y analizada, **sin registrar**. El 149.667.246.269 es una fila de ajuste (AJ, BP 99999999, periodo 2605). Las filas AJ suman 247.066 M en Stratio y 91.749 M en Fabric. Fuera de AJ, Fabric tiene +53.368 filas. 179 de 356 periodos son iguales |
| 35 | 8 diferencias PENDIENTE registradas por el cotejador: 11.206 filas con `documento_empresa='0'` (3.659 BP que Stratio sí tiene completos) y el corte de 2026 (+39,4 % de aportes en Fabric). **Presentar** |
| 21, 23 | Diferencias PENDIENTE registradas. #21: 21 filas de Stratio son del 05 y 06-10 (medido) y la fila 0012763665 es extra en Fabric. #23: 2.800 empleadores solo en Stratio y 47 solo en Fabric. **Presentar** |
| 31 | 10 diferencias PENDIENTE. Cuadre exacto: 2022 solo en Stratio (8.673.792), corte 2026-09 solo en Stratio (1.320.792) y corte 2026-08 (−152.011, con cuota 3/6). **Presentar** |
| 13 | El lado Fabric está descargado. Stratio se cortó en 3,2 GB de 3,68 GB (Rocket) |
| 10 | Re-ejecutada (10:12, PASA_CON_OMISIONES). El lado Fabric está descargado; **falta Stratio (Rocket)** |
| 2–6, 29, 30 | Re-ejecutadas (afiliados_02 a las 10:48, pacs_03 a las 11:07). **Faltan los dos lados por SFTP (VPN)** |
| 27, 28 | Re-ejecutadas. El lado Fabric está descargado; **falta Stratio** (#27 Postgres, #28 Rocket) |
| 7, 8, 15–20, 26, 32–34 | Bloque D, devueltas. No se miden |

## Siguiente paso al retomar
1. `pc mejora pendientes`, `fab auth status`, `pc stratio vpn` y `pc stratio cookie`. Las cookies vencían a las ~12:30 UTC y el token a las 13:53: pedir cookies nuevas.
2. Revisar con `ps` que el otro coordinador no esté descargando de HDFS de Stratio.
3. SFTP de los dos lados para las #2–#6, #29 y #30, con la fecha de escritura de cada archivo: `scripts/sftp_bajar.py <claves>`. Después, Postgres de Stratio de la #27 (`scripts/descargar_A.py ssf_pacs`, que repite también el lado Fabric).
4. Rocket, en serie: terminar la #13 (`scripts/descargar_B.py`, que salta lo ya bajado) y después las #28 y #10 con `bajar_hdfs_stratio`.
5. `pc medir` y `pc cotejar` por flujo. Cotejadores en paralelo para las tablas chicas y uno a la vez para las grandes (#13).
6. `pc etl evidencia --trabajo L10-1` para los 4 flujos re-ejecutados (CP-05). La decisión sobre los flujos del bloque A que no se re-ejecutaron sigue pendiente: (a) validar la corrida ya escrita o (b) re-ejecutar.
7. Presentar a QA, de a una: #35, #31, #11 y #12, #14, #21 y #23.
