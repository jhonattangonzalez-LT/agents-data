# Contexto · los notebooks de métricas, para quien vaya a modificarlos

> Documento de traspaso. Escrito para una IA con acceso y herramientas sobre Fabric que va a
> **corregir y mejorar** los notebooks de métricas. Las instrucciones concretas de qué cambiar
> las da el usuario; esto es el mapa del terreno y, sobre todo, **lo que no se puede romper**.
>
> Todo lo que aquí se afirma como «verificado» lo está. Lo que no, lo dice.

---

## 1. Qué son estos notebooks

La migración mueve datos de **Stratio** a **Microsoft Fabric**. Estos dos notebooks miden cada
fuente en las dos plataformas con las mismas reglas y cotejan las medidas, para responder una
sola pregunta, tabla por tabla:

> **¿Llegó el mismo dato?**

No se responde con un `count(*)`: dos tablas con el mismo número de filas pueden tener valores
distintos, tipos distintos, columnas renombradas, o el mismo texto leído con un encoding roto.

**Sobre las fuentes esto únicamente lee** (`spark.read` / `SELECT`). No hay código de escritura
a bases de datos, ni activo ni comentado. La única salida son archivos JSON.

| Archivo | Dónde se ejecuta |
|---|---|
| `auditoria_metricas_STRATIO_v7.ipynb` | Stratio Intelligence |
| `auditoria_metricas_FABRIC_v7.ipynb` | Microsoft Fabric |
| `etl_validator_fabric_v3.ipynb` | Microsoft Fabric · el validador de flujos, con el mismo `REPORTES_V2` |

**No son intercambiables.** Son el mismo código salvo por las rutas de `FUENTES`, el destino
de descarga del bucket, y `FABRIC_WORKSPACE` / `FABRIC_LAKEHOUSE`.

El punto de encuentro es un bucket de Azure (`comfqametricsdevqaeus2`): Stratio sube su
reporte, Fabric sube el suyo, descarga el de Stratio y coteja. El orden importa.

---

## 2. Reglas duras — leer antes de tocar nada

Estas no son preferencias de estilo. Romper cualquiera de ellas rompe el producto.

### 2.1 Los entregables son los `.ipynb`. No se regeneran.

El `README.md` dice que nunca se editen a mano y que se regeneren con `build_entregables.py`
desde `metricas_auditoria.py`. **Ese consejo está desactualizado y seguirlo destruye trabajo.**

Verificado regenerando y comparando celda a celda: `metricas_auditoria.py` **ya no refleja lo
que corre**. El Fabric `v4.1` sí correspondía a lo que genera el `.py`, pero el Stratio `v4.1`
venía de una versión anterior y le faltaban `SI_YA_EXISTE_EN_BUCKET`, `detectar_ambiente()` y
las funciones `_objetos_planos` / `_id_de` / `_elegir_por_id` del comparador.

Los notebooks están probados en producción. El `.py` no. **Se editan los `.ipynb`
directamente y se sube de versión** (v4.1 → v5 → v6 → v7…).

### 2.2 Añadir es seguro. Quitar y renombrar, no.

Entre los dos notebooks hay **260 funciones y 233 variables de módulo**. Todas se dan por
existentes en algún otro sitio: celdas posteriores, funciones de diagnóstico que el equipo
llama a mano, y el comparador.

- **Nunca renombrar** una función o variable existente.
- **Nunca eliminar** una declaración, ni aunque parezca muerta.
- **Nunca dejar una variable sin valor** «para que la rellene el usuario»: el notebook se
  ejecuta de arriba abajo y un `None` inesperado revienta tres celdas más abajo.
- Si hace falta una variable nueva, se añade **con un valor por defecto que no cambie el
  comportamiento actual**.

Ejemplo de la ronda anterior: `EJECUTAR_CP` era un flag decorativo. Se le dio efecto real,
pero se dejó en `True`, que es lo que hacía antes.

### 2.3 `FUENTES` (celda 7) es del usuario. No se toca.

Cada plataforma tiene su propia lista, con decenas de rutas comentadas que son el historial de
lotes del equipo. Se conservan **byte a byte**. Lo mismo con `RUN_ID_STRATIO`, las credenciales
y los identificadores de workspace/lakehouse.

### 2.4 Nada de sintaxis que exija Python 3.12

Los clústeres van por debajo. En concreto, **nada de f-strings con saltos de línea dentro de
`{}`** (PEP 701). En la ronda anterior hubo que reescribir un `print` por esto: compilaba en la
máquina de desarrollo (3.12) y habría reventado en el clúster.

### 2.5 Los `print` son parte del producto

El usuario lee la salida del notebook para decidir. Un mensaje que miente es peor que un fallo.
Ejemplo real: cuando no se calcula el checksum, los dos lados traen `hash_dataset = None`, y
`None == None` se imprimía como `✅ iguales`. Hubo que cambiarlo a `NO MEDIDO`.

---

## 3. El método seguro para editar

Lo que funcionó en la ronda anterior, y que conviene repetir:

1. **Parches de texto anclados**, no reescrituras de celda. Cada ancla debe encajar
   **exactamente una vez**; si encaja 0 o 2 veces, abortar sin escribir nada.
2. **Compilar todas las celdas** antes de escribir el archivo.
3. **Verificar con AST** que no desapareció ninguna declaración.
4. Solo entonces escribir el `.ipynb` nuevo.

Script de verificación, listo para usar tras cualquier cambio:

