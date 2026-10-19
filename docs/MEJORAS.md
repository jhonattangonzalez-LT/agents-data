# Mejoras del proceso

Cada mejora se comparte con el equipo (commit + push al repositorio). `SIN_COMPARTIR` = falta hacerlo.

## M-029 · 2026-10-19 · SIN_COMPARTIR

**Qué:** Historico incompleto en QA: el coordinador pregunta si cotejar solo la ventana comun (cotejo por corte) o pasar a analitica, con la salvedad escrita de que el historico se completa en produccion; nunca se recorta la ventana en silencio

**Por qué:** En QA puede faltar historico de las entradas de Fabric y eso no debe bloquear ni justificarse sin decision

**Archivos:** `CLAUDE.md`, `.claude/agents/cotejador.md` · por Jhonattan-LT

## M-028 · 2026-10-19 · COMPARTIDA

**Qué:** pc panel --asegurar (el coordinador arranca el panel al abrir y da el enlace); prompts de prueba del coordinador v3; firmantes del acta por equipo (CDS / DIA) en config/acta.json

**Por qué:** Que el panel siempre este corriendo con cada coordinador y dejar registrado el cambio de firmantes

**Archivos:** `pc/__main__.py`, `CLAUDE.md`, `docs/PROMPT_PRUEBA_COORDINADOR_V3.md`, `docs/PROMPT_PRUEBA_HOMOLOGACION_CORREOS.md`, `config/acta.json` · por Jhonattan-LT · compartida en 1fdc3e7

## M-027 · 2026-10-19 · COMPARTIDA

**Qué:** Mensajes: uno por destino (chat analitica DIA, chat ingesta CDS, correo Comfandi) sin nada del proceso QA, causas repetidas una sola vez; panel: clic en ficha la ilumina con sus carriles unidos por linea y abre su detalle debajo (sin comandos), re-pruebas con ↺vN y animacion de reinicio, rama iluminada al hacer clic en el grafo, trabajos de prueba (_*) fuera del panel; pc decision agrupa diferencias de igual causa; protocolo de decisiones en el chat con AskUserQuestion

**Por qué:** Mensajes que se copian tal cual al destinatario, menos preguntas repetidas y un panel que se entiende flujo por flujo

**Archivos:** `pc/mensajes.py`, `pc/panel/index.html`, `pc/panel/servidor.py`, `pc/coordinacion.py`, `pc/grafo.py`, `pc/__main__.py`, `CLAUDE.md` · por Jhonattan-LT · compartida en 1fdc3e7

## M-026 · 2026-10-19 · COMPARTIDA

**Qué:** Carriles paralelos por flujo: mientras Fabric ejecuta su ETL o se mide rapido, la revision de codigo y Stratio (descarga --anticipada y medicion) avanzan a la vez; pc trabajo siguiente los marca con ∥ y el panel como fichas punteadas. Pestaña Grafo en el panel: todo el grafo del trabajo por capas, filtrable por flujo, con destello en los nodos nuevos

**Por qué:** No esperar la corrida de Fabric para lo que no depende de ella, y ver como se llena el conocimiento del coordinador

**Archivos:** `pc/coordinacion.py`, `pc/__main__.py`, `pc/panel/index.html`, `pc/panel/servidor.py`, `CLAUDE.md`, `.claude/agents/gestor-descargas.md` · por Jhonattan-LT · compartida en 1fdc3e7

## M-025 · 2026-10-19 · COMPARTIDA

**Qué:** Mensajes listos para copiar (pc mensaje, automaticos tras semaforo, diferencia y cierre): a desarrollo en chat indicando ingesta (CDS) o analitica (DIA) con problema, cifras, ejemplo, regla de cada lado, que corregir y aceptacion; a Comfandi en correo cuando es regla de negocio (A_VERIFICAR) con la pregunta concreta y opciones. Panel arcade: ave por coordinador con filtro, equipo coordinador-agente-flujo con cables animados, recorrido por estaciones con fichas, vida de cookies, detalle por flujo (historia, respuestas, decisiones con ejemplo, mensajes) sin comandos, buzon de salida

**Por qué:** Que lo que se devuelve o se pregunta quede redactado y completo sin escribirlo en el chat, y que el panel se entienda de un vistazo con varios coordinadores abiertos

