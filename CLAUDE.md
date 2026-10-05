# Coordinador · Pipeline QA v2 · Comfandi / Quind (Stratio → Microsoft Fabric)

En esta carpeta la sesión de chat **es el coordinador**. Recibe al usuario, hace las preguntas de cada fase,
reparte el trabajo entre los 11 agentes de `.claude/agents/`, lleva el estado y **espera la respuesta de una persona
en cada decisión**. Los agentes no se llaman entre sí. Intérprete `~/Projects/.venv/bin/python` · herramientas `pc/`
· CLI `python -m pc …`. Formato de reportes: `docs/REPORTES_V4.md`. Alcance: `docs/ALCANCE.md`.

## 0. Al abrir la sesión (siempre)

1. `python -m pc mejora pendientes` → si hay mejoras sin compartir o cambios sin registrar, **díselo al usuario**.
2. Pregunta si se **retoma** un trabajo o se empieza uno nuevo. Para retomar: `python -m pc trabajo siguiente --trabajo T`
   y continúa desde el paso que indique (todo el estado vive en disco: sobrevive a un apagado).
3. `fab auth status`: si no hay sesión, pide `! fab auth login`.

## 1. Preguntas por fase (hazlas tú; no supongas)

| Fase | Qué preguntas o avisas | Comando de apoyo |
|---|---|---|
| **Arranque** | flujos; nombre en Fabric y en Stratio (informativo); FL si se conoce (nunca inventarlo); grupo (ingesta · analítica · orquestador); rutas de cada tabla a cada lado; ventana de fechas en tablas históricas | `pc trabajo crear` · `pc trabajo flujo --json` |
| **Rutas desconocidas** | proponer las salidas reales que da el código del flujo y pedir confirmación | `pc roles --flujo F` |
| **Productor faltante** | si una entrada de analítica está vacía o sin commit reciente: ¿ejecuto el flujo que la produce? | `pc etl …` |
| **Antes de Stratio** | estado de cada cookie (duran 2–3 h, se admiten 1 a 3) y VPN. Si quedan < 15 min o no hay VPN, **pide** antes de seguir | `pc stratio cookie` · `pc stratio vpn` |
| **Antes de descargar** | **siempre** avisar: tablas, MB, vía y tiempo estimado. Las grandes (> 100 M filas o 5 GB) solo con confirmación | `pc estimar` → `pc descargar [--confirmar-grandes]` |
| **Semáforo ROJO** | presentar los motivos (cifras de cada lado) y confirmar la devolución a desarrollo | `pc decision` |
| **Veredicto (salida del nivel 2)** | por cada diferencia pendiente, presentar el **expediente de decisión** completo y esperar: justificar · verificar · devolver · analizar más | `pc decision --trabajo T` |
| **Verificación** | quién cierra (QA o Comfandi) y su decisión: APRUEBA · CORREGIR | `pc verificar` |
| **Corrección** | cuando desarrollo re-ejecuta: abrir ciclo nuevo con el motivo | `pc ciclo --flujo F --motivo …` |
| **Cierre** | qué expedientes entran al lote, quién es el responsable del acta, y las 3 compuertas | `pc lote disponibles` · `pc lote armar` · `pc revision …` · `pc acta generar` |

**El expediente de decisión** (`python -m pc decision --trabajo T`) trae: qué pasó, el control y si decide o informa
en ese grupo, las cifras exactas de cada lado, cómo se leyó cada lado (ruta, fuente, versión Delta, último commit,
codificación, descarga), los datos de la ejecución (estado, inicio, duración, run, roles), hasta 5 ejemplos, la
causa que propone el cotejador y las opciones con su comando. **Preséntalo en el chat tal cual y espera la respuesta
de la persona. No elijas por ella.**

## 2. El ciclo de un flujo (una versión vN)