```python
import ast, json

def decls(src):
    out = set()
    try:
        for n in ast.parse(src).body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.add(n.name)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    for x in ast.walk(t):
                        if isinstance(x, ast.Name):
                            out.add(x.id)
    except SyntaxError:
        pass
    return out

for plat in ("STRATIO", "FABRIC"):
    viejo = json.load(open(f"auditoria_metricas_{plat}_v6.ipynb"))["cells"]
    nuevo = json.load(open(f"auditoria_metricas_{plat}_v7.ipynb"))["cells"]
    assert len(viejo) == len(nuevo), "cambió el número de celdas"
    perdidas, malas = [], []
    for i, (a, b) in enumerate(zip(viejo, nuevo)):
        if a["cell_type"] != "code":
            continue
        sa, sb = "".join(a["source"]), "".join(b["source"])
        perdidas += [f"celda {i}: {x}" for x in sorted(decls(sa) - decls(sb))]
        try:
            compile(sb, f"c{i}", "exec")
        except SyntaxError as e:
            malas.append(f"celda {i} línea {e.lineno}: {e.msg}")
    fuentes_ok = "".join(viejo[7]["source"]) == "".join(nuevo[7]["source"])
    print(f"{plat}: perdidas={len(perdidas)} {perdidas} · no compilan={malas} · "
          f"FUENTES intactas={fuentes_ok}")
```

También conviene un detector de f-strings multilínea, y **comparar su número contra el de la
versión anterior**: lo que importa no es que haya cero, sino que no aumenten.

---

## 4. Mapa de las celdas

25 celdas (24 de código). Se ejecutan **en orden**, de arriba abajo.

| # | Celda | Qué hace | Tamaño |
|---|---|---|---|
| 1 | **CELDA 0** · qué se ejecuta | Los flags maestros y `plan_de_ejecucion()` → `PLAN` | 2,8 KB |
| 2 | **CELDA 1** · parámetros | 91 variables de configuración con sus valores por defecto | 3,9 KB |
| 3 | **CELDA 1.CONFIG** · *aquí se configura todo* | Lo que el usuario edita. **Va después de la 1 a propósito: manda sobre ella** | 9-11 KB |
| 4 | **CELDA 2** · entorno y Spark | Detección de plataforma/ambiente, memoria, sesión, FS. 35 funciones | 46 KB |
| 5 | **CELDA 2.2** · bucket de Azure | Subir y descargar reportes | 5-6 KB |
| 6 | **CELDA 2.1** · capacidad | Diagnóstico del nodo. No audita | 15 KB |
| 7 | **CELDA 3** · `FUENTES` | **La lista del usuario. No tocar** | 6 KB |
| 8 | **CELDA 4** · radar | Explora rutas, detecta formato y particiones, nombra los objetos. 51 funciones | 55 KB |
| 9 | **CELDA 4.1** · fuentes que no abren | Diagnóstico Postgres y SFTP | 12 KB |
| 10 | **CELDA 5** · lectores | Uno por tipo de fuente. Todo el reparto JDBC de Postgres. 29 funciones | 36 KB |
| 11 | **CELDA 6** · canonicalización y hash | `expr_canonica`, `calcular_hashes`, particiones. **El corazón de la comparabilidad** | 17 KB |
| 12 | **CELDA 7** · perfilado | Métricas por columna según tipo y tamaño | 22 KB |
| 13 | **CELDA 8** · validaciones | `validar_integridad` (ID-01..08), `validar_esquema` (VG-01..08) | 12 KB |
| 14 | **CELDA 9** · persistencia | Rutas, manifiesto, `etiqueta_alcance`, contrato propuesto | 7 KB |
| 15 | **CELDA 10** · auditar un objeto | `auditar_objeto()`: arma el reporte completo de un objeto | 22 KB |
| 16 | **CELDA 11** · orquestador | Recorre objeto × alcance, paraleliza, escribe el JSON | 34 KB |
| 17 | **CELDA 12** · resumen en pantalla | | 3 KB |
| 18 | **CELDA 13** · destino de reportes | | 1 KB |
| 19 | **CELDA 14** · sonda HDFS | Diagnóstico interactivo. No audita | 7 KB |
| 20 | **CELDA 15** · sondas de conexión | Postgres y SFTP. No audita | 15 KB |
| 21 | **CELDA 16** · comparador | 40 funciones. Similitud, controles, nulos, encoding, contrato | 83 KB |
| 22 | **CELDA 12.1** · subir al bucket | | 0,5 KB |
| 23 | **CELDA 12.2** · cotejo desde el bucket | **El cotejo que se usa de verdad** | 10 KB |

### Las celdas que difieren entre plataformas

Solo estas. Cualquier cambio en el resto debe aplicarse **idéntico** a los dos notebooks:

`0` (título) · `2` (CELDA 1) · `3` (CONFIG) · `4` (CELDA 2) · `5` (CELDA 2.2) ·
`7` (**FUENTES**) · `16` (CELDA 11) · `20` (CELDA 15) · `21` (CELDA 16) ·
`22` (CELDA 12.1) · `23` (CELDA 12.2)

---

## 5. Los conceptos que hay que entender antes de tocar

### 5.1 Las cinco huellas

No una, cinco. Es la **combinación** la que distingue «cambió el dato» de «cambió el nombre».

| Huella | Qué detecta |
|---|---|
| `hash_dataset` | El **dato**. Renombrar o cambiar de tipo NO lo altera; cambiar un valor, sí |
| `hash_conjunto_columnas` | Las columnas por su **contenido**: sobrevive a renombrar y reordenar |
| `hash_esquema_tipos` | Nombre + tipo de cada columna |
| `hash_nombres_columnas` | Solo los nombres |
| `hash_esquema_estricto` | Nombre + tipo + nullable |