**Archivos:** `pc/mensajes.py`, `pc/panel/index.html`, `pc/panel/servidor.py`, `pc/hooks/evento.py`, `pc/coordinacion.py`, `pc/__main__.py`, `CLAUDE.md` · por Jhonattan-LT · compartida en 1fdc3e7

## M-024 · 2026-10-19 · COMPARTIDA

**Qué:** Modelo por agente (haiku: descargas, mediciones, publicacion, semaforo; sonnet: ETL, Postgres, lote, acta; opus: cotejador, revisor de codigo), seccion comun de reporte en los 12 agentes y reglas nuevas del coordinador en CLAUDE.md

**Por qué:** No usar el modelo mas caro para tareas deterministas y que todos los agentes reporten igual

**Archivos:** `.claude/agents/acta-final.md`, `.claude/agents/consolidador-revision.md`, `.claude/agents/cotejador.md`, `.claude/agents/etl-validador.md`, `.claude/agents/gestor-descargas.md`, `.claude/agents/medidor-completo.md`, `.claude/agents/medidor-rapido-fabric.md`, `.claude/agents/medidor-rapido-stratio.md`, `.claude/agents/postgres-fabric.md`, `.claude/agents/publicador-reportes.md`, `.claude/agents/revisor-codigo.md`, `.claude/agents/semaforo.md`, `CLAUDE.md` · por Jhonattan-LT · compartida en 1fdc3e7

## M-023 · 2026-10-19 · COMPARTIDA

**Qué:** Hooks de proyecto (.claude/settings.json + pc/hooks/evento.py) y panel en vivo (pc panel, localhost:8765) con coordinadores, agentes y modelo, etapas por flujo, progreso con ETA y vida de cookies; no toca la VPN

**Por qué:** Ver en casi tiempo real que hace cada coordinador y cada agente sin agregar demoras

**Archivos:** `.claude/settings.json`, `pc/hooks/evento.py`, `pc/panel/servidor.py`, `pc/panel/index.html`, `pc/hooks/`, `pc/panel/`, `pc/panel/__init__.py` · por Jhonattan-LT · compartida en 1fdc3e7

## M-022 · 2026-10-19 · COMPARTIDA

**Qué:** pc diferenciar: diferencias exactas por llave (declarada, una columna, compuesta o casi unica, comprobada), llave repetida aparte, patron por columna (nulos, espacios, mayusculas, acentos, mojibake, ceros, escala, max |S-F|, horario, columna corrida), por mes y ejemplos deterministas; pc cotejar compara 11 campos mas del perfil (informativos)

**Por qué:** Pasar de 'hash distinto' a la diferencia concreta y medida de cada columna, con precision

**Archivos:** `pc/cotejo/diferenciar.py`, `pc/cotejo/completo.py`, `pc/reportes/formato2.py`, `tests/test_diferenciar.py`, `.claude/agents/cotejador.md` · por Jhonattan-LT · compartida en 1fdc3e7

## M-021 · 2026-10-19 · COMPARTIDA

**Qué:** Grafo por coordinador (pc grafo construir|contexto|mermaid) y cierre en dos markdown cierre-v1 (EXITOSOS con enlaces del portal verificados con HEAD; PENDIENTES con ficha de 7 puntos, archivos locales y bloque de respuesta de desarrollo) + pc trabajo retomar

**Por qué:** Que cada coordinador entienda de donde se leyo, que se bajo y que se decidio, y que el agente de actas y un coordinador nuevo partan de un insumo estructurado

**Archivos:** `pc/grafo.py`, `pc/cierre.py` · por Jhonattan-LT · compartida en 1fdc3e7

## M-020 · 2026-10-19 · COMPARTIDA

**Qué:** Salidas cortas y cifras del disco: PC_RESUMEN (detalle en trabajos/T/salidas, avance con bytes/% en progreso/), partes de agente con cifras comprobadas contra el JSON (pc parte), pc trabajo resumen, siguiente con grupos en paralelo, ciclo con alcance codigo|fuente|lado y --comprobar; corrige pc decision, que no leia las diferencias del formato 2 (justificaciones) y ahora usa tarjetas de ~12 lineas

**Por qué:** Gastar menos tokens en texto de proceso, dar cifras exactas sin reescribirlas a mano, no rehacer todo cuando solo cambia una fuente, y que las diferencias pendientes lleguen a la persona

