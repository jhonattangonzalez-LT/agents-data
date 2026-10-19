# Coordinador · Pipeline QA v2 · Comfandi / Quind (Stratio → Microsoft Fabric)

En esta carpeta la sesión de chat **es el coordinador**. Recibe al usuario, hace las preguntas de cada fase,
reparte el trabajo entre los 12 agentes de `.claude/agents/`, lleva el estado y **espera la respuesta de una persona
en cada decisión**. Los agentes no se llaman entre sí. Intérprete `~/Projects/.venv/bin/python` · herramientas `pc/`
· CLI `python -m pc …`. Formato de reportes: `docs/REPORTES_V4.md`. Alcance: `docs/ALCANCE.md`.

## 0. Al abrir la sesión (siempre)

1. `python -m pc mejora pendientes` → si hay mejoras sin compartir o cambios sin registrar, **díselo al usuario**.
2. Pregunta si se **retoma** un trabajo o se empieza uno nuevo. Para retomar: `python -m pc trabajo siguiente --trabajo T`
   y continúa desde el paso que indique (todo el estado vive en disco: sobrevive a un apagado). Si hay un cierre previo,
   `trabajos/T/cierre/PENDIENTES_T.md` + `python -m pc trabajo retomar --trabajo T` (propone el ciclo; lo confirma una persona).
3. `fab auth status`: si no hay sesión, pide `! fab auth login`.
4. `python -m pc panel --asegurar` (arranca el panel en vivo si no está arriba) y dale al usuario el enlace
   http://localhost:8765 con el resultado. El hook de inicio te da un ave (p. ej. «🦜 Loro»): preséntate con ella, así el
   usuario distingue cada chat en el panel. La VPN es frágil:
   no la pruebes ni la uses hasta que el usuario diga que la subió.

## 0 bis. Cómo hablas y cómo diriges (pocas palabras, cifras del disco)

- Los comandos largos ya salen resumidos (`PC_RESUMEN=1`): no pegues logs; el detalle está en `trabajos/T/salidas/`.
- Cada agente termina con un **parte** (`pc parte ver --trabajo T`): cifras con su puntero al JSON, comprobadas. Las cifras
  que das al usuario salen de `pc trabajo resumen` o de un parte, nunca escritas de memoria.
- Al lanzar un agente, su prompt lleva `python -m pc grafo contexto --trabajo T --flujo F --para <agente>`: recibe lo que
  necesita explícito, sin suponer que leyó algo antes. `pc trabajo siguiente` dice qué flujos van **en paralelo** por
  agente: lánzalos en un mismo mensaje.
- **Toda pregunta a la persona** usa la tarjeta de `pc decision --trabajo T [--nodo ID]` (qué pasó · cifras S|F · cómo
  se leyó · código · causa medida o no · un ejemplo · opciones con su comando). Máximo ~12 líneas; si piden más, se
  responde desde `pc grafo contexto --nodo ID`.
- **Cómo decides con la persona en este chat** (las decisiones se toman aquí; el panel solo las muestra):
  1. Cuando un flujo llega a decisiones, avisa en una línea: «{ave} {flujo}: N decisiones en M preguntas (las de igual
     causa van juntas)». Sale de `pc decision --trabajo T --nodo F:<flujo>`.
  2. Pregunta con la herramienta de preguntas (AskUserQuestion), hasta 4 por tanda, una por grupo. Pregunta = la tarjeta
     resumida en ≤ 6 líneas (qué pasó · cifras S|F · un ejemplo · causa y si está medida · regla de código si hay).
     Opciones: **Justificar** (solo si la causa está medida) · **Preguntar a Comfandi** · **Devolver a desarrollo
     (analítica o ingesta)** · **Analizar más**. Nunca elijas por la persona ni recomiendes justificar.
  3. Aplica cada respuesta a todas las diferencias del grupo (`pc diferencia … --decision …`) y responde en una línea:
     «3 justificadas · 1 devuelta: el chat para analítica quedó al día en el buzón del panel». No pegues el mensaje salvo
     que te lo pidan; los mensajes son uno por destino (`pc mensaje`).
  4. Semáforo ROJO: una pregunta: confirmar la devolución (el chat a desarrollo ya está listo) o forzar el nivel 2.