Son **independientes del orden de las filas y del número de particiones** — eso es lo que
permite comparar dos motores Spark distintos. Se consigue con: hash SHA-256 por fila sobre un
texto canónico, y luego **sumas** de cuatro rebanadas del hash (posiciones 1/16/31/46, ancho
15). Una suma no depende del orden en que se sume.

**Si se toca `expr_canonica()` o `calcular_hashes()` en la CELDA 6, se invalidan todas las
mediciones anteriores.** Cualquier cambio ahí tiene que aplicarse a los dos notebooks a la vez
y obliga a volver a medir los dos lados.

### 5.2 Precisión comparable

Los topes de precisión decidían **cómo** se mide, no solo cuánto tarda. Salían de la memoria de
la sesión: Stratio (1 GB de ejecutor) contaba la cardinalidad con HyperLogLog (±1 %) y Fabric
(56 GB) de forma exacta. La misma tabla se medía distinto y el cotejo mostraba diferencias de
**medición** como si fueran del **dato**.

`PRECISION_COMPARABLE = True` los fija. **Tienen que ser idénticos en las dos plataformas.**

### 5.3 Los seis veredictos separados

Están separados a propósito: mezclarlos daría un «diferente» que no dice dónde mirar.

**del dato** · **de la medición** · **de encoding** · **de nulos** · **de controles** ·
**del contrato**

Ejemplo real de por qué importa: un hash difería, pero la causa no era que el dato cambiara —
Stratio había leído el archivo con el encoding equivocado (`Carn� Diplom�tico` →
`Carné Diplomático`). Sin esa distinción, alguien habría buscado el problema donde no estaba.

### 5.4 El contrato es propuesto, no oficial

Se deriva de la observación de un día. `nullable=false` significa «hoy no tenía nulos», no «es
obligatoria por acuerdo». `VG-07` seguirá en `NO_EVALUABLE` mientras no se publiquen contratos
reales.

---

## 6. Qué cambió en `v7` (la última ronda) · REPORTES_V2

Derivados de los `v6` por parches anclados (`patch_v7.py`). Cero declaraciones perdidas
(270 → 278 funciones, variables solo añadidas), `FUENTES` y credenciales byte a byte, las 14
celdas compartidas siguen idénticas entre plataformas, 14 suites pasando (11 heredadas + 3 nuevas).
Junto con ellos va **`etl_validator_fabric_v3.ipynb`** (2.0 → 3.0), derivado del notebook del
validador por el mismo método; su paquete `validador/` no se toca.

### 6.1 `REPORTES_V2` · raíz nueva, lo viejo no se mueve

```
Files/REPORTES_V2/
  metricas/<PLATAFORMA>/<ambiente>/
    objetos/<clave_cotejo>/<utc>__<run8>.json      un JSON por OBJETO: cada medición es un archivo
    flujos/<flujo>/<utc>__<run8>.json              índice por FLUJO: objetos, estados, tiempos, enlaces
    corridas/auditoria__<PLAT>__<utc>__<run8>.json el JSON de la corrida de siempre (sube al bucket)
    _manifiesto/                                   PLANO: leer_manifiesto() es un listdir plano
  cotejos/<clave_cotejo>/<mismo nombre base de siempre>
  cotejos/_totales/cotejo_total__STRATIO_vs_FABRIC__<utc>__<run8>.json
  descargados/<plataforma>/<ambiente>/
  validador/flujos/<flujo>/<CORRIDA>.json          el veredicto por flujo, UNA sola vez
  validador/corridas/ · dependencias/ · informes/ · analitica/<flujo>/
```

`RAIZ_REPORTES = "REPORTES_V2"` (CELDA 1 / CONFIG). El manifiesto arranca de cero: la primera
corrida no tiene «corrida previa» (`ID-07`/`ID-08`/`VG-08` → `NO_EVALUABLE` una vez).

**Lo que no ve la raíz nueva:** el generador de actas (`actas/descargar.py:18`, `actas/datos.py:37`,
`reportes/fuente.py:87,103`) lleva el prefijo `resultados/comparaciones/` literal. Los nombres base
del cotejo se conservan a propósito para que apuntarlo a `REPORTES_V2/cotejos/<clave>/` sea un
cambio de una línea cuando toque. Lo viejo sigue funcionando porque nada se movió.

### 6.2 Subida al bucket por objeto

`SUBIR_POR_OBJETO = True`. En `_reportar()` (CELDA 11), tras cada objeto: `guardar_objeto()` →
manifiesto (con `flujo` y `archivo_objeto`) → `guardar_parcial()` (que ahora también reescribe los
índices por flujo) → `_subir_avance_al_bucket()`. Cada paso va en `try/except`: un fallo del bucket
se imprime y la CELDA 12.1 lo reintenta al final.

En la CELDA 2.2: `subir_reporte_azure()` **actualiza en sitio** si el blob existe y su nombre
lleva el `RUN_ID[:8]` de la corrida en curso (sin `__v2`, sin buscar gemelos); otra corrida sigue con
`SI_YA_EXISTE_EN_BUCKET`. Nueva `subir_objeto_azure()` → `qa/objetos/<clave_cotejo>/<nombre>`,
nunca sobreescribe. Las dos funciones son idénticas byte a byte en las dos plataformas.

### 6.3 El enlace entre los tres reportes