**Archivos:** `pc/salida.py`, `pc/parte.py`, `pc/__main__.py`, `pc/coordinacion.py`, `pc/reportes/v4.py`, `pc/acceso/rocket.py`, `pc/medir/completo.py` · por Jhonattan-LT · compartida en 1fdc3e7

## M-019 · 2026-10-14 · COMPARTIDA

**Qué:** revisor-codigo: llave revision_codigo en el cotejo de flujo. Guarda la versión de Stratio y el zip revisados, las reglas IGUAL y no IGUAL con la cita de los dos lados, el impacto, la decisión (ACEPTADA · DEVOLVER · PENDIENTE) y los comentarios de desarrollo y de QA, además de bloquea, aclaraciones_pendientes e historial. Nuevos comandos pc codigo comentar y pc codigo cotejo --publicar. Las aclaraciones posteriores se registran en la misma vN. El semáforo respeta las decisiones.

**Por qué:** La revisión de código no bloquea las fases siguientes y sus diferencias se aclaran después (Lote 12: R2–R17 aceptadas el 14-10). Hasta ahora esas aclaraciones quedaban solo en archivos .md locales y no en el cotejo de flujo publicado, que es la evidencia que se cita en el acta.

**Archivos:** `pc/codigo.py`, `pc/__main__.py`, `pc/reportes/v4.py`, `.claude/agents/revisor-codigo.md`, `docs/REPORTES_V4.md` · por Jhonattan-LT · compartida en 9c288c2

## M-018 · 2026-10-14 · COMPARTIDA

**Qué:** Agente acta-entrega: punto 7 compacto en reportes v4. Por diferencia van tres columnas: la cifra en una frase; el ejemplo con la clave y STRATIO/FABRIC en dos líneas de color; y la justificación corta que cierra el control (✔) con la decisión, quién y la fecha. La causa corta se escribe en actas/justif_corta_loteN.py y el detalle completo queda en el cotejo enlazado.

**Por qué:** El acta del Lote 12 (Ola 3) ocupaba unas 110 páginas porque copiaba la justificación completa de cada cotejo (rutas, commits, horas). Con el modo compacto, el punto 7 pasa de 196.000 a 82.000 caracteres y el acta queda en unas 60 páginas.

**Archivos:** `muestras/agente_acta-entrega_v1.md` · por Jhonattan-LT · compartida en 6a4a9f1

## M-017 · 2026-10-14 · COMPARTIDA

**Qué:** Flujo QA de los agentes: evidencia vigente publicada (verificado = HEAD + medición del cierre), medición dirigida con los 18 controles declarados y cierre con salvedad, anexo de enlaces por lote y ficha de devolución de 7 puntos, retiro de flujos a otro lote y chequeo previo a producción (orquestadores de flujos devueltos o retirados)