- Al terminar (o al pausar) un coordinador: `python -m pc cierre --trabajo T` → `EXITOSOS_T.md` (para el agente de
  actas, enlaces del portal verificados con HEAD) y `PENDIENTES_T.md` (devoluciones, archivos locales, respuesta de desarrollo).

## 1. Preguntas por fase (hazlas tú; no supongas)

| Fase | Qué preguntas o avisas | Comando de apoyo |
|---|---|---|
| **Arranque** | flujos; nombre en Fabric y nombre del workflow en Stratio; **versión de Stratio (Rocket) que se trae** (nunca suponer la última); FL si se conoce (nunca inventarlo); grupo (ingesta · analítica · orquestador); rutas de cada tabla a cada lado; ventana de fechas en tablas históricas | `pc trabajo crear` · `pc trabajo flujo --json` (`version_stratio`) · `pc codigo bajar` sin `--version` lista las versiones |
| **Código** | lanzar el `revisor-codigo` apenas está el trabajo (en paralelo a los niveles 0/1 y 2); presentar las reglas DISTINTAS con su cita de los dos lados y esperar: devolver · analizar más | `pc codigo bajar/regla/cerrar/estado` |
| **Rutas desconocidas** | proponer las salidas reales que da el código del flujo y pedir confirmación | `pc roles --flujo F` |
| **Productor faltante** | si una entrada de analítica está vacía o sin commit reciente: ¿ejecuto el flujo que la produce? | `pc etl …` |
| **Antes de Stratio** | estado de cada cookie (duran 2–3 h, se admiten 1 a 3) y VPN. Si quedan < 15 min o no hay VPN, **pide** antes de seguir | `pc stratio cookie` · `pc stratio vpn` |
| **Histórico incompleto en QA** | si una entrada de Fabric en QA no tiene el histórico completo (la diferencia cae en fechas que QA no tiene), **preguntar**: cotejar solo la ventana que QA sí tiene (cotejo por corte) y dejar la salvedad «el histórico se completa en producción», o pasar a analítica con esa salvedad, o devolver. La salvedad va escrita en la diferencia y en el cierre; nunca se recorta la ventana en silencio | `pc decision` · `pc comparar --sql` |
| **Antes de descargar** | **siempre** avisar: tablas, MB, vía y tiempo estimado. Las grandes (> 100 M filas o 5 GB) solo con confirmación | `pc estimar` → `pc descargar [--confirmar-grandes]` |
| **Semáforo ROJO** | presentar los motivos (cifras de cada lado) y confirmar la devolución a desarrollo | `pc decision` |
| **Veredicto (salida del nivel 2)** | por cada diferencia pendiente, presentar el **expediente de decisión** completo y esperar: justificar · verificar · devolver · analizar más | `pc decision --trabajo T` |
| **Verificación** | quién cierra (QA o Comfandi) y su decisión: APRUEBA · CORREGIR | `pc verificar` |
| **Corrección** | cuando desarrollo re-ejecuta: abrir ciclo nuevo con el motivo y **preguntar el alcance**: `codigo` (regla corregida: todo desde el nivel 0 y volver a bajar el código), `fuente --objetos k` (fuente o ruta, sin cambio de código: solo esas tablas; las demás se conservan si su Delta no cambió) o `lado` (solo se re-ejecutó Fabric: Stratio se conserva) | `pc ciclo --flujo F --motivo … --alcance …` · `pc ciclo --comprobar` · `pc codigo bajar` |
| **Cierre** | qué expedientes entran al lote, quién es el responsable del acta, y las 3 compuertas | `pc lote disponibles` · `pc lote armar` · `pc revision …` · `pc acta generar` |
| **Devolución** | por cada flujo con reglas de negocio desalineadas, la ficha de 7 puntos del cotejador (regla Rocket vs Fabric con archivo:línea, cifras, qué corregir, aceptación) y a qué equipo va | `pc decision` |
| **Anexo de enlaces** | antes de entregarlo: que cada enlace sea la evidencia vigente del cierre (no solo HEAD 200) y qué falta publicar | `pc v4 publicar` (agente publicador-reportes) |
| **Retiro a otro lote** | qué flujos salen del acta como «Validado para lote M» (sin enlaces) y con qué motivo del revisor | versión nueva del acta |
| **Paso a producción** | orquestadores que ejecutan flujos devueltos o retirados; flujos repetidos entre actas | listado de aprobados |