`FUENTES` admite `{"ruta": ..., "flujo": "02-landing-sapcrm-adr2"}` — `_normalizar_fuente()` ya
dejaba pasar claves extra y los hijos de una carpeta explorada lo heredan por `dict(f)`. `flujo` va
al objeto, al manifiesto, al índice por flujo, al cotejo (`res["flujo"]`, `res["a"/"b"]["run_id"]`,
`archivo_objeto`) y al `cotejo_total`, cuyas `parejas` listan por tabla: flujo, run de Stratio, run
de Fabric, archivo del cotejo, veredicto del dato, veredicto de integridad y `corrida_validador`
(`CORRIDA_VALIDADOR` en la CONFIG, informativo). Con eso el «junto todo por tabla» ya no es manual.

### 6.4 Paralelismo

`PARALELISMO_FUENTES = 3` en Stratio y `6` en Fabric (con `AUTO` salían 2 y 5). En Stratio la
sesión da `defaultParallelism = 2`, así que 3 hilos solo solapan la planificación de un objeto con
la ejecución de otro: mejora modesta. El techo real es la configuración de sesión de la plataforma.

### 6.5 El validador (`etl_validator_fabric_v3.ipynb`)

- `RUTA_RESULTADOS = .../REPORTES_V2/validador`. El veredicto por flujo se escribe **una vez**
  (antes: plano + fechado). `corridas/`, `informes/`, `analitica/<flujo>/`.
- **Paso 5.1 · Dependencias y existencia** (celda nueva tras el Paso 5). Reutiliza `contrato_io()`
  tal cual. `clave_ruta()` normaliza; `grafo_es()` cruza salida→entrada por igualdad o prefijo
  (misma regla que `validador/dependencias.py`, que no se importa) y da `upstream`, `downstream`,
  orden topológico (`graphlib`) y ciclos; `existe_en_onelake()` hace `HEAD ?action=getStatus` con
  `_token("storage")`, sin Spark. Con `DEPENDENCIAS_CON_TODOS` lee los descriptores de todos los
  DataPipeline/SparkJobDefinition del ambiente para que haya con qué cruzar.
- Hallazgos: entrada inexistente → `BLOQUEANTE`; salida inexistente antes de ejecutar →
  `ADVERTENCIA`; upstream con salidas ausentes → `ADVERTENCIA`; ciclo → `ADVERTENCIA`.
- El veredicto por flujo gana `dependencias`, `existencia`, `n_entradas`, `n_salidas_declaradas`,
  `tiempo_total_segundos`; cada entrada/salida gana `existe`. El grafo va a `dependencias/<CORRIDA>.json`.
- Con muchas entradas/salidas (medido: hasta 18/15) la consola muestra conteos y las 6 primeras;
  el detalle completo está en el JSON.

**Sin verificar en ejecución real**, como siempre: nada corre sobre Spark ni contra OneLake desde
aquí. Las suites 12–14 ejercitan las funciones extraídas del `.ipynb` con el bucket y OneLake
simulados.

## 7. Qué cambió en `v6`

Derivados de los `v5` por parches anclados. **Cero declaraciones perdidas** (260 → 262
funciones, 233 → 241 variables, todas nuevas), `FUENTES` y credenciales intactas byte a byte,
todas las celdas compilan, 11 suites de prueba pasando: la 8 reproduce el cotejo
real de `ADR2` con sus números, la 10 corre el comparador contra **los dos reportes JSON
reales** del bucket y la 11 cubre el perfil normalizado (en positivo y en negativo) y la subida
de Stratio. Celdas tocadas: `0` (markdown), `1`
(CELDA 0), `2` (CELDA 1), `3` (CONFIG), `8` (CELDA 4), `21` (CELDA 16), `23` (CELDA 12.2).

### 6.1 `EXIGIR_PARIDAD` · paridad o integridad

La pregunta que responde la auditoría en **ingesta** es «¿llegó el mismo dato?». En
**analítica** no: los dos lados corren en momentos distintos, sobre ventanas distintas, y el
volumen no tiene por qué coincidir. Exigir paridad ahí llena el cotejo de errores que no lo
son y esconde los de verdad.

`EXIGIR_PARIDAD` (CELDA 1.CONFIG, bloque A.2) decide qué se le exige al cotejo:

| valor | qué hace |
|---|---|
| `"AUTO"` *(de fábrica)* | lo pega a `EJECUTAR_CP`: con checksum exige paridad, sin checksum pide integridad |
| `True` | exige PARIDAD aunque `EJECUTAR_CP` esté en `False` |
| `False` | modo INTEGRIDAD aunque haya checksum |

En modo INTEGRIDAD se **informan** (con `ℹ️`, sin fallar):
filas, `hash_dataset`, hash por columna, métricas por columna, particiones, nulos,
`CP-01` conteo, `CP-03` checksum, e `ID-07` / `ID-08` / `VG-08` — estas tres comparan cada
lado contra **su propia** corrida previa, así que entre plataformas nunca fueron una regresión.

Y se siguen **exigiendo**, con el mismo rigor: esquema y tipos (`hash_esquema_tipos`, columnas
que sobran o faltan), el contrato propuesto, `CP-02` esquema, el resto de reglas `ID` y `VG`,
el encoding y que las dos plataformas hayan medido con la misma precisión.

**No cambia nada de lo que se mide.** Solo cómo se clasifica y se imprime lo ya medido. Con
`EJECUTAR_CP = True` el notebook hace **exactamente** lo de `v5`: verificado comparando la
salida impresa carácter a carácter y el dict devuelto campo a campo.

