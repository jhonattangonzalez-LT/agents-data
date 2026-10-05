# Contexto · lo verificado de los pilotos, y lo que falta para correr analítica

> Documento de traspaso, autocontenido. Continúa `CONTEXTO_POSTGRES_FABRIC.md` y **lo corrige
> en dos puntos**. Todo lo que aquí se afirma como «medido» se midió; lo que no, lo dice.
>
> **Estado: no se ha editado ningún notebook.** Los `.ipynb` de `metricas/` están como estaban.

---

## 1. Cómo se verificó

El piloto de reconocimiento nunca se había ejecutado, y el piloto genérico solo se había probado
contra un simulador de la API de Fabric — que reproduce la forma de las respuestas pero **no
ejecuta SQL**. Por eso se montó un banco distinto:

- **Postgres 16 real**, embebido (`pgserver`), con base `analitica` y rol `analitica_rw`, para
  que `current_database()` y `current_user` sean los que el notebook espera.
- **Simulador de la API de Fabric** con las tres trampas puestas a propósito: 202 con el id en
  `Location` y un `x-ms-operation-id` **señuelo**; `queryactivityruns` que devuelve **200 con
  lista vacía** si falta la ventana de fechas; y un Lookup que **corta a 5000 filas**.
- El SQL que llega por la API se ejecuta de verdad contra ese Postgres, con `set role
  analitica_rw`, como haría el gateway.
- Escenario con señuelos: la tabla buena (`feco.tpos_client`), otra con **las mismas 5
  columnas** (`landing.cli_tpos_20260801`), otra de nombre parecido
  (`sgdatos.tpos_cliente_hist`), 120 tablas de ruido y una tabla con tipos raros
  (`uuid`, `jsonb`, `text[]`).

Para rehacerlo: `uv pip install --target ./libs pgserver psycopg2-binary`, levantar
`pgserver.get_server(dir)`, y apuntar el `API` de la celda 2 del notebook al simulador tras
ejecutarla. No hace falta Docker ni un Postgres instalado.

---

## 2. `piloto_tpos_client_v1.ipynb` · corre entero

Las 4 corridas, de la celda 1 a la 10, sin intervención. El radar encontró la tabla buena entre
los señuelos y desempató bien — por número de vías, no por nombre:

```
MUY PROBABLE  feco.tpos_client            5/5 · vías: columnas, esquema, nombre
MUY PROBABLE  landing.cli_tpos_20260801   5/5 · vías: columnas, esquema
posible       sgdatos.tpos_cliente_hist   0/5 · vías: esquema, nombre
```

Comprobado además, una por una: coge el id de `Location` y **no** el señuelo; siempre manda la
ventana de fechas; un SQL inválido levanta excepción en vez de pasar por bueno; a 5000 filas
exactas avisa de truncado; `firstRowOnly: true` se detecta; una corrida sin Lookup protesta.

**Un acierto que no estaba escrito:** el `order by via` del radar deja las filas `A_columnas`
primero, así que aunque el Lookup corte, la respuesta sobrevive al corte. No tocarlo.

### Defectos acotados (no bloquean esta corrida)

| | |
|---|---|
| **`sql_metricas()` rompe con 9 tipos** | `uuid`, `json`, `jsonb`, `bytea`, arrays, `interval`, `inet`, `bit`, `xml`. Todos caen en el `else: texto` y reciben `min()` o `length()`, que no existen para ellos. Como es **una sola agregación para todas las columnas**, una columna así revienta la consulta entera y se pierde la corrida. Con `TPOS_CLIENT` (varchar + numeric) no muerde; como base de un mecanismo genérico, sí. El arreglo es clasificar por lista blanca, no por `else`. |
| **Booleano: falta `falsos`** | Stratio calcula verdaderos **y** falsos. (El min/max que no salen tampoco los calcula Spark para booleanos, eso está bien.) |
| Cabeceras mal numeradas | Hay dos «CELDA 5» y dos «CELDA 7». La tabla de la sección 5 de `CONTEXTO_POSTGRES_FABRIC.md` va desfasada una posición porque no cuenta la celda de `a_dataframe`/`mostrar`. |
| `AYUDA` remite a otro notebook | Menciona `huella()` y `sql_huella()`, que viven en `piloto_postgres_fabric_v1.ipynb`. |

### Permisos (la pregunta 2 del documento anterior)

