# Alcance de la pipeline QA v2 · 2026-10-05

## Listo y probado con datos reales

| Pieza | Evidencia |
|---|---|
| Coordinador con preguntas por fase, expediente de decisión y retomar | `CLAUDE.md`, `pc decision`, `pc trabajo siguiente` |
| ETL Validator v10 (roles reales desde el código y el `_delta_log`, pruebas reclasificadas, analítica recalculada, cotejo de flujo) | `03-moves`: 6 roles invertidos corregidos; flujo real ejecutado en Fabric (ssf-tipo-identificacion) |
| Niveles 0 y 1 · Fabric sin descargar | 27,4 M filas en 34 s leyendo 8 MB |
| Niveles 0 y 1 · Postgres Stratio y Fabric en base | cuotas_pacs_anulados_ssf: 42.123 y 39.277 filas |
| Niveles 0 y 1 · HDFS y CSV de Stratio desde la descarga | Rocket **no** acepta lectura por rango (verificado) |
| Nivel 2 exacto en local, mismo motor a los dos lados | hash idéntico al publicado y al del notebook Spark (texto) |
| Paridad de ingesta entre plataformas | ssf_tipo_identificacion: CSV Latin-1 de Stratio ↔ parquet de Fabric con **SHA-256 idéntico** |
| Cotejo con análisis de las dos tablas y diferencias exactas | ape_repleg: 139 socios solo en Stratio (bloque sobre el máximo de Fabric) y 61 filas solo en Fabric |
| VG-09 contrato | cuotas_pacs: REFERENCIA obligatoria en Stratio, 11,34 % nulos en Fabric |
| Estados, verificación, ciclo vN+1 | simulación completa v1 → corrección → v2 APROBADO |
| Publicación v4 (solo mediciones, cotejos, cotejo de flujo) + bucket | HEAD OK en todo |
| Expediente → lote → 3 compuertas → acta .docx | acta generada y validada con el verificador de actas (sin fallos) |
| Cookies de Rocket (1 a 3), 8 hilos, avisos de vencimiento | `pc stratio cookie` |
| Registro de mejoras para compartir | `pc mejora …`, `docs/MEJORAS.md` |

## Se probará en marcha (no bloquea el uso)

Estas piezas están construidas y funcionan en las pruebas hechas; falta verlas con casos más grandes o distintos.
Cuando ocurran por primera vez, el coordinador lo anota en el log y, si hace falta un ajuste, se registra como mejora.

1. Tabla HDFS **grande y particionada**: velocidad real de Rocket con 8 hilos y el filtro de particiones por fecha.
2. **Rotación con 2 o 3 cookies** (construida; hoy se probó con una).
3. Postgres de Stratio con una **tabla grande**: bloques de columnas y tiempo máximo por consulta.
4. Calibración de **números, decimales y fechas** contra un hash del notebook de Spark (lo calibrado es texto).
5. Un **flujo de analítica ejecutado de punta a punta en la misma sesión** con el ETL v10.
6. Acta con **ingesta y analítica juntas** (firmantes de los dos grupos) y con diferencias justificadas reales.

## Fuera de alcance por ahora

- Programar corridas automáticas: el proceso lo activa una persona desde el chat.
- Reportes técnicos de fallas (siguen en el generador de actas anterior).
- Borrar `qa_validacion_lectura_postgres` (la usa `validacion_lote9`); queda hasta que el equipo lo decida.