Campos nuevos en el JSON (aditivos, nada se renombra): `modo_comparacion`,
`aspectos_de_paridad`, `aspectos_de_integridad`, `hallazgos_de_integridad`,
`veredicto_integridad`, `sellos_de_carga`, `totales.paridad_no_evaluada`,
`totales.con_esquema_distinto`, `esquemas_distintos`,
`reglas.no_comparables_entre_plataformas`,
`similitud.filas.sin_pareja_estimadas_sin_acotar`, `similitud.filas.todas_las_filas_difieren`,
`regresiones_de_integridad`, `perfil_normalizado`, y en `ejecucion`: `plan`, `exigir_paridad`
y `columnas_excluidas_hash`.
`veredicto` conserva el valor y el significado de siempre.

### 6.2 Tres prints que mentían

1. **`SIN_PARIDAD` se contaba como `NO_PASA`.** Con `EJECUTAR_CP = False`, `cotejar_ejecuciones`
   marcaba cada objeto como paridad `NO_PASA` y el veredicto global como `DIVERGENTE` — cuando
   lo que pasaba es que no se había medido. Ahora queda `NO_EVALUADA` y el global
   `SIN_PARIDAD_MEDIDA`. Causa de fondo: `_reporte_desde_resumen()` no copiaba
   `puntos_control`, así que `_sin_paridad()` nunca veía el `CP-03 NO_EJECUTADO`.
2. **Un cambio de tipo sin checksum decía «y el valor no coincide».** Sin hash por columna eso
   no se sabe. Ahora dice «cambió de tipo (el valor no se verificó)». Sigue siendo ruptura de
   contrato, que es lo correcto.
3. **`hash_dataset` sin medir en los dos lados salía como `❌ distintos`** en `imprimir_cotejo`,
   con `origen None / destino None` debajo. Ahora sale `➖ NO MEDIDO`. Es el mismo caso que ya
   se había arreglado en otro sitio: `None == None` no es «iguales», es «no se midió».

Los tres solo se manifestaban con `EJECUTAR_CP = False`, así que corregirlos no toca nada de
lo que hace una corrida con paridad.

### 6.3 El modo se ve, y la integridad significa lo mismo en los dos modos

Lo que hizo falta tras el primer cotejo real de analítica: el usuario corría en PARIDAD sin
saberlo y no había forma de verlo en la salida.

1. **`MODO DEL COTEJO`** se imprime en la cabecera de cada objeto y en el resumen de la
   CELDA 12.2, en los dos modos, nombrando la variable: `[EXIGIR_PARIDAD]`.
2. **`VEREDICTO DE INTEGRIDAD` se imprime siempre**, no solo en modo integridad. Era la
   respuesta a «¿y la integridad?» y estaba calculada pero sin imprimir.
3. **`veredicto_integridad` ya no depende del modo.** Antes, en paridad, las regresiones de
   `CP-01` y `CP-03` lo dejaban en `INTEGRIDAD_CON_HALLAZGOS`: contaba la diferencia de dato
   dos veces. `_regresiones_de_integridad()` deja fuera **siempre** `CP-01`, `CP-03`,
   `ID-07`, `ID-08` y `VG-08`. Los tres últimos comparan cada lado contra **su propia**
   corrida previa — en el caso real, Stratio-QA contra una corrida de Stratio-PROD de dos
   semanas antes— y no dicen nada de la migración. `res["controles"]["veredicto"]` no se toca:
   en paridad sigue valiendo lo de siempre.
4. **Si estás en paridad y la integridad sí cuadra, lo dice y dice cómo cambiarlo**: una línea
   con `EXIGIR_PARIDAD = False`. Solo sale cuando la integridad está OK y el dato difiere, así
   que nunca aparece sobre un fallo real de ingesta.
5. **`ID-07` / `ID-08` / `VG-08` van anotadas en los dos modos**: «cada lado se compara contra
   SU corrida previa, no contra el otro lado». En paridad no cambia su clasificación —siguen
   contando como mejora o regresión igual que en `v5`—, solo se explica qué son.
6. **`EXIGIR_PARIDAD` acepta las palabras**: `"PARIDAD"` y `"INTEGRIDAD"` además de
   `True` / `False` / `"AUTO"`, y avisa en pantalla si el valor no se reconoce en vez de caer
   en silencio al comportamiento por defecto.

### 6.4 `comparar_perfil_normalizado()` · la evaluación de integridad de verdad

La pregunta que responde: **¿los dos lados interpretan y extraen el dato igual?** No compara
valores ni volúmenes: compara **cada métrica por columna como proporción de las filas de su
lado**. Así, que un lado tenga 3.578.723 filas y el otro 3.576.473 deja de importar, y lo que
queda a la vista es si el flujo lee lo mismo.

Tres familias, y cada una se compara como toca:

| familia | qué entra | cómo se compara |
|---|---|---|
| **conteos** | vacíos, ceros a la izquierda, mayúsculas, centinelas, no-ASCII, caracteres de control, espacios en bordes, enteros/numéricos/fechas como texto, correos, verdaderos/falsos, anteriores a 1900… | proporción sobre las filas del lado · desvío en **puntos porcentuales** |
| **forma** | `tipo_spark`, `longitud_minima`, `longitud_maxima`, `bytes_minimo`, `bytes_maximo`, `es_constante`, `candidata_a_llave` | **igualdad exacta** — un cambio aquí es truncamiento o cambio de tipo |
| **ratios** | `pct_nulos`, `pct_completitud`, `pct_cardinalidad`, `longitud_promedio_referencial` | puntos porcentuales; el promedio, desviación relativa |

