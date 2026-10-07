# Prompts para iniciar y cerrar un trabajo · Pipeline QA v2

Dos prompts. El primero se llena con los flujos y arranca el trabajo; el segundo cierra diferencias y justificaciones
cuando ya está medido. Se pegan en una sesión abierta con `cd ~/Projects/pipeline-comfandi && claude`.

## Prompt 1 · Iniciar un trabajo

```text
Trabajo nuevo: <NOMBRE_TRABAJO>. Eres el coordinador (CLAUDE.md). No retomes ningún trabajo anterior.

## Qué quiero al final
Cada flujo de la lista con su cotejo de flujo y su cotejo por tabla en formato 2, completos y publicados, y cada
diferencia explicada con cifras de los dos lados y ejemplo. Prefiero un flujo honestamente «en revisión» a uno
aprobado con un dato sin medir. Para <LOTE / ACTA DESTINO>.

## Flujos a validar
Regístralos tal cual; no completes de memoria lo que falte: pregúntame.

| FL | Flujo en Fabric | Flujo en Stratio | Grupo | Tabla | Ruta Stratio | Ruta Fabric | Ventana de fechas |
|---|---|---|---|---|---|---|---|
| FL-0000 | <nombre_fabric> | <nombre_stratio> | ingesta / analitica / orquestador | <clave> | <hdfs:/… · pg:esquema.tabla · sftp:/…> | <silver.tabla · pgfab:esquema.tabla · Files/…> | <ninguna o columna y rango> |

Antes de medir, confirma cada ruta contra el código del flujo (`pc roles --flujo F`) y dime si alguna no coincide
con la que te di. Si no conozco un FL lo dejo vacío: no lo inventes.

## Plan de ejecución
Nada corre en paralelo: cada paso espera al anterior y el plan se detiene si uno falla. Elige el caso que aplique:

- Flujo a validar: <x> · Dependencias: no
- Flujo a validar: <x> · Dependencias: <a, b>  (corre a, luego b, sin validarlos; después ejecuta y valida x)
- Flujos a validar: <y, z, m> · Dependencias: sí, entre ellos  (ejecuta y valida y, luego z, luego m; cada uno se coteja aparte)
- Flujos a validar: <a, b> · Orquestador: <orq>  (corre el orquestador una vez y valida a y b sin re-ejecutarlos)

Antes de lanzar, muéstrame el plan en una lista ordenada y espera mi «sí». Si una dependencia ya corrió hoy y
terminó Completed, no la repitas: compruébalo en Fabric y dime qué corrida tomaste. Si al leer el código encuentras
una entrada que no está en mi lista de dependencias, dímelo antes de ejecutar: decido yo si se corre.
Es la primera vez que se usa `pc etl ejecutar` en Fabric: si algo no responde como esperas, para y cuéntame.

## Agentes
Usa los agentes de `.claude/agents/`, uno por paso, y pásale a cada uno el trabajo, el flujo y lo que debe devolver:
etl-validador (plan, veredicto y evidencia) → medidor-rapido-fabric y medidor-rapido-stratio en paralelo → semaforo →
gestor-descargas → medidor-completo → cotejador → publicador-reportes. Postgres de Fabric solo por postgres-fabric.
Los agentes no se llaman entre sí ni deciden por mí; lo que devuelvan lo compruebas tú antes de contármelo.

## Lo que no se negocia
- Se valida la corrida que escribió el dato que se mide. Si un flujo se re-ejecuta, el validador vuelve a correr sobre
  esa corrida y se abre versión nueva.
- Un control que cumple su regla pero queda en alerta en los dos lados, o con una medición distinta entre lados, no
  pasa en silencio: se registra como diferencia, con conteo exacto, ejemplo de los dos lados y explicación.
- Una comprobación del flujo que no cumple deja el flujo en revisión.
- `pc v4 incompletos` debe decir COMPLETO antes de publicar. Si falta un dato, dime cuál y por qué; no lo rellenes.
- Las decisiones (justificar, verificar, devolver) son mías. Solo se justifica con causa medida.

## Cómo trabajar
Arranca con lo de siempre (mejoras pendientes, `fab auth status`, VPN, cookies de Rocket) y pídeme lo que falte.
Prioriza ETL y lecturas de Stratio mientras haya VPN y cookie. Avísame antes de descargar (tablas, MB, tiempo); las
de más de 100 M de filas o 5 GB solo con mi confirmación. Avanza sin detenerte hasta el nivel 2 y el cotejo en todo
lo que no dependa de mí, y acumula las decisiones para el final.

## Qué me entregas
1. Por flujo: estado, corrida validada (hora y quién la lanzó), comprobaciones que no cumplen y por qué.
2. Por tabla: resumen exacto (100 % igual, o la diferencia con cifras) y las diferencias registradas.
3. Lo que no se pudo evaluar, dicho tal cual.
4. Los enlaces: 1 por flujo y 3 por tabla (cotejo, métrica Stratio, métrica Fabric), con FL y nombre del JSON.
```

## Prompt 2 · Cerrar diferencias y justificaciones

```text
Retoma el trabajo <NOMBRE_TRABAJO>. Ya está medido y cotejado; ahora cerramos las diferencias.

Corre `pc v4 incompletos` y `pc decision` y preséntame, tabla por tabla, cada punto abierto. Para cada uno necesito:
- qué control es y qué mide;
- la cifra exacta de Stratio y la de Fabric, y cuántas filas afecta;
- de 1 a 5 ejemplos con el valor de cada lado (datos personales enmascarados);
- la causa, y si está medida (con qué consulta la comprobaste) o es una hipótesis;
- qué propones: justificar, verificar con Comfandi, devolver a desarrollo, o analizar más.

Antes de presentármelos, usa el agente cotejador para registrar las que falten. Para las advertencias de llave
(ID-05) prueba la llave compuesta que tenga sentido y dame el resultado de los dos lados. Para duplicados y nulos,
dime si son las mismas filas en los dos lados o no.

No decidas por mí ni agrupes varias diferencias en una sola respuesta: las reviso una por una. Presenta los dos
lados con el mismo detalle. Un defecto de código no se justifica. Si una causa depende de negocio, va a verificar.

Con mis decisiones registradas: reconstruye, comprueba que `pc v4 incompletos` diga COMPLETO, publica y dame los
enlaces. Lo que quede en revisión o devuelto, dímelo con el mensaje corto para desarrollo o para Comfandi.

<Opcional, al final:> Con todo cerrado, genera el acta <N> con el agente acta-entrega: solo flujos aprobados o
aprobados con justificación, columna «Revalidación del lote», sección de pendientes y verificación de cada cifra
contra su JSON hasta dar 0 discrepancias. Local, sin publicar.
```

## Notas

- `pc etl ejecutar` (plan de ejecución) está programado pero no se ha probado contra un flujo real en Fabric
  (2026-10-06). Conviene estrenarlo con un trabajo de un solo flujo pequeño.
- El generador del acta todavía lee el formato anterior de los JSON; hay que adaptarlo al formato 2 antes de pedir un acta.