Medido: **sin `USAGE` sobre el esquema, `information_schema` devuelve 0 tablas y ningún error.**
El radar diría «ningún candidato» — y ya avisa de que los permisos son la causa nº 1. Pero queda
dicho: que no salga nada nunca prueba que la tabla no exista.

---

## 3. `piloto_postgres_fabric_v1.ipynb` · fallo de bloqueo

```python
_SENTINELA = "chr(0) || 'NULL' || chr(0)"
```

**Postgres no admite el carácter NUL en texto.** `chr(0)` da `null character not permitted`, y
como es inmutable se pliega en tiempo de planificación: **falla siempre, en toda tabla, haya
nulos o no**. El simulador nunca ejecutó SQL, por eso no lo cogió. `huella()` no ha funcionado
nunca contra un Postgres real.

Con un centinela válido (`chr(2)`) el mecanismo es sólido. Medido:

- independiente del orden de las filas (copia desordenada da huella idéntica);
- detecta **un solo carácter** cambiado en 50 000 filas;
- detecta una fila de menos;
- 25,9 s sobre 2 444 179 filas.

**La consecuencia de fondo:** el `SENTINELA_NULO` de los notebooks de métricas —el que lleva NUL
por delante y por detrás— es **inalcanzable desde SQL**. La paridad Spark-contra-SQL del hash no
está «acotada y documentada»: es imposible mientras la especificación use ese carácter. SQL
contra SQL sí, con tal de que los dos lados usen el mismo reemplazo.

---

## 4. Corrección a la tabla de «qué se puede medir»

`CONTEXTO_POSTGRES_FABRIC.md` §3 subestima lo que cabe en SQL. **Las 15 métricas que da por
imposibles funcionan todas en Postgres**, probadas una a una:

| Lo que el documento anterior daba por «no» | Realidad |
|---|---|
| Las 7 forenses de texto (regex) | operador `~` de Postgres, las 7 |
| Percentiles | `percentile_cont(array[...]) within group (order by ...)` |
| Desviación estándar | `stddev_samp` |
| Top-N de valores frecuentes | `group by ... order by ... limit` — 3 filas, 0,01 s |
| `solo_espacios`, `con_espacios_en_bordes`, `centinelas_de_nulo`, `mayusculas_completas` | `btrim` / `upper` |
| `ceros`, `negativos` | `count(*) filter (where ...)` |

Coste de las 11 de texto y forenses juntas sobre 2,44 M de filas: **5,6 s**.

Lo único que de verdad no cruza es el `hash_dataset` de Spark — y no necesita cruzar si los dos
lados miden en SQL, que es el caso: Postgres de Stratio contra Postgres de Fabric.

---

## 5. Los números para la decisión de arquitectura (pregunta 3)

| Medido sobre 2 444 179 filas | |
|---|---|
| Celda 9 tal cual, 5 columnas | 16,7 s |
| ...la misma sin `count(distinct)` | 1,9 s |
| Huella (SHA-256 por fila + 4 sumas) | 25,9 s |
| 40 columnas de texto (extrapolado desde 300 k) | ~59 s |
| `count(*)` solo | 0,1 s |

**Todo por debajo del minuto que tarda la pipeline en arrancar. El cuello de botella es la
pipeline, no Postgres** — añadir métricas es casi gratis, lo que cuesta es cada corrida.
`count(distinct)` se lleva el 90 % del tiempo de la celda 9.

Con 3 corridas por tabla, unos 3 min por tabla. La pipeline de Copy al lakehouse solo se
justifica si el inventario es grande o si se quiere el hash de Spark de verdad.

---

## 6. Dos trampas de paridad que no estaban documentadas

1. **Distintos aproximados.** Stratio usa `approx_count_distinct` (HyperLogLog, RSD 1 %) cuando
   la tabla pasa de `MAX_COLUMNAS_DISTINTO_EXACTO = 12` columnas o de
   `DISTINTOS_EXACTOS_HASTA = 10_000_000` filas. El `count(distinct)` de SQL es siempre exacto.
   Para `TPOS_CLIENT` (5 columnas, 2,44 M) los dos son exactos y coinciden; en una tabla ancha o
   grande, `distintos` diferiría hasta un 1 % y **parecería una diferencia del dato**.
2. En los notebooks de métricas, `_ESPEC_HASH` dice `SHA256-CANON-v2` y `_hash_desde_sumas`
   calcula `SHA256-CANON-v1`. Es la cadena de especificación que va al reporte.

