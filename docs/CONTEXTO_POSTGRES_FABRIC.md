# Contexto · Postgres desde Fabric, y el reconocimiento de flujos

> Documento de traspaso. Está escrito para que otra IA (o cualquiera que llegue nuevo) pueda
> continuar sin haber visto la conversación anterior. Todo lo que aquí se afirma como
> «verificado» lo está; lo que no, lo dice.

---

## 1. El problema

La auditoría de métricas mide cada fuente en **Stratio** y en **Fabric** con las mismas
reglas y coteja las dos medidas. Para las fuentes que son ficheros (parquet, CSV) eso ya
funciona: los dos lados leen con Spark y calculan la misma huella SHA-256.

**Para las fuentes que son Postgres, no.** En Fabric el compute de Spark **no tiene ruta a
Postgres**: lo corta el firewall de la base. Quien sí tiene ruta es el **gateway
on-premises**, y al gateway solo le llegan conexiones de Fabric — no un `psycopg2` ni un
`spark.read.jdbc()` desde el notebook.

En Stratio no hay ese problema: lee Postgres directo por JDBC.

Resultado: hoy la mitad Postgres de la migración no se puede medir en Fabric, y por tanto no
se puede cotejar.

---

## 2. La solución que existe hoy

Hay una **DataPipeline** creada para esto: **`qa_consulta_postgres`**. Recibe un SQL como
parámetro, lo ejecuta contra Postgres a través del gateway, y devuelve las filas en la salida
de una actividad Lookup. El notebook la dispara por la API REST de Fabric y lee el resultado.

```
notebook --REST--> pipeline qa_consulta_postgres --gateway--> Postgres
   \------------- filas (JSON) <---------------------------------/
```

### Coordenadas

| | |
|---|---|
| Pipeline | `qa_consulta_postgres` · `9c7de014-3dfa-4cd1-9bd8-4226d75260b3` |
| Workspace | `fabric-comfandi-datalake-qa` · `f46ef407-ab98-4741-8a4e-25d1d42ab145` |
| Conexión QA | `PG_ANALITICA_DEV_QA-RW` · `2d882b03-c343-489b-847f-e095b32c12c9` |
| Conexión PROD | `PG_ANALITICA_PROD-RW` · `884fa3bf-0a8f-4b6b-bb48-a658f3222ccf` |
| Servidor | `psql-analitica-dev-qa-eus2.postgres.database.azure.com` · base `analitica` · usuario `analitica_rw` |
| Parámetro | `consulta` (string) |

Dos actividades dentro: un **Lookup** con `firstRowOnly: false` (devuelve todas las filas, no
solo la primera) y un `SetVariable` que deja el conteo.

Sin credenciales en los notebooks: la clave vive en la conexión de Fabric y solo la ve el
gateway.

### Las tres llamadas REST

Contra `https://api.fabric.microsoft.com/v1`, con token de `https://api.fabric.microsoft.com`
(dentro de Fabric sale de `notebookutils.credentials.getToken(...)`).

1. `POST /workspaces/{ws}/items/{pipeline}/jobs/instances?jobType=Pipeline`
   con `{"executionData": {"parameters": {"consulta": "<SQL>"}}}` → **202**
2. `GET /workspaces/{ws}/items/{pipeline}/jobs/instances/{corrida}` → sondear hasta
   `status == "Completed"`
3. `POST /workspaces/{ws}/datapipelines/pipelineruns/{corrida}/queryactivityruns`
   con una ventana de fechas → buscar la actividad `activityType == "Lookup"`; las filas están
   en `output.value`, como lista de diccionarios.

### Las tres trampas (ya costaron tiempo, ya están resueltas en el código)

1. **El 202 del paso 1 no es una operación asíncrona.** El patrón habitual de Fabric
   (202 + `x-ms-operation-id` + sondear `/operations/{id}`) **no aplica**: en el arranque de un
   trabajo el 202 *es* la respuesta buena y el id de la corrida viene en la cabecera
   **`Location`**, no en el cuerpo. Seguir `x-ms-operation-id` lleva a sondear algo que no
   existe.
2. **`queryactivityruns` exige ventana de fechas.** Sin `lastUpdatedAfter` /
   `lastUpdatedBefore` responde **200 con lista vacía**, que se confunde con «la corrida no
   tuvo actividades». Conviene abrirla amplia (día anterior → ahora + 5 min).
3. **`datasetSettings` va al nivel de `typeProperties`, no dentro de `source`.** Anidado en
   `source`, la pipeline falla con *«Cannot find data set in the activity»*. Esto es de la
   pipeline, no del notebook: si hay que republicarla, tenerlo en cuenta.