`valores_distintos` y `dias_distintos` **no** entran como conteo a propósito: la cardinalidad no
escala linealmente con las filas y ya se compara normalizada en `pct_cardinalidad`. Contarla dos
veces producía falsos desvíos cuando los volúmenes eran muy distintos.

La tolerancia es `TOLERANCIA_PERFIL_PP` (0,5 puntos porcentuales de fábrica). Un desvío por
encima es **hallazgo de integridad** en los dos modos, y suma `"perfil"` a
`hallazgos_de_integridad`.

Medido sobre `ADDR2` con los dos reportes reales: **110 comparaciones en 6 columnas, desvío
máximo 0,0094 pp**. Los ceros a la izquierda de `ADDRNUMBER` y `PERSNUMBER` se preservan al
100 % —el fallo clásico de una migración SAP—, las longitudes son idénticas y no hay daño de
encoding. Y probado en negativo: un truncamiento de `longitud_maxima`, un cambio en la
proporción de ceros a la izquierda y un salto en la proporción de nulos se detectan los tres;
reducir el volumen a la mitad manteniendo las proporciones **no** lo dispara.

### 6.5 Detector de **sello de carga** — lo que costó el primer cotejo de analítica

`detectar_sellos_de_carga()` busca columnas **constantes en los dos lados y con valor distinto
entre ellos**. Un sello de carga (`Fecha_carga`, `fecha_proceso`, `run_id`, `ingestion_ts`…)
vale lo mismo en todas las filas de una corrida y cambia de una corrida a la siguiente. Si entra
al hash, **todas** las filas difieren y `hash_dataset` no puede coincidir jamás, por idéntico
que sea el dato de negocio.

Es la diferencia más cara de diagnosticar que hay, porque el cotejo canta «0 % de identidad»
mientras el 99,9 % del dato está bien. Medido sobre los parquet de `ADR2` el 2026-09-16:

| | filas idénticas |
|---|---|
| con `Fecha_carga` (lo que hashea el notebook) | **0** de 3.578.723 |
| sin `Fecha_carga` (las 5 columnas de negocio) | **3.574.043** de 3.578.723 · **99,869227 %** |

**Solo diagnostica. No cambia nada de lo que se mide:** la columna se sigue hasheando,
perfilando, comparando y metiendo en el contrato como cualquier otra — no se esconde. Lo único
que hace es decir *por qué* el porcentaje de identidad del dato no significa nada en ese objeto,
para que no se lea como un fallo de la migración y se busque el problema donde no está.

**No propone excluir la columna.** La primera versión de este aviso recomendaba declararla en
`COLUMNAS_EXCLUIDAS_HASH`, y era mal consejo: sacar una columna real del hash es dejar de
atestiguarla, justo lo contrario de lo que busca una auditoría de integridad. El aviso manda a
leer el **VEREDICTO DE INTEGRIDAD**, que es donde está la respuesta. `COLUMNAS_EXCLUIDAS_HASH`
sigue existiendo y sigue en `[]`: es del usuario y para el caso para el que se creó (la columna
de partición que Spark materializa), no para esto.

Sale en el cotejo por objeto y en el resumen de la CELDA 12.2, en los dos modos: en paridad
explica el fallo, en integridad quita ruido.

### 6.6 El estimador de filas sin pareja, acotado

`_estimar_filas_distintas()` saca el número de filas que difieren de **cuatro** sumas parciales
del hash. Es un estimador de momentos con una varianza enorme, y podía devolver más filas de las
que tiene la tabla. Visto en el cotejo de `ADR2`:

```
11.304.386 sin pareja   sobre una tabla de 3.578.723 filas
-215,877646859 % de las filas coinciden
```

Un porcentaje de coincidencia no puede ser negativo y no puede haber más filas sin pareja que
filas. Se acota al total, el crudo se conserva en
`similitud.filas.sin_pareja_estimadas_sin_acotar`, y cuando se acota se dice con palabras:
«TODAS las filas difieren · el estimador se salió de rango y se acota al total de la tabla».

**Esto sí cambia lo que imprime una corrida con paridad**, y a propósito: lo que imprimía era
falso. Es el único cambio de `v6` que toca el modo paridad.

### 6.7 `comparar_medicion` ya vigila `COLUMNAS_EXCLUIDAS_HASH`

Si un lado saca una columna del hash y el otro no, los dos `hash_dataset` se calculan sobre
**columnas distintas** y dejan de ser comparables. `comparar_medicion()` no lo miraba: la
diferencia salía como «el dato no coincide», sin decir que era de configuración. Es la trampa
exacta de declarar `COLUMNAS_EXCLUIDAS_HASH` en una sola plataforma — justo lo que invita a
hacer el detector de sello de carga.

Ahora es un aspecto más de la medición («columnas fuera del hash»), así que una lista distinta
deja `medicion.iguales = False`, cuenta como hallazgo de integridad y sale en pantalla. Cuando
las dos listas coinciden —el caso normal— no cambia ni una línea de la salida.

### 6.8 Stratio ya no se niega a subir al bucket

Era la divergencia de §8.2. El `subir_reporte_azure()` de Stratio era la versión vieja: si en el
bucket ya había un reporte con los **mismos objetos y hashes**, omitía la subida sin más. Con
`SALTAR_YA_AUDITADOS = False` para repetir una prueba, Stratio medía otra vez y **se negaba a
subir**, así que el cotejo se hacía contra el reporte viejo sin que nadie se enterara.