---

## 7. Lo que viene ahora: correr analítica con los dos `v6`

Lo de Postgres queda aparcado hasta después. El siguiente paso es ejecutar
`auditoria_metricas_STRATIO_v6.ipynb` y `auditoria_metricas_FABRIC_v6.ipynb` sobre los flujos de
**analítica**, que hasta ahora solo se han corrido sobre ingesta.

> **`v6` es la versión hecha para esto.** En analítica no se busca paridad: se busca
> integridad. Con `EJECUTAR_CP = False` (o `EXIGIR_PARIDAD = False`) el cotejo deja de tratar
> las diferencias de volumen y de contenido como fallos —las informa— y sigue exigiendo
> esquema, contrato, reglas ID/VG, encoding y precisión de medición. El detalle está en
> `CONTEXTO_NOTEBOOKS_METRICAS.md` §6.

### De dónde salen las rutas

- Inventario: `comfandi/cea-analytics-comfandi/qa-etl-validador-agent-v2/inventario/flows-qa.txt`
  — **40 flujos de analítica en QA** (`comercial/gold`, `contactabilidad/silver`, `core/gold`,
  `core/silver`).
- **Lado Stratio:** la ruta original de Rocket quedó de-hardcodeada como literal en el
  `params.py` de cada flujo (`# NEW var (replaces hardcoded '/data/prod/trusted/...')`) y el
  `contract.yaml` dice cuál es la variable de salida (`physicalName: params.<x>_output_path`).
  Extraíble limpiamente en **~11 de los 40**; en el resto el `params.py` no deja el literal y hay
  que mirar el `job_definition.json` o el flujo en sí.
- **Lado Fabric:** las rutas **no son literales** — se resuelven contra la **Variable Library**
  por ambiente. `validador_analitica_qa.ipynb` (en la raíz de `Projects/`) ya hace justo esa
  resolución; de ahí hay que sacarlas, no del repo de flujos.
- Las salidas de analítica aterrizan en `lh_transversal`, que es el lakehouse ya configurado en
  la celda 1 de los dos notebooks.

### El emparejamiento sí funciona (probado)

`clave_de_cotejo()` de `v5` empareja correctamente los pares reales de analítica, y **no** cruza
objetos homónimos de proyectos distintos:

| Stratio | Fabric | clave | ¿par? |
|---|---|---|---|
| `.../trusted/sap/crm/contactabilidad/TIPO_DOCUMENTO` | `/Files/silver/sap/crm/contactabilidad/TIPO_DOCUMENTO` | `sap_crm_contactabilidad_tipo_documento` | sí |
| `.../trusted/sap/crm/contactabilidad/ADR2/registrosValidos/` | `Tables/sap_crm_contactabilidad_adr2` | `sap_crm_contactabilidad_adr2` | sí |
| `.../trusted/globales/contactabilidad/contactabilidad_comercial/registrosValidos` | `/Files/silver/globales/contactabilidad/contactabilidad_comercial` | `globales_contactabilidad_contactabilidad_comercial` | sí |
| `.../trusted/comercial/contactabilidad/account` | `/Files/silver/salesforce/contactabilidad/account` | distintas | **no** (correcto) |

### Pero hay dos trampas nuevas, propias de analítica

**a) La zona en medio de la ruta no se quita.** `clave_de_cotejo()` quita los segmentos de zona
solo del **principio**. En ingesta eso basta porque `landingraw` y `bronze` siempre van delante.
En analítica la capa (`silver`, `gold`) aparece en posiciones distintas en cada lado:

```
STRATIO  /data/prod/refined/core/gold/validaciones/...  ->  core_gold_validaciones_...
FABRIC   /Files/gold/core/validaciones/...              ->  core_validaciones_...
                                                            NO EMPAREJAN
```

**Resuelto en `v6`:** `ZONA_EN_CUALQUIER_POSICION = True` (CELDA 1.CONFIG) quita la zona esté
donde esté y las dos claves coinciden. Viene **apagado**, porque si una carpeta real se llama
como una zona (`gold`, `qa`, `data`…) también se la llevaría. Mismo valor en las dos
plataformas. Sigue siendo buena idea pasar las dos listas por `clave_de_cotejo()` antes de
correr: es gratis.