### Los límites que condicionan todo el diseño

- **Una corrida tarda ~1 minuto**, casi todo en arrancar la pipeline. No sirve para consultas
  en bucle fila por fila: una llamada por tabla, y que devuelva agregados.
- **El Lookup no está hecho para traer tablas completas**: corta por número de filas (~5000) y
  por tamaño de salida. Un resultado de exactamente 5000 filas está **truncado y es mentira**.

De esos dos límites sale la consecuencia de fondo:

> **Desde Fabric, a Postgres solo se le pueden pedir agregados. El DataFrame nunca llega al
> notebook.**

---

## 3. Qué se puede y qué no se puede medir así

Esto es lo que hay que tener claro antes de tocar el notebook de métricas.

| | Desde Fabric, vía pipeline |
|---|---|
| Conteo de filas | **sí** |
| Esquema, tipos, nulabilidad | **sí** (`information_schema`) |
| Nulos, distintos, min, max, sumas, longitudes, constantes, candidatas a llave | **sí**, en SQL |
| Huella del dato | **sí**, calculándola **dentro** de Postgres |
| `hash_dataset` de Spark (el del notebook de métricas) | **no** — necesita el DataFrame |
| Percentiles, stddev, top-N de valores frecuentes | **no** — necesitan el DataFrame |
| Métricas forenses de texto (las 7 regex) | **no** por la misma razón |

**Consecuencia para la paridad:** si Fabric mide en SQL y Stratio mide en Spark, se están
comparando dos formas distintas de medir y las diferencias no son del dato. Para que el cotejo
signifique algo, **el lado de Stratio tiene que medirse con el mismo SQL empujado a su
Postgres** (Stratio sí puede: tiene JDBC directo). Es decir: para fuentes Postgres, la paridad
es **SQL contra SQL**, no Spark contra Spark.

---

## 4. Estado actual del trabajo

### 4.1 Los notebooks de métricas · `v5`

`auditoria_metricas_STRATIO_v5.ipynb` y `auditoria_metricas_FABRIC_v5.ipynb`, derivados de los
`v4.1` por parches de texto verificados (cada ancla debía encajar exactamente una vez; cero
declaraciones perdidas; `FUENTES` y credenciales intactas; todas las celdas compilan).

Cambios respecto a `v4.1`:

1. **`EJECUTAR_CP` ya manda.** Era un flag decorativo: `plan_de_ejecucion()` lo forzaba a
   `True` y `PLAN["cp"]` no se leía en ninguna otra parte. En `False` no se calcula el checksum
   SHA-256 del dataset, ni el hash por columna, ni el muestreo, ni el desglose por partición —
   que es la pasada cara. Sí se siguen midiendo CP-01 conteo, CP-02 esquema, perfilado, ID, VG
   y contrato. El veredicto del dato pasa a `SIN_PARIDAD` (que **no** es «diferente»: es «no se
   midió»). `ID-02` y `ID-08` quedan en `NO_EVALUABLE` porque leen del checksum.
2. **Ventana de fechas**: `ALCANCE_DESDE` / `ALCANCE_HASTA` acotan los objetos particionados
   por fecha (los flujos *rewrite*). Cualquiera de los dos extremos puede ir vacío —
   «desde X en adelante» no se podía expresar antes. Todas las particiones de la ventana se
   miden como **un solo dataset**. La etiqueta del alcance es la ventana **pedida**, no las
   particiones que resultaron existir, para que Stratio (con más historia) y Fabric (que
   arranca después) se emparejen; las fechas que le falten a un lado salen como hallazgo en
   `diferencias.particiones`. También se puede declarar **por fuente**:
   `{"ruta": "...", "desde": "01/08/2026"}`.
3. **El cotejo empareja por `clave_cotejo`, no por id.** La clave sale de la ruta sin los
   segmentos de zona ni las carpetas contenedoras, así que
   `/data/prod/trusted/sap/crm/contactabilidad/ADR2/registrosValidos/` (Stratio) y la tabla
   `sap_crm_contactabilidad_adr2` (Fabric) se emparejan solas. Se conserva la ruta entera
   (`sap`, `crm`, `contactabilidad`) para no cruzar tablas homónimas de otros proyectos.
4. **Las carpetas contenedoras ya no dan nombre**: el objeto de `.../ADR2/registrosValidos/`
   se llama `ADR2`. Las varias partes del parquet se leen como un solo dataset.