Se portó la versión de Fabric: `SI_YA_EXISTE_EN_BUCKET` con `VERSIONAR` (de fábrica, sube
siempre como `__v2`, `__v3`…), `SOBREESCRIBIR` u `OMITIR`, expuesto en la CONFIG de Stratio.
`subir_reporte_azure()` es ahora **idéntica byte a byte en las dos plataformas** — verificado por
AST. `descargar_reportes_azure()` **no** se tocó: la de Fabric lleva la ruta
`/lakehouse/default/…`, que en Stratio no existe.

También se portó `detectar_ambiente()` a la CELDA 12.1 de Stratio, que derivaba el ambiente de
`REPORTES[0]["ejecucion"]["ambiente"]`. Los dos lados resuelven ya la carpeta del bucket por el
mismo camino, que es condición para que el cotejo los empareje.

### 6.9 `ZONA_EN_CUALQUIER_POSICION`

`clave_de_cotejo()` quitaba los segmentos de zona solo del **principio** de la ruta. En ingesta
basta porque `landingraw` / `bronze` van siempre delante. En analítica la capa cae en sitios
distintos en cada lado y los objetos no emparejan:

```
STRATIO  /data/prod/refined/core/gold/validaciones  ->  core_gold_validaciones
FABRIC   /Files/gold/core/validaciones              ->  core_validaciones      NO emparejan
```

En `True` la zona se quita esté donde esté y las dos claves coinciden. **Apagado por defecto**:
si una carpeta real se llama como una zona (`gold`, `qa`, `data`…), también se la llevaría por
delante. Mismo valor en las dos plataformas. La desambiguación de claves repetidas
(`registrosValidos` / `registrosRechazados`) sigue funcionando igual con el interruptor puesto.

---

## 8. Qué cambió en `v5`

Derivados de los `v4.1` por parches anclados. **Cero declaraciones perdidas**, `FUENTES` y
credenciales intactas, todas las celdas compilan, 8 suites de prueba pasando.

1. **`EJECUTAR_CP` ya manda.** Era decorativo: `plan_de_ejecucion()` lo forzaba a `True` y
   `PLAN["cp"]` no se leía en ninguna otra parte del archivo. En `False` no se calcula el
   checksum del dataset, ni el hash por columna, ni el muestreo, ni el desglose por partición
   — la pasada cara. Sí se siguen midiendo CP-01 conteo, CP-02 esquema, perfilado, ID, VG y
   contrato. El veredicto del dato pasa a `SIN_PARIDAD`, que **no** es «diferente»: es «no se
   midió». `ID-02` y `ID-08` quedan en `NO_EVALUABLE` porque leen del checksum.
2. **Ventana de fechas.** `ALCANCE_DESDE` / `ALCANCE_HASTA` acotan los objetos particionados
   por fecha (flujos *rewrite*). Cualquiera de los dos extremos puede ir vacío — «desde X en
   adelante» no se podía expresar antes. Todas las particiones de la ventana se miden como **un
   solo dataset**. También se declara por fuente: `{"ruta": "...", "desde": "01/08/2026"}`.
   La etiqueta del alcance es la ventana **pedida**, no las particiones que resultaron existir,
   para que Stratio (con más historia) y Fabric (que arranca después) se emparejen.
3. **El cotejo empareja por `clave_cotejo`, no por id.** La clave sale de la ruta sin los
   segmentos de zona ni las carpetas contenedoras, así que
   `/data/prod/trusted/sap/crm/contactabilidad/ADR2/registrosValidos/` y la tabla
   `sap_crm_contactabilidad_adr2` se emparejan solas. Se conserva la ruta entera para no cruzar
   tablas homónimas de otros proyectos.
4. **Las carpetas contenedoras ya no dan nombre**: el objeto de `.../ADR2/registrosValidos/` se
   llama `ADR2`. Las varias partes del parquet se leen como un solo dataset.
5. **La CELDA 12.2 guarda el cotejo.** Antes lo construía en memoria, lo imprimía y lo perdía.
6. **`COLUMNAS_EXCLUIDAS_HASH` subido a la CONFIG.** Cuando Stratio particiona Hive
   (`fecha=...`), Spark materializa `fecha` como columna y el hash difiere aunque el dato sea
   idéntico. Ojo: la exclusión afecta al hash del **dato**, no al del esquema — la diferencia de
   esquema se sigue reportando aparte, que es lo correcto.
7. Se portó a Stratio el aplanado de objetos del comparador (`_objetos_planos`, `_id_de`,
   `_elegir_por_id`). Sin eso, su `_cargar_reporte()` leía `resumen_ejecucion` como lista plana
   cuando la CELDA 11 escribe flujos con los objetos dentro: **no encontraba ningún objeto**.

---

## 9. Estado real y deuda conocida

### 8.1 Lo que NO está verificado

**Los `v5` y los `v6` nunca se han ejecutado sobre Spark real, ni en Stratio ni en Fabric.** Toda la
verificación es estática (compilación, AST) más las suites que ejercitan las funciones puras
extraídas de los propios notebooks. La lógica que toca Spark (`expr_clave_particion`, el filtro
de particiones sobre el DataFrame, los lectores) **no se ha probado en ejecución**.

### 8.2 Divergencia pendiente entre plataformas — verificada

Al pasar a `v5` solo se portó a Stratio el aplanado del comparador. **Stratio sigue llevando
código más viejo que Fabric** en:

- ~~**CELDA 2.2** — Stratio no tiene `SI_YA_EXISTE_EN_BUCKET` y omite la subida duplicada.~~
  **RESUELTO en `v6`** (§6.8): se portó la versión de Fabric, idéntica byte a byte.
- ~~**CELDA 2 y CELDA 12.1** — Stratio deriva el ambiente de `REPORTES[0]`.~~
  **RESUELTO en `v6`** (§6.8): usa `detectar_ambiente()`, como Fabric.
- La CONFIG de Stratio ya expone `SI_YA_EXISTE_EN_BUCKET`. Sigue sin exponer `AMBIENTE_FORZADO`,
  aunque está en su CELDA 1 con el valor correcto (`"QA"`).

Lo que queda de divergencia en la CELDA 16: el `_cargar_reporte()` de Stratio no rellena
`hash.columnas`, así que su comparador reporta «columnas no comparables» donde el de Fabric sí
empareja por hash de columna. El cotejo real se ejecuta en Fabric, así que no muerde, pero
está pendiente.

### 8.3 Límites del entorno, no del código

- **Stratio corre con `defaultParallelism = 2`**: solo 2 tareas a la vez en toda la auditoría.
  Es el techo, y no lo sube ninguna cantidad de memoria — se pide en la configuración de sesión
  de la plataforma, no desde el notebook. Fabric va con 8.
- **Stratio no tiene sistema de archivos compartido** (HDFS no es escribible y el home del
  workspace no está montado en los pods ejecutores, comprobado). Eso impide materializar en
  Parquet y deja **dos lecturas de Postgres por objeto** en vez de una. En Fabric sí funciona,
  vía OneLake.
- **Fabric no tiene ruta a Postgres**: lo corta el firewall. Ver
  `CONTEXTO_POSTGRES_FABRIC.md` — es un problema abierto con su propio documento y su propio
  piloto.

### 8.4 Trampas de Spark ya documentadas en el código

Conviene no «arreglarlas»: están así por una razón que costó encontrarla.

- `input_file_name()` devuelve cadena **vacía** cuando el DataFrame se sirve desde cache. Por
  eso hay una columna técnica `__archivo_origen` materializada.
- `df.persist()` **no devuelve una copia**: devuelve el mismo objeto ya marcado para cachear.
- Varios `countDistinct` en la misma agregación hacen que Catalyst inserte un `Expand` que
  replica cada fila una vez por distinct. Por eso la unicidad exacta se verifica **una columna
  por agregación**.
- `spark.sql.codegen.maxFields` (100 por defecto): una agregación con 47 columnas × 12 métricas
  son 564 campos, Catalyst desactiva el codegen **sin decir nada** y evalúa fila a fila, entre
  10 y 30 veces más lento. Es lo que hizo que una tabla de 5,8 M de filas llevara 3 h 43 min sin
  terminar. Por eso `TOPE_EXPRESIONES_POR_PASADA = 90` y **no se sube**.

---

## 10. Forma del JSON de salida

Un solo archivo por ejecución, con todos los objetos dentro. Los reportes nunca se
sobreescriben: el origen sí se sobreescribe a diario, así que ese JSON es el único registro de
cómo estaba el dato ese día.

```
resultados/<fecha>/auditoria__<PLATAFORMA>__<utc>Z__<run8>.json
resultados/comparaciones/<objeto>__<alcance>__<utc>__<run8>.json
resultados/comparaciones/cotejo_total__STRATIO_vs_FABRIC__<utc>__<run8>.json
resultados/descargados/
```

Raíz: `indice` · `ejecucion` · `tiempos` · `totales` · `resumen_ejecucion` · `contratos`

`resumen_ejecucion` es una **lista de flujos**, y cada flujo lleva sus `objetos` dentro. Quien
lea el JSON tiene que aplanarlo (`_objetos_planos`). Cada objeto:

```
objeto · clave_cotejo · nombre · tipo_fuente · ubicacion · plataforma_ambiente · estado
diagnostico · medido_utc · datos_del_utc · duracion_segundos · alcance · conteos
huellas · esquema · almacenamiento · lectura · particiones · validaciones
contrato_en · columnas · valores_frecuentes · comparado_contra
```

El detalle campo por campo está en `MCD.md`.

---

## 11. Documentos relacionados

| Archivo | Qué |
|---|---|
| `README.md` | Entrada rápida. **Desactualizado** en lo de regenerar desde el `.py` |
| `CONTEXTO.md` | Qué obtiene la auditoría, los dos notebooks y su orden |
| `MCD.md` | El modelo de datos del reporte, campo por campo |
| `AUDITORIA_METRICAS.md` | El documento maestro: detalle técnico celda por celda |
| `CONTEXTO_POSTGRES_FABRIC.md` | El problema abierto de Postgres desde Fabric |
| **`CONTEXTO_NOTEBOOKS_METRICAS.md`** | ← este |

---

## 12. Resumen para quien va a editar

1. Editar los `.ipynb`, **nunca** regenerar desde el `.py`.
2. Subir de versión (`v7` → `v8`), no sobreescribir.
3. Parches anclados que encajen exactamente una vez; abortar si no.
4. Compilar todas las celdas y verificar con AST **antes** de escribir.
5. Cero declaraciones perdidas. Añadir sí, quitar y renombrar no.
6. `FUENTES` y credenciales, intactas byte a byte.
7. Un cambio fuera de las celdas que difieren va **idéntico** a los dos notebooks.
8. Nada de sintaxis de Python 3.12.
9. Si se toca la CELDA 6, se invalidan las mediciones anteriores: hay que decirlo.
10. Los `print` son el producto. Que no mientan.