**b) La desambiguación es local a cada lado.** Cuando un flujo publica `registrosValidos` y
`registrosRechazados`, las dos rutas colapsan a la clave del padre y `_desambiguar_claves()` las
separa añadiendo la carpeta — bien, y además lo avisa. **Pero solo desambigua dentro del lado que
tiene la colisión.** Probado:

```
CASO A (simétrico)   Stratio: validos + rechazados    Fabric: validos + rechazados
                     -> los dos lados quedan ..._registrosvalidos / ..._registrosrechazados
                     -> emparejan los dos

CASO B (asimétrico)  Stratio: validos + rechazados    Fabric: una sola tabla
                     -> Stratio queda ..._registrosvalidos / ..._registrosrechazados
                        Fabric queda  ..._account
                     -> NO EMPAREJA NINGUNO. Tres huérfanos.
```

Regla para declarar `FUENTES` de analítica: **lo que se declare en un lado hay que declararlo en
el otro con la misma granularidad.** Si Fabric solo tiene la tabla de válidos, en Stratio hay que
declarar solo `registrosValidos`, no el par.

### Orden sugerido

1. Elegir el lote de analítica (empezar por `contactabilidad/silver`, que es el mejor mapeado).
2. Sacar las rutas de Fabric resolviendo la Variable Library con `validador_analitica_qa.ipynb`.
3. Sacar las de Stratio del `params.py` / `contract.yaml` de cada flujo.
4. **Antes de correr**, pasar las dos listas por `clave_de_cotejo()` y comprobar que emparejan —
   es gratis y evita una corrida entera perdida. Las trampas (a) y (b) salen ahí. Si es la (a),
   `ZONA_EN_CUALQUIER_POSICION = True` en los dos notebooks.
5. En la CELDA 1.CONFIG de **los dos** notebooks: `EJECUTAR_CP = False` (que con
   `EXIGIR_PARIDAD = "AUTO"` ya pide integridad y ahorra la pasada cara del checksum). Si se
   quiere el checksum pero sin que la diferencia falle: `EJECUTAR_CP = True` y
   `EXIGIR_PARIDAD = False`.
6. Declarar `FUENTES` en las celdas 3 de los dos notebooks, correr, cotejar.
7. Leer el cotejo por el **VEREDICTO DE INTEGRIDAD**, no por el del dato: el del dato dirá
   `SIN PARIDAD` (no se midió) o `DIFERENTE` (se midió y difiere), y en analítica ninguno de
   los dos es un fallo por sí solo.

---

## 8. El primer cotejo real de analítica: `ADR2` (2026-09-16)

Medido sobre los parquet de las dos plataformas, no sobre los reportes.

| | STRATIO | FABRIC |
|---|---|---|
| ruta | `.../trusted/sap/crm/contactabilidad/ADR2/registrosValidos` | `Tables/silver/sap_crm_contactabilidad_adr2` |
| filas | 3.578.723 | 3.576.473 |
| esquema | 6 columnas | **idéntico**, misma firma |
| `Fecha_carga` | `2026-09-15` en todas las filas | `2026-09-16` en todas las filas |
| `max(ADDRNUMBER)` | `0011033663` | `0011027991` |
| nulos | 0 en las 6 columnas | 0 en las 6 columnas |

**Veredicto de integridad, leído de los dos reportes JSON** (`974da98e` ↔ `3f1c65ca`):

| | |
|---|---|
| firma del esquema | **idéntica** byte a byte, 6 columnas, mismos tipos y mismo orden |
| `hash_esquema_tipos` | **idéntico** · `c3feaaf5…` |
| contrato propuesto | **COMPATIBLE** · 100 % de columnas intactas |
| nulos | 0 en las 6 columnas, en los dos lados |
| encoding | sin bytes ilegibles |
| medición | misma precisión en los dos lados |
| `VG-01..VG-06` (esquema) | **OK** en los dos lados |
| `ID-01..ID-06` | **el mismo estado en los dos lados**, regla por regla |
| únicas reglas que difieren | `ID-07`, `ID-08`, `VG-08` — las tres comparan cada lado contra **su propia** corrida previa. Stratio-QA lo hacía contra `STRATIO_PROD @ 2026-09-02` (delta −124.804): no dice nada de la migración |

**La integridad de esta tabla no está fallando.** Lo único que difiere es el volumen y el
contenido del dato, que es paridad, no integridad.

**Qué dice el dato, comparando los dos parquet columna a columna (duckdb, multiconjunto):**

