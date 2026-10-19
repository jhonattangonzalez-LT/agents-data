Trabajo nuevo: **L<N>.<v>** — validación de los hallazgos del lote <N> (documento del revisor: `~/Projects/reportes/Hallazgos_Lote<N>.<v>.md`, ya guardado completo; fuente: <reporte / html / fecha>). Eres el coordinador (CLAUDE.md). Trabajos anteriores del mismo lote: `<trabajos/L…>` (<fecha, formato>): <retómalo | solo lectura, es antecedente>. No toques `<otros trabajos abiertos>`.

## Qué quiero al final
**Cada hallazgo # respondido con dato**: la «prueba a realizar» ejecutada y el «criterio para cerrar» evaluado tal como está escrito en el documento. Cada uno termina en uno de tres estados: cerrado con causa medida (qué filas, de qué periodo, por qué entrada o qué paso del código), corregido por desarrollo y re-medido (ciclo nuevo), o abierto diciendo qué falta y de quién depende. El criterio de cierre es el del revisor; no lo cambies ni lo relajes. Prefiero un flujo devuelto con evidencia a uno aprobado sin causa medida.

## Estado al escribir este prompt (<fecha y hora UTC>)
- VPN: <arriba | caída>. Cookies de Rocket: <cuántas, hora en que se pusieron, vencimiento> — compruébalas con `pc stratio cookie` y `pc stratio vpn`; avísame cuando queden menos de 15 min.
- Otras sesiones en paralelo: <ninguna | trabajo `L…`: comparten las cookies (8 hilos de Rocket en total) y la Postgres de Stratio (una sola cosa a la vez)>.
- Mejoras sin compartir: <M-0xx…> — pregúntame.

## Primer paso (antes de ejecutar nada)
1. Lee completo el documento de hallazgos, tal cual lo entregó el revisor.
2. Lee los antecedentes: <`~/Projects/reportes/Lote<N>…md`, `datos_acta_lote<N>.json`, `trabajos/_sesion_…/RETOMAR.md`, prompts anteriores del lote>, `.claude/agents/cotejador.md`, `pc/reportes/formato2.py`.
3. Si hay trabajo previo: `pc trabajo tablero --trabajo <T>` · `pc decision --trabajo <T>` · `pc v4 incompletos --trabajo <T>`.
4. Lo de siempre: `pc mejora pendientes`, `fab auth status`, VPN y cookies.
5. Hazme una tabla, hallazgo por hallazgo, con: **# · tabla · lo que pide el revisor · lo que ya está medido (cifra, fecha y archivo) · lo que falta · ¿desarrollo re-entregó? (última corrida en Fabric: estado, fecha, commit de la salida)**. Con esa tabla decido qué se re-ejecuta, qué se trae de otro trabajo y qué se publica. No ejecutes ni publiques nada sin mi «sí».

## Hallazgos a validar
Rutas: confírmalas con `pc roles --flujo F` y dime cuál no coincide. Postgres de Fabric solo por el agente postgres-fabric. FL: si no se conoce, déjalo vacío; no lo inventes.

| # | FL | Flujo en Fabric | Flujo en Stratio | Grupo | Tabla | Ruta Stratio | Ruta Fabric | Prueba a realizar (del documento) | Criterio para cerrar (del documento) | Antecedente — pista, verifícalo |
|---|---|---|---|---|---|---|---|---|---|---|
| <1> | <FL-0000> | <…> | <…> | <ingesta · analitica · orquestador> | <…> | <hdfs:/… · pg:esquema.tabla · sftp:/…> | <silver.… · pgfab:… · sftp:/…> | <…> | <…> | <cifras S / F, estado que quedó, fecha> |

Total: <n> hallazgos · <n> flujos · <n> tablas (<n> Delta/HDFS, <n> Postgres, <n> SFTP). Grandes (> 100 M filas o 5 GB): <lista>.