5. **La celda 12.2 guarda el cotejo.** Antes lo imprimía y lo perdía.
6. `COLUMNAS_EXCLUIDAS_HASH` subido a la celda de configuración: cuando Stratio particiona
   Hive (`fecha=...`), Spark materializa `fecha` como columna y el hash difiere aunque el dato
   sea idéntico. Excluyéndola, la paridad pasa y la diferencia de esquema se reporta aparte
   (no se esconde).

**Verificación:** 8 suites de prueba contra el código real de los notebooks, todas pasando.
**No se han ejecutado nunca sobre Spark real, ni en Stratio ni en Fabric.**

### 4.2 El piloto genérico · `piloto_postgres_fabric_v1.ipynb`

Prueba la ruta notebook → pipeline → gateway → Postgres, e incluye una huella de paridad
calculada dentro de Postgres (SHA-256 por fila sobre el texto canónico, y 4 sumas de rebanadas
del hash — independiente del orden de las filas y de memoria constante, a diferencia de
`string_agg`, que revienta en tablas grandes).

La canonicalización está alineada con `expr_canonica()` del notebook de métricas (separador
`chr(1)`, marca de NULL `chr(0)||'NULL'||chr(0)`, rebanadas en 1/16/31/46 de ancho 15).
**Eso no la hace intercambiable con el hash de Spark**: el JDBC se mete por medio con su propio
mapeo de tipos y de zona horaria. Está alineada para que, si algún día se quieren cruzar, la
diferencia esté acotada y documentada.

**Verificación:** probado contra un simulador de la API de Fabric con las tres trampas puestas.
Verificado que coge el id de `Location` y no el `x-ms-operation-id` señuelo, que siempre manda
la ventana de fechas, que una corrida `Failed` no pasa por buena, que un Lookup fallido propaga
el error de Postgres, que `firstRowOnly: true` se detecta, y que 5000 filas exactas se marcan
como truncado. **El simulador cubre la forma de las respuestas, no el gateway real. Nunca se ha
ejecutado contra Fabric.**

### 4.3 El piloto de reconocimiento · `piloto_tpos_client_v1.ipynb`

**Este es el que hay que ejecutar ahora.** Pinchado en el flujo `01-landing-feco-tpos-client`.

No coteja nada: **descubre** qué tabla de Postgres alimenta ese flujo, con qué columnas y qué
tipos, para poder alinear después las métricas.

⚠️ **Compila, pero NO está probado.** Se interrumpió la prueba contra un Postgres simulado
antes de terminarla. Es lo primero que habría que hacer, o asumir que la primera ejecución real
hará de prueba.

---

## 5. El flujo que se está reconociendo

| | |
|---|---|
| Flujo | `01-landing-feco-tpos-client` |
| Objeto | `TPOS_CLIENT` |
| Ruta en Fabric | `/Files/bronze/feco/sgdatos/TPOS_CLIENT` |
| Sistema fuente | `feco / sgdatos` |
| Columnas | `NROIDE`, `NOMCLI`, `APECLI`, `EMAIL` (texto) · `TIPOID` (`decimal(2,0)`) |
| Filas | 2.444.179 — **medido el 2026-08-12, orientativo** |

Las columnas y el conteo salen de un cotejo viejo que estaba en el repo
(`historico/corridas/comparar/tpos_client__PARQUET__total__20260812T142820Z__c84b3ab6.json`),
medido en el workspace `demo-comfandi-camilo-migracion` / `comfandi_vivienda.Lakehouse`, que ya
no se usa. **La tabla se sobreescribe, así que ese conteo sirve para reconocer la tabla, no
para cuadrar nada.**

La pista fuerte no es el conteo: es la **firma de columnas**. Cinco columnas llamadas `NROIDE`,
`NOMCLI`, `APECLI`, `EMAIL` y `TIPOID` juntas no son casualidad.

### Cómo busca el notebook

Una sola consulta con tres vías independientes (porque cada corrida cuesta un minuto):

- **A · por columnas** — tablas con al menos 4 de las 5 columnas conocidas. Es la vía fuerte.
- **B · por nombre** — el nombre se parece a `TPOS_CLIENT`, con y sin guiones bajos.
- **C · por esquema** — el esquema se llama como el sistema fuente (`feco`, `sgdatos`, …).

Una tabla que salga por las tres es casi con seguridad la buena. Si solo sale por nombre, hay
que confirmarla antes de creérsela. El ranking pondera la firma de columnas por encima del
nombre.

### Orden de ejecución y coste