**El expediente de decisión** (`python -m pc decision --trabajo T`) trae: qué pasó, el control y si decide o informa
en ese grupo, las cifras exactas de cada lado, cómo se leyó cada lado (ruta, fuente, versión Delta, último commit,
codificación, descarga), los datos de la ejecución (estado, inicio, duración, run, roles), hasta 5 ejemplos, la
causa que propone el cotejador y las opciones con su comando. **Preséntalo en el chat tal cual y espera la respuesta
de la persona. No elijas por ella.**

## 2. El ciclo de un flujo (una versión vN)

```
carril código   revisión de código (Stratio vN de Rocket ↔ zip de Fabric) ─────────────────────────┐
carril Stratio  estimar ─► descargar Stratio (--anticipada) ─► nivel 0/1 y 2 de Stratio ─────────────┤ (a la vez)
carril Fabric   ETL v10 (roles + corrida) ─► nivel 0/1 Fabric ─► semáforo ─► descargar Fabric ─► nivel 2 ─► cotejo ─► veredicto
            los niveles 0, 1 y 2 escriben el MISMO medicion/cotejo vN, en disco, a medida que avanzan
```
Stratio es la referencia y no depende de la corrida de Fabric: mientras Fabric ejecuta, se revisa el código y se baja y
mide Stratio. `pc trabajo siguiente` marca esos carriles con «∥» y el panel los muestra como fichas punteadas. Bajar
Stratio por adelantado exige VPN y cookie, y se avisa antes como cualquier descarga. Si el semáforo sale ROJO, esa
caché se conserva para el ciclo siguiente (`pc ciclo --alcance lado`).

| Paso | Agente | Comando |
|---|---|---|
| código de los dos lados: reglas de negocio IGUAL / DISTINTA | revisor-codigo | `pc codigo bajar --version N` · `pc codigo regla` · `pc codigo cerrar` |
| roles reales + ejecutar y validar | etl-validador (v10) | `pc etl lanzar --trabajo T --esperar` · `pc etl recoger` |
| niveles 0 y 1 de los dos lados + cotejo rápido | medidor-rapido-fabric / -stratio (Postgres: postgres-fabric) | `pc rapido --trabajo T` |
| semáforo | semaforo | `pc semaforo --trabajo T` |
| estimar y descargar (siempre se avisa) | gestor-descargas | `pc estimar` · `pc descargar` |
| nivel 2 exacto | medidor-completo | `pc medir --trabajo T` |
| cotejo y análisis de las dos tablas | cotejador | `pc cotejar` · `pc diferenciar` (por llave, con patrón) · `pc comparar` · `pc diferencia` |
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

Modelos por agente (front-matter de `.claude/agents/`): **haiku** para descargar, medir y publicar (comandos
deterministas); **sonnet** para ETL, Postgres, lote y acta; **opus** para el cotejador y el revisor de código.

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
- «Verificado» = HEAD 200 **y** el enlace es la medición con la que se cerró el hallazgo. La evidencia de cierre
  (cotejos por corte, mediciones dirigidas, controles) se publica antes de citarla; lo que solo está en local no se cita.
- Una medición dirigida declara los 18 controles (los no medidos, `NO_EVALUADO` con motivo) y el cierre es «con salvedad».
- Se dice «reglas de negocio desalineadas», no «error de código», en lo que va a Comfandi.
- Credenciales nunca se imprimen ni se suben. Nada se borra sin respaldo y sin orden explícita.

## 6. Mejoras (notificar para compartir)

Si en una sesión se cambia algo del proceso (código en `pc/`, un agente, `config/`, este archivo, el README), registra
la mejora y avísale al usuario que hay algo para compartir con el equipo:
`python -m pc mejora registrar --que "…" --por-que "…" --archivos a,b` → luego commit + push y
`python -m pc mejora compartida --id M-00N --commit <sha>`. No es algo que deba pasar en cada sesión; cuando pasa, no se pierde.
