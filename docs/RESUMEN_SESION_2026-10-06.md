# Resumen de la sesión 2026-10-06 · para retomar

Trabajos: `L11-complemento` (7 flujos), `L12` (15 flujos), diagnósticos `L11-insumos` y `L12-insumos` (no entregables).
Informes: `trabajos/L11-complemento/INFORME_LOTE11.md`, `trabajos/L12/INFORME_LOTE12.md` (se regeneran con
`trabajos/_sesion_2026-10-06/armar_todo.py`; el de L11 aún describe el ciclo v1 en varias secciones: **actualizar con el v2**).
Links del lote 11 (unificado, 158 enlaces): `~/Projects/reportes/Links_Lote11_2026-10-06.md`.
Scripts y evidencias de la sesión (el scratchpad de /tmp se pierde al reiniciar): `trabajos/_sesion_2026-10-06/`.

## Lote 11 · estado (ciclo v2: cadena re-ejecutada por `orq_agrupadoras` 2026-10-06 11:10–12:31 UTC)
| FL | Flujo | Estado | Falta |
|---|---|---|---|
| FL-0464 | origenes | APROBADO (IDÉNTICO, SHA-256 igual) | expediente |
| FL-0466 | moves | APROBADO_CON_JUSTIFICACION (corte ingesta SAP; decisión QA) | reconstruir v4 + publicar + expediente |
| FL-0469 | tasas | APROBADO_CON_JUSTIFICACION (corte SAP + desfase Stratio 0060019894; decisión QA) | ídem |
| FL-0470 | sabana_pila | EN_REVISION | decisión QA: justificar corte SAP / fecha de corrida / heredado de tasas; 42 empresas de vacaciones (lado Stratio): justificar o verificar |
| FL-0465 | destinos | EN_REVISION | agru justificado; norm: 247 filas (D3) dependen del bronze SAP → esperar ingesta o justificar |
| FL-0155 / FL-0156 | DET_APO / TAB_CTRL | EN_REVISION | desarrollo: Copy con `escapeChar = \` rechaza registros antiguos (ya enviado mensaje); re-ejecutar y re-validar (v2) |

Pendiente técnico: `python -m pc v4 construir --trabajo L11-complemento` y `v4 publicar` (con red) para que los cotejos
reflejen las decisiones registradas (el último `pc diferencia` se cortó en la reconstrucción por la VPN caída; las
decisiones SÍ quedaron en `v4/diferencias.json`, respaldo `.bak_2026-10-06`).
Ojo: `pc ciclo` borra la caché de los dos lados; el lado Stratio v1 está respaldado en
`trabajos/L11-complemento/_respaldo_stratio_v1/` (se restauró para el v2).

## Lote 12 · estado
- Propuesta aprobar: FL-0632 (justificar `Fecha_carga`), FL-0590 y FL-0329 (por ejecución). **Falta decisión QA.**
- FL-0442 aforo: solo corte → justificar o re-ejecutar. FL-0385, FL-0409: re-ejecutar con entradas al día o devolver.
- Devolver (defecto de código/insumo): FL-0401 y FL-0403 (`total_aportes` no existe, DEBT-2), FL-0407, FL-0416, FL-0490,
  FL-0521 (sus tablas SÍ existen; defectos de columnas/formatos), FL-0472 (sin objeto en QA). **Falta confirmación QA.**
- Fotos FL-0703 / FL-0707: cobertura de periodos JUSTIFICADA (decisión QA). Diferencia dentro de la foto 202509 PENDIENTE:
  Fabric calculó la foto con el bronze VBAP incompleto (recargado 05-10). QA decidió NO re-ejecutar por ahora.

## Mejoras sin compartir (falta commit + push)
M-002 descarga HDFS por partición exacta · M-003 spill de DuckDB por conexión · M-004 limpieza de parquet viejos en la
caché Fabric. Propuestas no aplicadas: el validador debe respetar el orden del orquestador; medir de a un objeto las
tablas > 100 M filas; `pc ciclo` no debería borrar la caché de Stratio; `pc diferencia --id` no debería pisar `control`.

## Otros hallazgos
- `orq_agrupadoras` terminó Failed en `calculo_trab_ben_cuota_monetaria` (posterior a los flujos del lote 11).
- `/data/prod/trusted/agrupadoras/vacaciones_empresas` está vacía en Stratio.
- Cookies de Rocket: las del 06-10 vencen ~15:15 UTC; para nuevas descargas pedir otras.

## CIERRE DEL LOTE 11 (2026-10-06 ~20:25 UTC) · reemplaza la tabla de estado de arriba
Los 7 flujos quedaron en estado final, ciclo v2, reportes v4 publicados (37 archivos, HEAD OK, mediciones también en el bucket)
y verificados con `trabajos/_sesion_2026-10-06/verificar_l11.py` (0 problemas).
- FL-0464 origenes: APROBADO (idéntico).
- FL-0465 destinos, FL-0466 moves, FL-0469 tasas, FL-0470 sabana_pila: APROBADO_CON_JUSTIFICACION (decisiones QA del 06-10).
- FL-0155 DET_APO y FL-0156 TAB_CTRL: APROBADO_CON_JUSTIFICACION. Desarrollo cambió `escapeChar` a `"`; las dos ingestas corrieron
  Completed. Hallazgo clave: el archivo del SFTP trae periodos distintos según el día y los dos lados cargan por partición
  `PERIODO_PAGO`; las diferencias son de archivos de días distintos (y 30 filas de comillas en TAB_CTRL, Fabric des-escapa).
- Empresa 0060019894 (tasas/sabana_pila): desfase del catálogo en Stratio, probable readmisión; consulta enviada a analítica.
Enlaces: `~/Projects/reportes/Links_Lote11_2026-10-06.md` (23 flujos, 45 tablas, 158 enlaces; generador `links_final.py`).
Pendiente: acta .docx (el usuario confirma), expedientes/lote (`pc lote armar`), actualizar `INFORME_LOTE11.md` al v2,
commit + push de M-002/M-003/M-004 y de las mejoras propuestas (io_medido en ciclos manuales; `pc diferencia` no debe
reconstruir por red; publicación en paralelo).