## Ya resueltos en otros trabajos (NO los vuelvas a ejecutar: tráelos con cifras y enlaces)
- <**FL-0000 `flujo`** (#n) — `trabajos/L…`, ciclo vN: cifras, estado, publicado sí/no>.
Comprueba en Fabric que no corrieron después de esa medición; si corrieron, dímelo. Si un mismo flujo tiene dos estados distintos en dos trabajos, muéstrame las dos mediciones lado a lado (corrida, fecha, salida medida) y decido yo cuál vale; no los concilies tú.

## Cómo se trata cada tipo de hallazgo
- **Diferencia de filas:** conteo exacto a cada lado, las filas sin pareja listadas (o contadas por periodo si son muchas) y la causa: corte, entrada atrasada, cruce, duplicados. «Corte» solo si se mide: fecha de escritura de cada lado y conteo dentro y fuera de la ventana.
- **Columna vacía o con más nulos:** nulos **y vacíos** de la columna a cada lado, y de la entrada que la alimenta (fecha y conteo de esa entrada). Si es un cruce roto, el paso del código que lo rompe.
- **Duplicados / llave:** ID-02 exacto en los dos lados, nunca `NO_EVALUABLE`; cuántas copias, en qué particiones o cargas.
- **Tipos / contrato (VG-09):** contrato de los dos lados columna por columna y, por cada cambio, medición de si hay pérdida de valor.
- **Periodo o histórico faltante:** mínimo y máximo de la fecha y **conteo por año o periodo en los dos lados**. La ventana común se coteja aparte y me presentas las dos cifras, con y sin ventana; no la apliques en silencio.
- **«No vino la evidencia» / motores distintos:** los dos lados con el mismo motor y parámetros (v15, SHA-256 completo y hash por columna), Fabric medido **después** de su última corrida.
- **Salida SFTP:** se mide el CSV final (conteo, SHA-256, separador, comillas, saltos de línea), no el parquet; la ruta productiva la confirmo yo.
- **Orquestadores:** definición del pipeline con sus actividades y la última corrida (estado, inicio, duración, hijos). No lances ninguno sin mi «sí».

## Plan de ejecución (muéstramelo ordenado y espera mi «sí»; nada en paralelo dentro de Fabric)
1. La tabla del primer paso y el estado en Fabric de cada flujo (¿re-entregado o no?).
2. Los que desarrollo ya corrigió: `pc ciclo --flujo F --motivo …` y vN+1 desde el nivel 0, uno por uno. Antes de abrir cada ciclo dime qué caché se pierde y cuánto cuesta volver a bajarla.
3. Los que no se han tocado: re-ejecutar solo refresca el corte; mide la causa sobre lo que hay y propón devolver.
4. Stratio primero mientras haya VPN; las descargas grandes solo con mi confirmación.
5. Reservas de tablas ya aprobadas, al final.
Si una entrada está vacía o vieja, dímelo antes de ejecutar: decido yo si se corre su productor.

## Lecciones (aplícalas)
- Procesos largos con `setsid`/`nohup` y log; matar solo por PID. La VPN se cae con tráfico sostenido contra la Postgres de Stratio: una sola cosa a la vez contra esa base, extracciones por trozos reanudables, tablas grandes no se miden dentro de la base.
- 19 GB de RAM: tablas de más de 50 M de filas se miden de a un objeto; a los cotejadores, DuckDB ≤ 4 GB.
- Avísame siempre antes de descargar: tablas, MB, vía y tiempo.
- Un cotejador por tabla o por flujo, con el # del hallazgo, su «prueba a realizar» y su «criterio para cerrar» copiados del documento; comprueba tú lo que devuelva antes de registrarlo. Que no dejen datos personales en el scratchpad.

## Lo que no se negocia
- Se valida la corrida que escribió el dato que se mide; registra la fecha de escritura de cada lado. Re-ejecución = versión nueva.
- Un antecedente es una pista, no un resultado: si una cifra ya no se reproduce, dilo.
- Toda diferencia se registra con conteo exacto, ejemplo y causa. «No se evaluó» no es «cumple».
- Las decisiones (justificar, verificar, devolver) son mías, una por una, con el expediente (`pc decision`). Un defecto del código del flujo no se justifica.
- `pc v4 incompletos` en COMPLETO antes de publicar. Los devueltos no se publican sin mi «sí».

## Qué me entregas
1. La tabla «pide · ya medido · falta · re-entregado» de todos los hallazgos.
2. Por flujo: estado, corrida validada (hora y run), comprobaciones que no cumplen y por qué. Por tabla: resumen exacto y diferencias registradas con ejemplo.
3. `~/Projects/reportes/Lote<N>.<v>_<fecha>.md` (documento vivo): un bloque por hallazgo # con «prueba a realizar» → resultado en cifras, «criterio para cerrar» → se cumple / no se cumple / no se pudo evaluar (por qué), y los enlaces (1 por flujo y 3 por tabla: cotejo, métrica Stratio, métrica Fabric). Arriba, el resumen: cerrados, devueltos, abiertos y qué falta de cada uno.
4. El expediente de decisión (`pc decision --trabajo L<N>.<v>`) para que yo decida una por una.
5. El acta <N>.<v> (.docx) solo cuando yo cierre las decisiones.
