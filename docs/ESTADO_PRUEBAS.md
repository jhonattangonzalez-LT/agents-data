# Estado de las pruebas · 2026-10-04

Todo lo de Fabric se probó contra QA real. Lo de Stratio está construido y **sin probar** (requiere VPN y cookie).

| Pieza | Prueba | Resultado |
|---|---|---|
| Nivel 0/1 Fabric (Delta) | `silver.agrupadoras_ape_repleg` · 106.782 filas, 4 col | 6 s, 64 KB leídos; conteo de pies = `numRecords` del log |
| | `silver.afiliados_pacs` · 5,47 M filas, 68 col, 446 MB | 5,8 s, 66 KB leídos |
| | `gold.afiliados_ssf_pacs_historico` · 27,4 M filas, 122 archivos, 863 MB | 34 s, 8 MB leídos |
| Nivel 0/1 Postgres Fabric | `corporativo.cuotas_pacs_anulados_ssf` vía `qa_v2_postgres` | 39.277 filas (igual a lo conocido), 13 col, 2 consultas, 61 s |
| Pipeline `qa_v2_postgres` | creada en datalake-qa (`d663cc2a-…`) | OK |
| Limpieza de pipelines viejas | `qa_consulta_postgres` (último uso 26-09) y `qa_validacion_lectura_odbc` (nunca usada) | borradas, definiciones en `muestras/fabric_respaldo/` |
| | `qa_validacion_lectura_postgres` | **se conserva**: la usó `validacion_lote9/fabpg.py` el 02-10 |
| Roles reales | `03-moves` (orq_agrupadoras) | detecta los 6 roles invertidos; las 3 salidas reales tienen commit en la corrida del 30-09 y las 3 entradas no |
| ETL Validator v9 parametrizado | `qa_v2_etl_validator` + `23-landing-globales-ssf-tipo-identificacion` | notebook 2 min, flujo Completed en 42 s, veredicto PASA_CON_OMISIONES leído y resumido desde local |
| Nivel 2 local · calibración 1 | `ape_repleg` medido en local vs reporte publicado (mismo motor) | `hash_dataset` idéntico `350b2021…` |
| Nivel 2 local · calibración 2 | `CLASE_DOCUMENTO` en local vs notebook **Spark** de Fabric | `hash_dataset` idéntico `b5d6f639…` (solo columnas texto) |
| Cotejo rápido | tabla contra sí misma / con diferencia sembrada | CUMPLE / NO_CUMPLE CP-01 + ID-03 en ingesta; en analítica CP-01 informativo |
| Cotejo completo | `ape_repleg` contra sí mismo | APROBADO / IDENTICO |
| Semáforo | sin diferencias / con diferencia / sin lado Stratio | AMARILLO (roles corregidos) / ROJO / AMARILLO |
| Publicación | lote `_prueba_fabric` en `Files/resultados/pipeline_v2/_pruebas/` | 2 reportes, HEAD OK, 0 enlaces rotos |
| Compuertas | orden y bloqueo del acta | rechaza revisión Comfandi antes de QA; acta bloqueada hasta las 3 |
| Bucket (SAS) | listado de `metricas-stratio` | OK (lectura) |

## Pendiente de probar (mañana, con VPN y cookie)
1. `stratio_pg.vpn_ok()` y una consulta de agregados en la Postgres de Stratio.
2. `rapido.stratio.rocket_acepta_rango(<parquet pequeño>)`: decide si el nivel 1 de HDFS se hace sin descargar.
3. Descarga HDFS de una tabla chica + nivel 2 + cotejo completo contra Fabric (ciclo entero con los dos lados).
4. SFTP (parquet por rango; CSV por descarga).
5. Calibrar la canonicalización de números, decimales y timestamps contra un hash del notebook de Spark.

## Datos de prueba que quedan
- `lotes/_calibracion/`, `lotes/_prueba_fabric/`, `cache/_calibracion/`, `cache/_prueba_fabric/` (locales, se pueden borrar).
- OneLake: `Files/resultados/pipeline_v2/_pruebas/_prueba_fabric/` (2 JSON) y `Files/resultados/pipeline_v2/_pg/` (resultados de la pipeline).

# Stratio real · 2026-10-05 (VPN + cookie nueva), trabajo `_stratio_real`

| Pieza | Resultado |
|---|---|
| VPN y Postgres de Stratio | OK; la primera conexión tarda ~39 s |
| Cookie de Rocket | OK; JWT hasta las 17:27 UTC, estado y aviso con `pc stratio cookie` |
| Rocket: listar | OK, ~8,5 s por llamada |
| Rocket: Range | **NO lo acepta** (HTTP 200 con el archivo entero) → el nivel 0/1 de HDFS sale de la descarga |
| Rocket: descarga | ape_repleg, 5 parquet (1,7 MB) en 18 s con 8 hilos y 1 cookie |
| Postgres Stratio nivel 0/1 en base | cuotas_pacs_anulados_ssf: 42.123 filas, 13 col, 18 s |
| Postgres Stratio extracción (nivel 2) | OK, 2 min |
| SFTP | OK; el CSV viene en **Latin-1 y `;`**: el lector prueba UTF-8 y luego Latin-1 y deja anotada la codificación |
| Ingesta CSV → parquet | ssf_tipo_identificacion: 12 = 12 y **hash SHA-256 idéntico** entre Stratio y Fabric |
| Analítica HDFS → Delta | ape_repleg: 106.895 → 106.782; 139 socios solo en Stratio (bloque 0070062180–0070062318, todos sobre el máximo de Fabric) y 61 filas solo en Fabric (46 socios con otro representante) — registradas como D1 INFORMATIVA y D2 PENDIENTE |
| Postgres ↔ Postgres | cuotas_pacs: 42.123 → 39.277; **VG-09 no cumple**: REFERENCIA sin nulos en Stratio, 11,34 % en Fabric (sin analizar) |
| Publicación | 12 archivos, HEAD OK; las 6 mediciones también en el bucket `v4/_pruebas/` |
| Regla nueva | una tabla con diferencias medibles (filas, huella o contrato) queda EN_REVISION hasta que el cotejador las registre |