| Celda | Qué hace | Corridas |
|---|---|---|
| 1-4 | Configuración, REST, `consultar()`, datos del flujo | – |
| **5** | **Prueba de vida** — si falla, parar y correr `diagnostico()` | 1 |
| 6 | Radar: encontrar la tabla | 1 |
| 7 | Confirmar: esquema real y conteo | 1 |
| 8 | Métricas por columna, en SQL | 1 |
| 9 | La ficha: el JSON a devolver | – |
| 10 | Diagnóstico, solo si algo falla | – |

**4 corridas ≈ 5 minutos.** Si ya se sabe el nombre de la tabla, se pone en `TABLA_PG` en la
celda 4 y la 6 se salta sola.

---

## 6. Qué hace falta ahora

1. **Ejecutar `piloto_tpos_client_v1.ipynb`** en el workspace `fabric-comfandi-datalake-qa` y
   devolver la salida de las celdas 4 a 9 (la celda 9 imprime una ficha JSON pensada justo para
   eso). Si la celda 5 falla, devolver la salida de `diagnostico()` de la celda 10.

2. **Con esa ficha**, decidir cómo se declara una fuente Postgres en el notebook de métricas de
   Fabric. Hoy en Stratio se declara como `jdbc:postgresql:esquema.tabla` en `FUENTES` y se lee
   por Spark. En Fabric eso no puede funcionar, así que hace falta un tipo de fuente nuevo
   —algo como `pipeline:postgres:esquema.tabla`— que en vez de leer el DataFrame construya los
   agregados y los pida por la pipeline.

3. **Alinear el lado de Stratio**: que para fuentes Postgres empuje el **mismo SQL** a su
   Postgres por JDBC, en vez de perfilar con Spark. Si no, se compara SQL contra Spark y las
   diferencias no son del dato.

4. **Sólo entonces**, las pruebas de paridad para fuentes Postgres.

### Preguntas abiertas

- ¿Existe realmente `TPOS_CLIENT` en la Postgres de Fabric, o este flujo viene de otra fuente
  (un SFTP, un extracto de SAP) y no de Postgres? El radar lo dirá.
- ¿El usuario `analitica_rw` ve todos los esquemas que hacen falta, o hay que pedir permisos?
- ¿Cuántas fuentes Postgres hay en total en el inventario? Con ~1 minuto por corrida y 3-4
  corridas por tabla, el coste total decide si esto es viable tabla a tabla o hace falta otra
  estrategia (por ejemplo, una pipeline de Copy que aterrice en el lakehouse y entonces sí se
  mida con Spark como todo lo demás).

---

## 7. Convenciones del repositorio que hay que respetar

- **Los entregables son los `.ipynb`**, y se editan directamente subiendo de versión
  (v4.1 → v5). **No** se regenera con `build_entregables.py`, pese a lo que dice el README:
  ese documento está desactualizado en este punto. Los notebooks están probados en Stratio
  Intelligence y en Fabric; regenerarlos desde el `.py` los reemplazaría por código que nunca
  se ejecutó allí.
- `metricas_auditoria.py` **ya no refleja lo que corre**. Verificado regenerando y comparando
  celda a celda: el Fabric `v4.1` sí correspondía, pero el Stratio `v4.1` venía de una versión
  anterior y le faltaban `SI_YA_EXISTE_EN_BUCKET`, `detectar_ambiente()` y las funciones
  `_objetos_planos` / `_id_de` / `_elegir_por_id` del comparador. Sin esas tres últimas, el
  cotejo en Stratio no encontraba **ningún** objeto, porque leía `resumen_ejecucion` como lista
  plana cuando la celda 11 escribe flujos con los objetos dentro. En `v5` se portaron.
- **Nunca renombrar ni eliminar variables o funciones existentes.** Añadir es seguro; quitar
  rompe. Las `FUENTES` (celda 3) de cada plataforma y `RUN_ID_STRATIO` se conservan intactas.
- **Nada de sintaxis que exija Python 3.12** (f-strings con saltos de línea dentro de `{}`,
  PEP 701): los clústeres van por debajo. Ya hubo que reescribir un `print` por esto.
- Al parchear un notebook: cada ancla debe encajar **exactamente una vez**, compilar todas las
  celdas antes de escribir, y comprobar con AST que no desapareció ninguna declaración.

---

## 8. Documentos relacionados

| Archivo | Qué |
|---|---|
| `README.md` | Entrada rápida — desactualizado en lo de regenerar desde el `.py` |
| `CONTEXTO.md` | Qué obtiene la auditoría, los dos notebooks y su orden |
| `MCD.md` | El modelo de datos del reporte: qué hay dentro del JSON |
| `AUDITORIA_METRICAS.md` | El documento maestro: detalle técnico celda por celda |
| **`CONTEXTO_POSTGRES_FABRIC.md`** | ← este |
