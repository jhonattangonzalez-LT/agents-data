# Mejoras del proceso

Cada mejora se comparte con el equipo (commit + push al repositorio). `SIN_COMPARTIR` = falta hacerlo.

## M-016 · 2026-10-13 · SIN_COMPARTIR

**Qué:** Agente revisor-codigo y comando pc codigo: al comienzo del trabajo, en paralelo a los niveles 0/1 y 2, baja la version de Stratio que indica el usuario (Rocket: /assets, findAllVersions, findById) y el zip del flujo de Fabric, los deja en texto por nodo y por archivo, y registra cada regla de negocio como IGUAL, DISTINTA, SOLO_STRATIO o SOLO_FABRIC con la cita de los dos lados. La revision cerrada entra al semaforo (AMARILLO si esta sin cerrar o con una regla distinta), a pc decision (tipo CODIGO y reglas de la columna de cada diferencia) y a pc trabajo siguiente. El trabajo guarda version_stratio por flujo. Agentes alineados: cotejador (clasifica dato/error con la revision; redaccion precisa sin 'no medido' en una justificacion), semaforo, etl-validador, medidores y gestor de descargas (--trabajo T, trabajos/T).

**Por qué:** Una diferencia solo se puede clasificar como dato si la regla de negocio es la misma en los dos lados; hasta ahora la comparacion de codigo se hacia a mano y sin registrar la version de Stratio revisada, y en el lote 8 eso dejo justificaciones 'compatibles' sin cita. Con la version dada por el usuario y la regla citada nodo a nodo la clasificacion es precisa y trazable.

**Archivos:** `pc/codigo.py`, `pc/__main__.py`, `pc/lote.py`, `pc/compuerta/semaforo.py`, `pc/coordinacion.py`, `.claude/agents/revisor-codigo.md`, `.claude/agents/cotejador.md`, `.claude/agents/semaforo.md`, `.claude/agents/etl-validador.md`, `.claude/agents/medidor-rapido-fabric.md`, `.claude/agents/medidor-rapido-stratio.md`, `.claude/agents/gestor-descargas.md`, `CLAUDE.md`, `README.md` · por Jhonattan-LT

## M-015 · 2026-10-12 · SIN_COMPARTIR

**Qué:** Evidencia de ejecucion: si una entrada Delta la escribe una Copy de la misma corrida antes del paso de computo, la version leida es la ultima de esa Copy (antes quedaba 'sin version leida'); el cotejo de flujo muestra la actividad productora

**Por qué:** tableros_web_service_16 copia silver.subsidios_encuestados dentro de la corrida (src_encuestados) y el cotejo de flujo no se podia publicar

**Archivos:** `pc/etl/evidencia.py`, `pc/reportes/formato2.py` · por Jhonattan-LT

## M-014 · 2026-10-11 · SIN_COMPARTIR

**Qué:** pc roles encuentra el codigo de un flujo cuyo zip esta en una subcarpeta de version (<grupo>/<capa>/<flujo>/vN/<flujo>.zip): el candidato se busca tambien por el nombre del zip, y la capa y el grupo se leen saltando la carpeta vN

**Por qué:** tabla_base_reporte_aportes_v6 salia SIN_CODIGO; sin roles del codigo, el cotejo de flujo tomaba como entrada la Postgres public.detalle_aportes (que es la salida de su Copy) y bloqueaba la publicacion de L8.2 por una entrada sin medir

**Archivos:** `pc/inventario/roles.py` · por Jhonattan-LT

## M-013 · 2026-10-08 · SIN_COMPARTIR

**Qué:** Registro Delta: un commit sin commitInfo o sin fecha (tablas cargadas con otra herramienta) toma la fecha de los archivos que escribio (modificationTime de sus add) o, si no escribio ninguno, la del json del commit; se marca utc_origen

**Por qué:** L10-1: las entradas silver.sat_respuesta_* y silver.subsidios_encuestados (cargas manuales) salian 'sin version leida' en el cotejo de flujo y se habian leido como 'sin escrituras', lo que llevo a reportar tablas vacias que si tenian datos

**Archivos:** `pc/rapido/delta_remoto.py` · por Jhonattan-LT

## M-012 · 2026-10-08 · SIN_COMPARTIR

**Qué:** Nivel 0/1 de Stratio calculado desde la descarga: una Postgres de Stratio extraida a parquet se etiqueta POSTGRES_EXTRAIDA_A_PARQUET (antes HDFS_PARQUET)

**Por qué:** L8.2 Tabla_cosechas se coteja contra credito.cosechas (Postgres) y el reporte decia que se leyo de HDFS

**Archivos:** `pc/__main__.py` · por Jhonattan-LT

## M-011 · 2026-10-08 · SIN_COMPARTIR

**Qué:** Cotejo de flujo: (1) en ingestas por Copy cuyo origen externo (BD, AS400) no declara el validador, las entradas se toman de las actividades Copy medidas en la corrida (las Inactive quedan fuera del alcance y se listan); (2) una entrada del validador cuyo parametro no figura entre las entradas del codigo del flujo (pc roles) y no existe en el lakehouse se descarta y se anota en roles.entradas_del_validador_descartadas_por_el_codigo

**Por qué:** L8.2: sts-full y feco salian INCOMPLETO por 'entradas' vacias y core_validaciones_pac_03 / ssf_afiliados_02 por una tabla Postgres de salida que el validador ponia como entrada; roles por el codigo, no por el nombre

**Archivos:** `pc/reportes/formato2.py` · por Jhonattan-LT

## M-010 · 2026-10-08 · SIN_COMPARTIR

**Qué:** Nivel 0/1 de Postgres de Fabric en tablas grandes: agregados troceados por rangos de ctid (TID Range Scan) y combinados de forma exacta (sumas; min/max recombinados en la base con el tipo declarado)

**Por qué:** La Copy de qa_v2_postgres pierde el socket (~35-48 s sin devolver filas) en agregados de barrido completo; mercadeo.ventas (19 GB, 2,35 M paginas) fallaba con errorCode 2200 Npgsql 'Exception while reading from stream'

**Archivos:** `pc/pgfabric/sql.py`, `pc/rapido/postgres.py`, `config/pipeline.json` · por Jhonattan-LT

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

