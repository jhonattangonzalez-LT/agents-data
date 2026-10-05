# Por qué existe la v2 · contexto entregado por el usuario (2026-10-03/04)

## Problemas del proceso anterior
- Cada tabla se medía completa de una vez (conteo, SHA-256 y perfil): los errores aparecían al final, tras horas.
- Tablas pesadas: 1–2 h hasta 500 MB, 3–4 h hasta 2 GB, hasta 8 h por encima. Stratio: PySpark con 2 hilos y 1 GB.
- Caídas de VPN o red obligaban a reiniciar mediciones largas.
- El ritmo de paso a QA subió en la 2.ª–3.ª semana y colapsó las validaciones extensas.
- Un solo agente activo para descargar y cotejar.
- Las diferencias por histórico se confirmaban tabla por tabla.
- Al alinear todo al agente del acta, algunas URL se corrompían.
- El ETL Validator invierte entradas/salidas en flujos encadenados (ver abajo).

## Qué cambia
- Primero errores rápidos: ETL Validator (10–20 min por flujo, en paralelo) y después conteo y esquema (nivel 0/1).
- Lo que falla vuelve a desarrollo de inmediato. Flujos llegan a QA desde el primer día (10–20 por día).
- Después, lo extenso: SHA-256 y perfil completo con tiempo presupuestado, en local y en paralelo.
- Delimitador de fechas definido al inicio.
- Entrega: un lote cada lunes desde el 12-oct, mínimo 40 flujos. Un hallazgo no detiene el lote.
- Cada tabla lleva 4 reportes: Métricas Stratio, Métricas Fabric, cotejo y ejecución del flujo.

## Novedad: entradas leídas como salidas por el nombre del parámetro
En los orquestadores el generador de código reusa el MISMO parámetro (y la misma variable de la Variable
Library) en el flujo que escribe la tabla y en el que la lee. El validador asigna el rol por la bandera
(`--xxx-output-path`, `--xxx-path`, `--xxx-output-table`) y los invierte: mide como salidas tablas que el
flujo solo lee (SALIDA_NO_ACTUALIZADA / «contenido idéntico») y no coteja las que sí escribe. Se arrastró
a las actas de los lotes 6, 7, 8 y 10. Detectado en orq_agrupadoras: origenes → destinos → moves → … → master_data.

Checklist (automatizado en `pc/inventario/roles.py`):
1. No decidir el rol por el nombre del parámetro.
2. Fuente de verdad: el zip del flujo (`extract.py` = entradas, `load.py` = salidas; `migrations/001_init_schema.py` suele crear solo salidas).
3. Recorrer el orquestador: lo que escribe un flujo anterior aquí es entrada. Señal: solo el que escribe tiene `--xxx-write-mode`.
4. Validar con `_delta_log`: toda salida tiene commit dentro de la corrida; si una «salida» no lo tiene y una «entrada» sí, están invertidos.
5. SALIDA_NO_ACTUALIZADA en TODAS las salidas de una corrida Completed = casi siempre roles invertidos.
6. En el acta: cada tabla de un flujo está en su `load.py` y tiene commit en la corrida citada.

## Proceso de medición anterior (resumen)
Accesos (VPN, cookie de Rocket, `.stratio_conn.json`, `fab`, SAS), descarga Stratio (Rocket con
`fuentes.hdfs_bajar`: un objeto a la vez, 32 hilos; Postgres por DuckDB o medida en base con `motor_pg`;
SFTP con paramiko y lectura RFC 4180), descarga Fabric (`_delta_log` + parquet vigentes; Postgres por
pipeline), medición con el motor v15 en DuckDB (mismo reporte de 17 secciones que los notebooks),
cotejo con criterio por grupo y justificaciones, publicación en OneLake y bucket con HEAD.
Herramientas originales: `~/Projects/validacion_lote9/`, `~/Projects/rocket_download.py`,
`~/Projects/comfandi/cea-analytics-comfandi/qa-etl-validador-agent-v2/actas/`.

Trampas: Rocket frágil y secuencial (OneLake acepta paralelismo); HLL no prueba duplicación; mín/máx de
texto no comparable entre Postgres y DuckDB; `information_schema` de Fabric trae NaN; `pkill -f` puede
matar el propio shell (matar por PID).