**Por qué:** Lotes 7–10 (13/14-10): se entregaron enlaces con HEAD OK que no eran la evidencia del cierre (L7: 196 enlaces a v2.1; L10 #15 DFKKOP); Comfandi observó 11 de 18 controles sin evaluar en DFKKOP; 2 orquestadores aprobados ejecutan flujos devueltos o retirados

**Archivos:** `.claude/agents/publicador-reportes.md`, `.claude/agents/medidor-completo.md`, `.claude/agents/cotejador.md`, `.claude/agents/acta-final.md`, `CLAUDE.md` · por Jhonattan-LT · compartida en 1fdc3e7

## M-016 · 2026-10-13 · COMPARTIDA

**Qué:** Agente revisor-codigo y comando pc codigo: al comienzo del trabajo, en paralelo a los niveles 0/1 y 2, baja la version de Stratio que indica el usuario (Rocket: /assets, findAllVersions, findById) y el zip del flujo de Fabric, los deja en texto por nodo y por archivo, y registra cada regla de negocio como IGUAL, DISTINTA, SOLO_STRATIO o SOLO_FABRIC con la cita de los dos lados. La revision cerrada entra al semaforo (AMARILLO si esta sin cerrar o con una regla distinta), a pc decision (tipo CODIGO y reglas de la columna de cada diferencia) y a pc trabajo siguiente. El trabajo guarda version_stratio por flujo. Agentes alineados: cotejador (clasifica dato/error con la revision; redaccion precisa sin 'no medido' en una justificacion), semaforo, etl-validador, medidores y gestor de descargas (--trabajo T, trabajos/T).

**Por qué:** Una diferencia solo se puede clasificar como dato si la regla de negocio es la misma en los dos lados; hasta ahora la comparacion de codigo se hacia a mano y sin registrar la version de Stratio revisada, y en el lote 8 eso dejo justificaciones 'compatibles' sin cita. Con la version dada por el usuario y la regla citada nodo a nodo la clasificacion es precisa y trazable.

**Archivos:** `pc/codigo.py`, `pc/__main__.py`, `pc/lote.py`, `pc/compuerta/semaforo.py`, `pc/coordinacion.py`, `.claude/agents/revisor-codigo.md`, `.claude/agents/cotejador.md`, `.claude/agents/semaforo.md`, `.claude/agents/etl-validador.md`, `.claude/agents/medidor-rapido-fabric.md`, `.claude/agents/medidor-rapido-stratio.md`, `.claude/agents/gestor-descargas.md`, `CLAUDE.md`, `README.md` · por Jhonattan-LT · compartida en b82699b

## M-015 · 2026-10-12 · COMPARTIDA

**Qué:** Evidencia de ejecucion: si una entrada Delta la escribe una Copy de la misma corrida antes del paso de computo, la version leida es la ultima de esa Copy (antes quedaba 'sin version leida'); el cotejo de flujo muestra la actividad productora

**Por qué:** tableros_web_service_16 copia silver.subsidios_encuestados dentro de la corrida (src_encuestados) y el cotejo de flujo no se podia publicar

**Archivos:** `pc/etl/evidencia.py`, `pc/reportes/formato2.py` · por Jhonattan-LT · compartida en b82699b

## M-014 · 2026-10-11 · COMPARTIDA

**Qué:** pc roles encuentra el codigo de un flujo cuyo zip esta en una subcarpeta de version (<grupo>/<capa>/<flujo>/vN/<flujo>.zip): el candidato se busca tambien por el nombre del zip, y la capa y el grupo se leen saltando la carpeta vN

**Por qué:** tabla_base_reporte_aportes_v6 salia SIN_CODIGO; sin roles del codigo, el cotejo de flujo tomaba como entrada la Postgres public.detalle_aportes (que es la salida de su Copy) y bloqueaba la publicacion de L8.2 por una entrada sin medir

**Archivos:** `pc/inventario/roles.py` · por Jhonattan-LT · compartida en b82699b

## M-013 · 2026-10-08 · COMPARTIDA

**Qué:** Registro Delta: un commit sin commitInfo o sin fecha (tablas cargadas con otra herramienta) toma la fecha de los archivos que escribio (modificationTime de sus add) o, si no escribio ninguno, la del json del commit; se marca utc_origen

**Por qué:** L10-1: las entradas silver.sat_respuesta_* y silver.subsidios_encuestados (cargas manuales) salian 'sin version leida' en el cotejo de flujo y se habian leido como 'sin escrituras', lo que llevo a reportar tablas vacias que si tenian datos

**Archivos:** `pc/rapido/delta_remoto.py` · por Jhonattan-LT · compartida en 92f467c

## M-012 · 2026-10-08 · COMPARTIDA

**Qué:** Nivel 0/1 de Stratio calculado desde la descarga: una Postgres de Stratio extraida a parquet se etiqueta POSTGRES_EXTRAIDA_A_PARQUET (antes HDFS_PARQUET)

**Por qué:** L8.2 Tabla_cosechas se coteja contra credito.cosechas (Postgres) y el reporte decia que se leyo de HDFS

**Archivos:** `pc/__main__.py` · por Jhonattan-LT · compartida en b82699b

## M-011 · 2026-10-08 · COMPARTIDA

**Qué:** Cotejo de flujo: (1) en ingestas por Copy cuyo origen externo (BD, AS400) no declara el validador, las entradas se toman de las actividades Copy medidas en la corrida (las Inactive quedan fuera del alcance y se listan); (2) una entrada del validador cuyo parametro no figura entre las entradas del codigo del flujo (pc roles) y no existe en el lakehouse se descarta y se anota en roles.entradas_del_validador_descartadas_por_el_codigo

**Por qué:** L8.2: sts-full y feco salian INCOMPLETO por 'entradas' vacias y core_validaciones_pac_03 / ssf_afiliados_02 por una tabla Postgres de salida que el validador ponia como entrada; roles por el codigo, no por el nombre

**Archivos:** `pc/reportes/formato2.py` · por Jhonattan-LT · compartida en b82699b

## M-010 · 2026-10-08 · COMPARTIDA

**Qué:** Nivel 0/1 de Postgres de Fabric en tablas grandes: agregados troceados por rangos de ctid (TID Range Scan) y combinados de forma exacta (sumas; min/max recombinados en la base con el tipo declarado)

**Por qué:** La Copy de qa_v2_postgres pierde el socket (~35-48 s sin devolver filas) en agregados de barrido completo; mercadeo.ventas (19 GB, 2,35 M paginas) fallaba con errorCode 2200 Npgsql 'Exception while reading from stream'

**Archivos:** `pc/pgfabric/sql.py`, `pc/rapido/postgres.py`, `config/pipeline.json` · por Jhonattan-LT · compartida en b82699b

## M-009 · 2026-10-07 · COMPARTIDA

**Qué:** CP-05 de las salidas SFTP con la fecha de modificacion del archivo dentro de la corrida validada; pc descargar baja tambien el SFTP del lado Fabric y guarda la fecha de cada archivo (archivos_sftp); el cotejo de flujo ya no cuenta una salida registrada del flujo como entrada (rol invertido del validador); el gestor de descargas respalda la descarga cara de Stratio antes de un ciclo nuevo

**Por qué:** Las salidas SFTP quedaban con CP-05 'no evaluado' aunque el dato estaba medido (L10-1: #2-#6, #29, #30), y SSF.PACS aparecia como entrada 'sin medir' del flujo pacs_03; un ciclo nuevo obligaba a volver a bajar por Rocket datos de Stratio que no cambiaron

**Archivos:** `pc/reportes/v4.py`, `pc/reportes/formato2.py`, `pc/medir/completo.py`, `pc/__main__.py`, `.claude/agents/gestor-descargas.md` · por Jhonattan-LT · compartida en 561e7d1

## M-008 · 2026-10-07 · COMPARTIDA

**Qué:** Cotejo de tabla: cada control lleva «medicion» con lo que midio cada lado completo (VG: columnas, tipos, longitudes; CP-02 esquema; CP-01/ID-01 conteo; CP-03 SHA-256 y huella por columna; CP-04 las 10 filas; CP-05 commit; ID-02 duplicados; ID-03/ID-04 nulos por columna; ID-05 distintos y candidatas; ID-06 distintos y constantes), como ya hacia VG-09 con los dos contratos. Semaforo: para un flujo validado sin ejecutar (orquestador) usa la corrida medida en la evidencia

**Por qué:** QA pidio el 2026-10-07 ver en cada control las mediciones obtenidas en Stratio y en Fabric, no solo la explicacion; el semaforo marcaba ROJO por corrida None en flujos del orquestador

**Archivos:** `pc/reportes/formato2.py`, `pc/__main__.py`, `.claude/agents/cotejador.md` · por Jhonattan-LT · compartida en 2228ca4

## M-007 · 2026-10-07 · COMPARTIDA

**Qué:** Cotejo de flujo: (1) un flujo que corre dentro de un orquestador se valida con la validacion estatica del validador posterior a la corrida mas la evidencia medida en Fabric; (2) la comprobacion «ninguna entrada cambio despues» incluye carpetas de Files; (3) ingestas por Copy: las entradas se documentan con las filas leidas/copiadas de cada actividad, las comprobaciones se acotan a las actividades que cargan las tablas del trabajo y una falla fuera del alcance deja el flujo en revision en vez de devuelto; (4) decisiones de una persona sobre comprobaciones del flujo (v4.decidir_comprobacion)

**Por qué:** El validador en modo sin ejecutar no cita la corrida (comprobado el 2026-10-07); los insumos bronze de agrupadoras cambiaron despues de la corrida validada sin que el reporte lo marcara; ingesta-novar tiene 30 Copy y falla en una fuera del alcance. QA autorizo aplicar el criterio necesario el 2026-10-07

**Archivos:** `pc/reportes/formato2.py`, `pc/reportes/v4.py` · por Jhonattan-LT · compartida en 2228ca4

## M-006 · 2026-10-07 · COMPARTIDA

**Qué:** Cache de resolucion DNS por proceso (pc/acceso/dns.py, activado en pc/__init__.py): cada nombre se resuelve una vez cada 10 min

**Por qué:** Con la VPN activa los DNS de la VPN no responden nombres publicos de Fabric/OneLake: 9-16 s por llamada HTTP y espera sin limite si la VPN cae (causa del cuelgue de pc etl evidencia del 2026-10-06, localizado en socket.getaddrinfo). Medido: listar OneLake pasa de ~9 s a ~0,5 s por llamada

**Archivos:** `pc/acceso/dns.py`, `pc/__init__.py` · por Jhonattan-LT · compartida en 2228ca4

## M-005 · 2026-10-07 · COMPARTIDA

**Qué:** Formato 2 de los reportes v4 (cotejo de tabla: encabezado, controles resumen/detalle, justificaciones, metricas; cotejo de flujo: ejecucion, analitica/ingesta, orquestacion, comprobaciones, semaforo), evidencia del flujo medida en Fabric (pc etl evidencia), compuerta de completitud (pc v4 incompletos; publicar se niega con faltantes), plan de ejecucion del ETL (pc etl ejecutar --validar --dependencias|--encadenados|--orquestador) e instrucciones de 7 agentes

**Por qué:** Los reportes decian CUMPLE sin mostrar que se midio en cada lado, un control podia cumplir con alerta en los dos lados sin registro, el cotejo de flujo citaba una corrida distinta de la que escribio el dato y no detallaba dependencias; QA pidio el formato y las reglas el 2026-10-06 (comprobacion fallida = EN_REVISION; toda diferencia registrada con ejemplo y explicacion)

**Archivos:** `pc/reportes/formato2.py`, `pc/reportes/v4.py`, `pc/etl/evidencia.py`, `pc/__main__.py`, `.claude/agents/etl-validador.md`, `.claude/agents/cotejador.md`, `.claude/agents/publicador-reportes.md`, `.claude/agents/semaforo.md`, `.claude/agents/medidor-completo.md`, `.claude/agents/medidor-rapido-fabric.md`, `.claude/agents/medidor-rapido-stratio.md` · por Jhonattan-LT · compartida en 53331f9

## M-004 · 2026-10-06 · COMPARTIDA

**Qué:** La descarga Delta de Fabric limpia de la cache los parquet de versiones anteriores

**Por qué:** Al re-descargar una tabla reescrita (tabla_agrupadoras v7->v8) quedaban los parquet viejos en la carpeta y el nivel 2 medio 724+731=1.455 filas en vez de 731.

**Archivos:** `pc/medir/completo.py` · por Jhonattan-LT · compartida en 53331f9

## M-003 · 2026-10-06 · COMPARTIDA

**Qué:** Carpeta de desborde de DuckDB por conexion (cache/.spill/<pid>_<hilo>)

**Por qué:** Con la medicion del nivel 2 y la mesa de analisis del cotejador corriendo a la vez, ambos DuckDB escribian los mismos duckdb_temp_storage_*.tmp y la medicion de tablas grandes fallaba con IO Error (moves, 124 M filas). Luego tambien fallo dentro de un mismo proceso: pc medir mide 2 objetos en hilos con conexiones distintas que compartian la carpeta por pid; se paso a pid+hilo.

**Archivos:** `pc/medir/completo.py` · por Jhonattan-LT · compartida en 53331f9

## M-002 · 2026-10-06 · COMPARTIDA

**Qué:** Descarga HDFS por particion Hive exacta (objeto stratio.particion, p. ej. periodo_foto=202509)

**Por qué:** Las tablas fotos de Fabric guardan UNA foto por corrida; en Stratio hay 48 particiones (~36 GB). Para cotejar la misma foto sin bajar todo, se baja solo esa particion y se conserva la carpeta Hive para que la columna de particion siga en el dato.

**Archivos:** `pc/acceso/rocket.py`, `pc/medir/completo.py`, `pc/__main__.py` · por Jhonattan-LT · compartida en 53331f9

## M-001 · 2026-10-05 · COMPARTIDA

**Qué:** Versión inicial de la pipeline QA v2: coordinador, 11 agentes, reportes_v4, ETL v10, Stratio probado, acta v4

**Por qué:** Cerrar el proceso para que el equipo lo pueda instalar y correr

**Archivos:** `README.md`, `CLAUDE.md` · por Jhonattan-LT · compartida en 240d3a5

