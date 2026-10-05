# Resumen de la sesión (03 al 05 de octubre de 2026) · para retomar

## Qué se construyó
- `~/Projects/pipeline-comfandi`: un coordinador (`CLAUDE.md`), 12 agentes (`.claude/agents/`) y las herramientas `pc` (`python -m pc …`).
- El proceso está en `CLAUDE.md` y el formato de los reportes en `docs/REPORTES_V4.md`. El estado de las pruebas de Fabric está en `docs/ESTADO_PRUEBAS.md`.
- Mapa del proceso (v1 como estaba, v2 con agentes): `docs/mapa/mapa_evidencia_qa.html`, publicado en https://claude.ai/artifact/Go94eTVr1VWk3yJgZLkbsr

## Decisiones tomadas
1. **La unidad es el flujo.** Se valida como un *trabajo* (`trabajos/<id>/`). El **lote** se arma al final con los expedientes aprobados, y lo arma una sola persona.
2. **Un ciclo es una versión vN.**
   - Los niveles 0, 1 y 2 escriben el mismo JSON.
   - Corregir (re-ejecutar) abre vN+1 desde el nivel 0.
   - Justificar mantiene vN.
3. **Estados:**
   - EN_CURSO o EN_REVISION mientras falta algo;
   - APROBADO;
   - APROBADO_CON_JUSTIFICACION (exige causa medida);
   - APROBADO_CON_VERIFICACION: lo cierra QA o Comfandi; si se pide corregir, pasa a DEVUELTO y se abre una versión nueva;
   - DEVUELTO.

   Nada pendiente de verificar pasa al acta.
4. **Nada estimado en el dato.** Solo se estima el **tiempo** del nivel 2. Las tablas de más de 100 M filas o 5 GB se miden después de preguntar.
5. **Controles:**
   - Retirados (no se calculan ni aparecen): VG-07, VG-08, ID-07 e ID-08.
   - Nuevo: **VG-09**, el contrato de Stratio debe ser igual en Fabric. Es justificable, por ejemplo varchar contra string.
   - Ingesta decide con VG, ID y CP, con SHA-256 obligatorio. Analítica mide todo y decide con VG, ID, CP-02, CP-05 y VG-09.
   - CP-04 es un muestreo informativo con `limit 10`.
6. **Diferencias.** Las encuentra el agente cotejador mirando las dos tablas (`pc comparar`). Son exactas, llevan hasta 5 ejemplos y van dentro del cotejo (`pc diferencia`).
7. **Semáforo.** ROJO solo para lo no justificable: corrida fallida, bloqueante real, salida sin commit en la corrida o tabla vacía. Lo demás da AMARILLO, pasa al nivel 2 y allí se decide.
8. **Roles de entrada y salida.** Salen del código del flujo y del `_delta_log`, nunca del nombre del parámetro: el validador los invierte en los orquestadores.
9. **Archivos en `reportes_v4`:** medición Fabric, medición Stratio, cotejo, cotejo de flujo, log de agentes y expediente. Las dos mediciones también van al bucket `v4/`.
10. **Cookies de Rocket.** Duran 2–3 h; se admiten 1 a 3 (`.rocket_cookie`, `_2`, `_3`) y el coordinador avisa siempre (`pc stratio cookie`).
    Sin abusar de las plataformas: 8 hilos en Rocket (repartidos entre las cookies) y 8 en OneLake.
11. **Acta.** Estructura de las actas 6–10 con la presentación de las 2–3. El anexo lleva todos los enlaces verificados.
12. **Firmantes del acta:**
    - solo ingesta → Erick (CDS);
    - solo analítica, incluidos los orquestadores → Diego (DIA);
    - ambos grupos → los dos.

## Probado
- Contra Fabric QA:
  - nivel 0/1 sin descargar: 27,4 M filas en 34 s;
  - pipeline `qa_v2_postgres`;
  - corrección de roles en `03-moves`;
  - notebook `qa_v2_etl_validator` lanzado con un flujo real;
  - nivel 2 calibrado: hash idéntico al publicado y al del notebook Spark;
  - publicación en `reportes_v4/_pruebas/`.
- Simulación local de Stratio (`trabajos/_sim_formato`): el ciclo completo v1 (con verificación de Comfandi) → corrección → v2 APROBADO → expediente → lote armado.

## Pendiente, en orden
1. **Probar Stratio real.** Hace falta VPN y una cookie nueva (la actual venció).
   - ¿Rocket acepta Range?
   - Postgres de Stratio en base;
   - descarga de HDFS y SFTP;
   - el ciclo completo con los dos lados.
2. **Generador del acta v4:** JSON del acta → .docx, con gráficas, la comparación lado a lado, firmantes según el grupo y el anexo con HEAD.
3. **Notebook ETL v10** para mostrar una ejecución en vivo. El agente ya lanza la ejecución y escribe el cotejo de flujo.
4. Calibrar números y fechas contra un hash de Spark (lo calibrado hasta ahora solo cubre texto).
5. Decidir si se borra `qa_validacion_lectura_postgres` (la usa `validacion_lote9/fabpg.py`).
6. Limpiar los datos de prueba:
   - local: `trabajos/_prueba_*`, `_sim_formato`, `_calibracion`, `lotes/_prueba_formato`;
   - OneLake: `reportes_v4/_pruebas/`, `pipeline_v2/_pruebas/` y `pipeline_v2/_pg/`;
   - bucket: `v4/_pruebas/`.

## Para retomar
Abrir Claude Code en `~/Projects/pipeline-comfandi` y pedir: «retomemos desde docs/RESUMEN_SESION_2026-10-05.md».