- con `Fecha_carga`: **0** filas idénticas de 3,5 M;
- sin `Fecha_carga`: **3.574.043 de 3.578.723 = 99,869227 %**;
- 4.680 filas solo en Stratio, 2.430 solo en Fabric (neto −2.250); de las de Stratio, 1.237
  tienen `ADDRNUMBER` por encima del máximo de Fabric: son registros que llegaron después.

**Por qué:** son dos cosechas distintas de la misma fuente, no un defecto de la migración.

1. `Fecha_carga` es un **sello de carga**: cambia en cada corrida y hace que todas las filas
   difieran por construcción. No hay que excluirla del hash —eso sería dejar de atestiguar una
   columna real—: hay que **leer el cotejo por el veredicto de integridad**, que es para lo que
   está. `v6` lo detecta y lo dice solo.
2. El `_delta_log` de la tabla de Fabric tiene **10 versiones** y el contenido de negocio es
   **byte a byte el mismo desde la v0 del 2026-09-11**: mismo conteo, mismos min/max, y el
   `EXCEPT ALL` de las 5 columnas de negocio entre v0 y v9 da **0 filas** en los dos sentidos.
   Lo único que cambia entre versiones es `Fecha_carga`. Es decir: **el flujo se reejecuta pero
   su fuente no se ha refrescado desde el 11-09**, mientras que Stratio leyó la zona `trusted`
   viva a día 15-09.

Las versiones, con su sello: v0 `2026-09-11 20:58Z` → `Fecha_carga = 2026-09-11`; v1..v7
`2026-09-14` (seis reejecuciones ese día); v8 `2026-09-16 15:08Z` y v9 `2026-09-16 20:32Z` →
`Fecha_carga = 2026-09-16`. Siempre 3.576.473 filas, siempre `CREATE OR REPLACE TABLE AS SELECT`.

**Qué hacer antes del siguiente cotejo de este objeto:**

1. Correr en modo **INTEGRIDAD** (`EXIGIR_PARIDAD = False`): la diferencia de cosecha y el
   sello de carga se informan en vez de fallar, y el esquema y el contrato se siguen exigiendo.
2. Refrescar la fuente del flujo de Fabric: lleva congelada desde el 11-09.
3. Medir los dos lados **el mismo día**; si no, la diferencia de vintage se lleva el veredicto.
4. Nada de tocar `COLUMNAS_EXCLUIDAS_HASH`: se queda en `[]`.

---

## 9. Qué queda pendiente de Postgres, para cuando se retome

1. Cambiar `_SENTINELA` en `piloto_postgres_fabric_v1.ipynb` — `chr(0)` no existe en Postgres.
2. Decidir el centinela común, porque el de Spark no es replicable en SQL.
3. Ampliar `sql_metricas()` a las 15 métricas que sí caben en SQL, y a los 9 tipos que hoy
   revientan la consulta.
4. Fijar `distintos` exacto en los dos lados, o no compararlo.
5. Ejecutar `piloto_tpos_client_v1.ipynb` de verdad en `fabric-comfandi-datalake-qa` y devolver
   la ficha de la celda 10.

---

## 10. Convenciones del repositorio (siguen vigentes)

- Los entregables son los `.ipynb` y se editan directamente subiendo de versión. **No** se
  regenera con `build_entregables.py`; `metricas_auditoria.py` ya no refleja lo que corre.
- Nunca renombrar ni eliminar variables o funciones existentes. Añadir es seguro.
- Cualquier interruptor nuevo entra con el valor por defecto que reproduce el comportamiento
  anterior: `EXIGIR_PARIDAD = "AUTO"` y `ZONA_EN_CUALQUIER_POSICION = False` lo cumplen.
- Nada de sintaxis que exija Python 3.12: los clústeres van por debajo.
- Al parchear: cada ancla encaja **exactamente una vez**, compilar todas las celdas antes de
  escribir, y comprobar con AST que no desapareció ninguna declaración.

---

## 11. Documentos relacionados

| Archivo | Qué |
|---|---|
| `CONTEXTO_POSTGRES_FABRIC.md` | El traspaso de Postgres. **§3 y §4.2 quedan corregidos por este documento.** |
| `CONTEXTO.md` | Qué obtiene la auditoría, los dos notebooks y su orden |
| `MCD.md` | El modelo de datos del reporte |
| `AUDITORIA_METRICAS.md` | El documento maestro, celda por celda |
| **`CONTEXTO_VERIFICACION_Y_ANALITICA.md`** | este |