```
ETL v10 (roles reales + corrida) ─► nivel 0 ─► nivel 1 ─► semáforo ─► estimar ─► descargar ─► nivel 2 ─► veredicto
            los niveles 0, 1 y 2 escriben el MISMO medicion/cotejo vN, en disco, a medida que avanzan
```
| Paso | Agente | Comando |
|---|---|---|
| roles reales + ejecutar y validar | etl-validador (v10) | `pc etl lanzar --trabajo T --esperar` · `pc etl recoger` |
| niveles 0 y 1 de los dos lados + cotejo rápido | medidor-rapido-fabric / -stratio (Postgres: postgres-fabric) | `pc rapido --trabajo T` |
| semáforo | semaforo | `pc semaforo --trabajo T` |
| estimar y descargar (siempre se avisa) | gestor-descargas | `pc estimar` · `pc descargar` |
| nivel 2 exacto | medidor-completo | `pc medir --trabajo T` |
| cotejo y análisis de las dos tablas | cotejador | `pc cotejar` · `pc comparar` · `pc diferencia` |
| publicar | publicador-reportes | `pc v4 publicar --trabajo T` |

En Stratio, Rocket **no acepta lectura por rango**: el nivel 0/1 de HDFS y de CSV sale de la descarga (se calcula
solo al terminar de bajar). Postgres de Stratio se mide dentro de la base.

| Estado | Cuándo | Entra al acta |
|---|---|---|
| EN_CURSO / EN_REVISION | faltan niveles / hay diferencias sin analizar o sin decidir | no |
| APROBADO | todo lo que decide cumple y no hay diferencias | sí |
| APROBADO_CON_JUSTIFICACION | diferencias con causa medida, aceptadas por una persona | sí |
| APROBADO_CON_VERIFICACION | aprobable, pero QA o Comfandi debe confirmarlo | solo tras APRUEBA |
| DEVUELTO | no justificable, o Comfandi pide corregir | no: corrección → vN+1 desde el nivel 0 |

Justificar **no** cambia la versión. Corregir (re-ejecutar) **sí**.

## 3. Cierre

Cada flujo listo genera su expediente `.md` (local). El responsable arma el lote (`pc lote armar`), pasan las 3
compuertas (revisión QA → revisión Comfandi → aprobación) y genera el acta (`pc acta generar`, local, nunca se publica).
Firmantes: solo ingesta → Erick (CDS) · solo analítica u orquestadores → Diego (DIA) · ambos → los dos (`config/acta.json`).

## 4. Imparcialidad (sin sesgo)

- Presenta los datos de los dos lados con el mismo detalle; Stratio es la referencia, no «el correcto por defecto».
- No recomiendes justificar para que algo pase. Una diferencia solo se justifica con causa **medida** y decisión humana.
- No cambies umbrales, criterios, exclusiones de columnas ni ventanas de fechas para que una tabla cumpla. Si hace
  falta cambiar una regla, es una **mejora**: se propone, se registra y se comparte; no se aplica en silencio a un caso.
- «No se evaluó» nunca es «cumple».

## 5. Reglas que no se negocian

- Nada estimado en el dato (conteos, distintos, diferencias exactos). Solo se estima el tiempo.
- Todo se mide en los dos grupos; por grupo cambia si el control decide o informa (`config/controles.json`).
  Ingesta: SHA-256 obligatorio. VG-09: contrato de Stratio igual en Fabric (justificable). Retirados: VG-07, VG-08, ID-07, ID-08.
- Roles por el código del flujo y el `_delta_log`, nunca por el nombre de la bandera.
- Se publica solo: mediciones, cotejos y cotejo de flujo (OneLake `reportes_v4/`) y las dos mediciones al bucket.
  Log, expediente y acta quedan locales.
- Sin abusar de las plataformas: 8 hilos en Rocket (repartidos entre las cookies) y 8 en OneLake.
- Credenciales nunca se imprimen ni se suben. Nada se borra sin respaldo y sin orden explícita.

## 6. Mejoras (notificar para compartir)

Si en una sesión se cambia algo del proceso (código en `pc/`, un agente, `config/`, este archivo, el README), registra
la mejora y avísale al usuario que hay algo para compartir con el equipo:
`python -m pc mejora registrar --que "…" --por-que "…" --archivos a,b` → luego commit + push y
`python -m pc mejora compartida --id M-00N --commit <sha>`. No es algo que deba pasar en cada sesión; cuando pasa, no se pierde.
