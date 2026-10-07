# reportes_v4 · formato acordado e implementado (2026-10-05)

> **Formato 2 (2026-10-06, mejora M-005).** Las secciones del cotejo y del cotejo de flujo descritas más abajo son las
> del formato 1. Lo vigente está en `pc/reportes/formato2.py`:
> - **cotejo de tabla**: `encabezado` (estado, resumen exacto, cómo se leyó cada lado, versión anterior) ·
>   `controles.resumen` (una palabra por control, por familia VG / ID / CP; VG-09 dentro de VG) · `controles.detalle`
>   (qué midió cada lado, comparación y decisión) · `justificaciones` · `metricas`.
> - **cotejo de flujo**: `encabezado` · `ejecucion` (corrida validada, actividades, validador) · `analitica` o `ingesta`
>   (roles, entradas, salidas, flujos dependientes) · `orquestacion` · `comprobaciones` · `tablas` · `semaforo`.
> - Reglas nuevas: un control en alerta en los dos lados o con medición distinta exige una diferencia registrada; una
>   comprobación del flujo que no cumple deja el flujo EN_REVISION; con faltantes (`pc v4 incompletos`) no se publica.
> - La evidencia del flujo la mide `pc etl evidencia`; el plan de ejecución es `pc etl ejecutar`. Prompts: `docs/PROMPTS.md`.

Decisiones confirmadas por el usuario e implementadas en `pc/reportes/v4.py`. Probado en Fabric real
(trabajo `_prueba_v4`) y en una simulación local de Stratio (`_sim_formato`). Pendiente: Stratio real y el generador del acta.

## Reglas acordadas

1. **Unidad de trabajo = el flujo.** Se valida un flujo (o varios) cuando llega; el **lote se arma al final**,
   en las compuertas, juntando los flujos aprobados. Una sola persona reúne todo y activa el acta.
2. **Un ciclo = una versión.** Al correr un flujo, cada tabla pasa nivel 0 → 1 → 2 y **los tres niveles escriben
   el mismo JSON** (`vN`). Al salir del nivel 2 hay veredicto final.
   - **Corrección** (desarrollo cambia algo y se re-ejecuta) → **versión nueva `vN+1`, desde el nivel 0**.
   - **Justificación** de un control o diferencia → **misma versión**; sigue al siguiente nivel o a las compuertas.
3. **Nada estimado.** Ni conteos, ni distintos, ni diferencias: todo exacto. Se retiran del reporte las métricas
   «referenciales» aproximadas (HLL, percentiles aproximados, desviación) o se calculan exactas.
4. **Diferencias exactas y completas dentro del JSON**, sin enlaces externos: qué control, qué columna, qué filas y qué
   valor a cada lado, obtenidas comparando las dos tablas en local en el nivel 2 (sin llave declarada). Hasta **5 filas
   de ejemplo** por diferencia, más el conteo total exacto de filas afectadas. Los ejemplos sirven para mostrar el error
   o para justificarlo.
5. **Controles retirados** (no se calculan ni aparecen): VG-07, VG-08, ID-07, ID-08.
   **Nuevo: VG-09 · conformidad de contrato** — el contrato obtenido de Stratio debe ser tal cual en Fabric; si falla
   puede justificarse (p. ej. `varchar` ↔ `string`). Los informativos lo son según el grupo.
6. **Nombres del flujo** en Fabric y en Stratio en todos los archivos, solo informativos.
7. **Encabezado**: solo el nivel alcanzado (no la hora de cada nivel).
8. **Estados de aprobación**: APROBADO · APROBADO_CON_JUSTIFICACION · APROBADO_CON_VERIFICACION · DEVUELTO · EN_CURSO.
   Nada pasa al acta con una verificación pendiente.
9. **Expediente por flujo aprobado**: un `.md` con todos sus JSON, resultados y contexto; los expedientes de los
   aprobados son lo que recibe la persona que activa el acta final.
10. **El agente ETL** lanza la ejecución y escribe él mismo el JSON de cotejo de flujo, respetando el cuerpo que
    escribiría el notebook v10. El notebook v10 existe para mostrar una ejecución en vivo.
11. **El acta**: estructura de los lotes 6–10 (9 puntos, firmas, anexo con TODOS los enlaces —4 por tabla— sin uno
    roto ni mal dirigido) con la presentación de los lotes 2–3 (valor de cada lado lado a lado, comprobación paso a
    paso, cifras de cierre, gráficas).

## Archivos

| Archivo | Uno por | Escribe |
|---|---|---|
| `medicion_fabric_<clave>_v<N>.json` | tabla · ciclo | medidores (niveles 0, 1, 2) |
| `medicion_stratio_<clave>_v<N>.json` | tabla · ciclo | medidores (niveles 0, 1, 2) |
| `cotejo_<clave>_v<N>.json` | tabla · ciclo | cotejo rápido + cotejador + decisiones |
| `cotejo_flujo_<flujo>_v<N>.json` | flujo · ciclo | agente ETL |
| `log_agentes` (bitacora.jsonl) | trabajo | todos los agentes · **solo local** |
| `expediente_<flujo>_v<N>.md` | flujo aprobado | consolidador · **solo local** |
| `acta_<lote>_v<ver>.json` + `.docx` | lote | acta-final · **solo local** (`~/Projects/reportes/`) |

**Se publica únicamente**: las dos mediciones, los cotejos y el cotejo de flujo en OneLake `reportes_v4/`, y las dos
mediciones en el bucket `metricas-*/v4/qa/<clave>/`. Nada más sale del equipo local.

## Secciones de cada JSON

- **medicion**: `encabezado` (formato, versión, trabajo, flujo Fabric/Stratio, grupo, plataforma, objeto, fuente,
  nivel_alcanzado, medido_utc, reemplaza_a) · `estado_controles` (cada control: nivel, rol decide/informa/no_aplica,
  estado) · `nivel_0` · `nivel_1` · `nivel_2` (cada uno con sus métricas y sus `pruebas` por control) · `contrato`.
- **cotejo**: `encabezado` (+ verdad STRATIO, versiones y huellas de las dos mediciones, estado, resumen) ·
  `estado_controles` (resultado entre lados) · `nivel_0/1/2` (comparación por control) · `VG-09_contrato`
  (contrato de cada lado y rupturas) · `diferencias` (id, control, tipo, columna, descripción, filas_afectadas
  exactas, hasta 5 ejemplos, causa, causa_medida, decisión, historial de decisiones).
- **cotejo_flujo**: `encabezado` · `ejecucion` (corrida, actividades, validador, pruebas reclasificadas) ·
  `dependencias` · `roles` · `entradas` · `salidas` (filas, versión Delta, commits en la corrida, rol según el
  validador) · `analitica` (transformación con roles reales + lo que dijo el validador) · `tablas` · `semaforo` · `verificacion`.
- **log_agentes**: una línea por evento (evento, ts, usuario, agente, acción, fase, nivel, flujo, clave, estado, duración, detalle, salidas, error).
- **expediente**: .md del flujo listo para acta (ver `pc/reportes/v4.py → expediente`).
