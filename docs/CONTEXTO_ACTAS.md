# Contexto para generar las actas y los informes

Proyecto **Comfandi / Quind · migración Stratio → Microsoft Fabric**.
Este documento es el traspaso completo: qué documentos se producen, qué forma
tiene cada uno, de dónde sale cada cifra, con qué herramientas se mide y dónde
está cada cosa. Quien lo lea debería poder producir el acta del lote siguiente
—o el informe de salida a producción— sin preguntar nada más.

---


## §0 · Formato normalizado del acta de entrega (vigente desde el 2026-09-29, manda sobre el resto)

Pedido por el cliente al entregar los lotes 9 (v2.0) y 10 (v1.0). Generador: `generar_acta_normalizada.py`,
datos: `datos_normalizados.py`, verificación: `verificar.py --enlaces`.

1. Tabla de flujos entregados dividida en **ingesta, analítica y orquestadores**, con nombre en Fabric,
   nombre en Stratio, **FL-0xxx** y **capa (Bronze/Silver/Gold)**. Lo que falte se busca en
   `inventario/matriz.json`; si no está, se deja «sin código FL asignado» y se pide al usuario.
2. **Ejecución por flujo** (estado, inicio, duración, dependencias) y **cotejo de tablas completas por
   flujo** (filas a cada lado, columnas con perfil idéntico, huella/resultado), cada uno con su gráfica.
3. **Capa por tabla** en las tablas por flujo.
4. **Diferencias puntuales**: diferencia con su cifra, ejemplo concreto de la comparación y
   justificación en una línea. Nada de párrafos largos.
5. **Todos los enlaces al final**, organizados por flujo y tabla, apuntando al lakehouse, resueltos
   contra lo publicado y comprobados con HEAD. Ningún enlace roto; el generador no emite el acta si
   queda alguno sin resolver.
6. Criterio: ingesta VG, ID y CP · analítica VG e ID · orquestadores por ejecución.

## 1 · Qué es un acta de entrega

Un `.docx` que el equipo de QA entrega al cliente para que firme la aprobación
del despliegue a producción de un lote de flujos. No es un informe técnico: es
un documento de aceptación. Cada cifra que aparece tiene que ser verificable por
quien lo firma, y por eso el acta enlaza la evidencia en el portal de Fabric.

Dos actas de lotes distintos salen del mismo código, así que quedan comparables
entre sí. **Eso es una restricción de diseño, no una casualidad.**

---

## 1 bis · Tres familias de documento, y no se mezclan

El repositorio produce tres cosas distintas. Confundirlas es el error más caro,
porque cada una tiene un lector y un propósito diferentes.

| | **Acta de entrega** | **Acta técnica · reporte** | **Informe de salida a producción** |
|---|---|---|---|
| Para qué | Que el cliente **firme** la aprobación de un lote | Que el equipo **reparta trabajo** sobre lo que falla | Que el comité **autorice el despliegue** de lo ya aprobado |
| Quién lo lee | Revisores UAT, líder técnico, dirección | Desarrollo y QA | Comité de cambios y operación |
| Lleva firmas | Sí | No | Sí |
| Tono | Lo que se entrega y su evidencia | Seco, sin narrativa: flujo, error, objeto exacto, acción | Estado, riesgo y plan |
| Habla de lo que falla | No · va a un reporte aparte | Es su único tema | Sí, como riesgo conocido y controlado |
| Generador | `generar.py`, `generar_analitica.py`, `generar_mixto.py` | `reporte_consolidado.py`, `reporte_fallas.py`, `reporte_fallas_detalle.py`, `hallazgo_contrato.py` | pendiente · §10 |

**La regla que las separa:** el acta de entrega no menciona negativas. Cuando
durante un lote aparece algo que no pasa, no se mete en el acta: se saca a un
reporte técnico y el acta sigue hablando solo de lo que se entrega. Así se hizo
con `Informe_Analitica_Formatos_2026-09-23.docx` y con
`Fallas_Analitica_Detalle_2026-09-23.docx`, que acompañan al lote 7 sin
ensuciarlo.

### Los reportes técnicos que ya existen

| Generador | Qué produce |
|---|---|
| `reporte_consolidado.py` | Hallazgos por tipo de flujo: tabla maestra y, debajo, un bloque por hallazgo con la tabla que demuestra el error concreto —columna, tipo, filas, valor— y la acción requerida |
| `reporte_fallas.py` | Tablero: qué flujo falla, dónde y a quién pertenece. Una página por bloque de severidad. Sirve para repartir el trabajo |
| `reporte_fallas_detalle.py` | Listado seco de fallas de analítica: flujo, error, objeto exacto, reporte. Con el diccionario de códigos de error del motor |
| `hallazgo_contrato.py` | Rupturas de contrato: cambio de tipo, endurecimiento de nulos, columnas movidas, con lo que significa cada una |

---

## 2 · El formato canónico · diez puntos

Las actas 1 a 6 usan esta estructura, y es a la que hay que volver. El acta 7 se
desvió (ver §3) y el cliente pidió expresamente regresar a esta.

Antes del punto 1, sin numerar:

| Bloque | Contenido |
|---|---|
| Portada | «Proyecto de Migración de la Plataforma de Datos · Stratio → Microsoft Fabric», «ACTA DE ENTREGA DE FLUJOS», «Lote N · …», subtítulo con las cifras del lote |
| **Control de versiones** | Versión, fecha, autor, qué cambió. **El acta 7 lo omitió: hay que reponerlo.** |
| **Participantes** | Nombre, empresa, rol. Seis filas fijas, están en el generador |

Y los diez puntos:

| # | Título | Qué lleva |
|---|---|---|
| 1 | **Objeto del acta** | Qué se entrega y **qué criterio se exige**. Aquí se declara si el lote va por paridad (ingesta) o por integridad (analítica), y por qué |
| 2 | **Resumen de resultados** | Tabla indicador/resultado + las gráficas de cobertura y de resultado del dato |
| 3 | **Alcance del lote** | Qué flujo entra, con su origen, su objeto y su destino en el lakehouse. Es la lista que se aprueba |
| 4 | **Ejecución de los flujos** | Corrida, duración, filas escritas, estado. Aquí va la gráfica de duración |
| 5 | **Paridad del dato contra Stratio** (ingesta) · **Balance de la transformación** (analítica) | El cotejo. Filas a cada lado, delta, % de identidad |
| 6 | **Huella criptográfica del dato** (ingesta) · **Salidas escritas en el lakehouse** (analítica) | Checksum SHA-256 (obligatorio en ingesta); esquema y contrato en analítica |
| 7 | **Controles de calidad** | CP, ID y VG. Cuántos se evaluaron y cuántos cumplen |
| 8 | **Diferencias observadas y su justificación** | Una entrada por diferencia, con la causa **medida**. Ninguna diferencia queda sin causa |
| 9 | **Evidencia** | Dónde está cada archivo y el enlace que lo abre en el portal de Fabric |
| 10 | **Declaración y aprobación para producción** | Las decisiones que se solicitan, la declaración del equipo de pruebas y las firmas |

### Variantes por tipo de lote

- **Ingesta** → `generar.py`. Puntos 5 y 6 en su forma de paridad.
- **Analítica** → `generar_analitica.py`. Punto 5 es balance de transformación; punto 6, salidas escritas.
- **Mixto** (ingesta + analítica en el mismo lote) → `generar_mixto.py`. Es el de las actas 5 y 6.

---

## 2 bis · El acta del lote 5 es la referencia

El cliente la señaló como la mejor de todas. Antes de escribir una línea, abra
`~/Projects/reportes/Acta_Entrega_Flujos_Lote5_2026-09-17.docx` y mírela. Lo que
la hace buena no es el contenido, es cómo está organizada, y eso se puede copiar.

**Su esqueleto real**, tal como sale del documento:

```
Control de versiones
Participantes
1. Objeto del acta
2. Resumen de resultados
   2.1  Flujos de ingesta
   2.2  Flujos de analítica
3. Alcance del lote
   3.1  Flujos de ingesta
   3.2  Flujos de analítica
4. Ejecución de los flujos
5. Paridad del dato contra Stratio · flujos de ingesta
   5.1  Detalle de la comparación por flujo
   5.2  Huella criptográfica del dato
6. Integridad de esquema y de la transformación · flujos de analítica
   6.1  Balance de la transformación por flujo
   6.2  Esquema de cada salida
   6.3  Salidas escritas en el lakehouse
   6.4  Cotejo de paridad donde Stratio produce la misma salida
7. Controles de calidad
   7.1  Controles de paridad · flujos de ingesta
   7.2  Pruebas del validador · flujos de analítica
8. Diferencias observadas y su justificación
   Ingesta
   8.1  04-landing-sapcrm-adrc
   8.2  extraccion-fomento-full
   Analítica
   8.3  limpieza_remediacion_adrc
   …    una subsección por diferencia, titulada con el nombre del flujo
9. Evidencia
10. Declaración y aprobación para producción
Firmas
```

12 gráficas · 75 enlaces · 17 flujos. Diez puntos, y el detalle vive en
subsecciones.

### Las cuatro cosas que hay que copiar

**1 · Simetría dentro del punto, no secciones sueltas.**
Ingesta y analítica se tratan en paralelo como `x.1` y `x.2` del mismo punto
(2.1/2.2, 3.1/3.2, 7.1/7.2). El acta 7 sacó «Flujos de fotos» y «Orquestadores»
a puntos de primer nivel y con eso desordenó la numeración. Van dentro de 3 y 4.

**2 · Una subsección por diferencia, titulada con el nombre del flujo.**
Esto es lo más importante del formato y es lo que el acta 7 perdió al resumirlo
en una tabla. Cada diferencia lleva su propio `8.N  <nombre del flujo>` y dentro,
en este orden, lo que aplique (helper `bloque_8` en `generar_mixto.py:59`):

| Elemento | Helper | Para qué |
|---|---|---|
| Subtítulo de una línea | `parrafo` | Las cifras del caso: «98 columnas · 3.742.001 filas en Stratio y 3.741.999 en Fabric · dos filas fantasma del origen» |
| El mismo valor a cada lado | `cara_a_cara`, `tabla_valores` | Cuando la diferencia es de contenido: el valor en Stratio y en Fabric, con lo que cambia resaltado |
| Tabla del caso | `tabla` | Cuando hay un reparto que mostrar |
| **La comprobación, paso a paso** | `pasos` | La cadena causal numerada. Cada paso afirma algo y, al lado, dice con qué evidencia se sostiene. El último paso va en verde: es la conclusión |
| Cifras de cierre | `hechos` | Cuatro o cinco números en fila: filas, identidad, filas fantasma, registros perdidos, contrato |
| **Causa identificada** | `parrafo` con borde ámbar | El párrafo que cierra. Lo que se lee si solo se lee una cosa |

El bloque `pasos` es lo que convierte una diferencia en algo defendible. Así se
lee el de `04-landing-sapcrm-adrc`:

```
Qué pasó con esas dos filas
1  El origen entrega ADRC como CSV. Dos direcciones tienen un salto de línea
   dentro de un campo de texto        → el archivo es el mismo para las dos plataformas
2  El lector de Stratio corta la línea en el salto…
                                      → por eso Stratio cuenta 3.742.001 y 51 columnas
                                        tienen exactamente 2 nulos más
3  Fabric lee el campo entero, respetando las comillas…
                                      → por eso Fabric cuenta 3.741.999
4  Las 3.741.999 direcciones reales están en Fabric
                                      → las 2 de diferencia son las fantasma;
                                        ninguna dirección se perdió
```

Columna izquierda: qué pasó. Columna derecha: cómo se sabe. El lector sigue el
razonamiento sin tener que creer en la palabra de nadie.

**3 · Pies de gráfica que dicen qué mirar.**
No «Gráfica 8. Filas por flujo», sino «Gráfica 8. Filas leídas y escritas por
cada flujo de analítica. **Cuando la salida es menor, el flujo filtra.**» El pie
enseña a leer la gráfica.

**4 · Control de versiones y Firmas explícitos.**
Bloque de versión antes de Participantes; bloque de firmas con nombre, rol,
empresa y línea de fecha al cierre del punto 10.

### Cómo se alimenta

`bloque_8` lee cada caso de la especificación. Un caso completo se ve así:

```json
{"flujo": "04-landing-sapcrm-adrc",
 "subtitulo": "98 columnas · 3.742.001 filas en Stratio y 3.741.999 en Fabric · …",
 "ejemplos": [{"columna": "NAME1", "origen": "…", "destino": "…", "celdas": "2"}],
 "titulo_pasos": "Qué pasó con esas dos filas",
 "pasos": [["El origen entrega ADRC como CSV…", "el archivo es el mismo…"],
           ["El lector de Stratio corta la línea…", "por eso Stratio cuenta…"]],
 "hechos": [["Filas", "3.742.001 → 3.741.999", "neutro"],
            ["Identidad", "99,9979 %", "ok"],
            ["Direcciones perdidas", "0", "ok"]],
 "titulo_causa": "Causa identificada",
 "observacion": "La misma causa documentada en las tablas BUT000 del lote 4…"}
```

Todos los campos son opcionales salvo el título y `observacion`. Un caso sin
`pasos` sigue siendo válido; simplemente convence menos.

---

## 3 · Qué pasó con el acta 7 y cómo corregirlo

El acta 7 (73 flujos de analítica, 23-Sep) se generó con `generar_acta7.py`, un
generador nuevo que rompió el formato. El cliente lo aceptó pero pidió volver al
anterior: *«me gusta más el formato visual y organizacional»*, y señaló el lote 5
como el modelo (§2 bis).

**El acta 7 ya se entregó así y no se regenera.** Esta sección no es una tarea
pendiente: es la lista de lo que no se debe repetir en el lote 8.

Lo que se desvió, y cómo devolverlo:

| Desviación del acta 7 | Corrección |
|---|---|
| Nueve puntos en vez de diez | Volver a los diez títulos de §2 |
| Sin «Control de versiones» | Reponerlo antes de Participantes |
| Títulos propios («Flujos entregados», «Controles de integridad medidos sobre las salidas», «Tiempos de ejecución») | Usar los títulos canónicos |
| Puntos 4 y 5 partidos en «Flujos de fotos» y «Orquestadores» como secciones de primer nivel | Bajarlos a subsecciones del punto 3 (alcance) y del punto 4 (ejecución) |
| «Lo que no entra en esta acta» como sección | **Eliminado a petición del cliente.** El acta habla de lo que se entrega, no de lo que falta |
| La justificación de diferencias quedó en 9.1, como tabla plana | Va al punto 8, y **cada diferencia recupera su propia subsección `8.N` con bloque de pasos**, como en el lote 5 |
| Sin subsecciones simétricas ingesta/analítica | Reponer el patrón `x.1` / `x.2` dentro de cada punto |

**Lo que sí hay que conservar del acta 7**, porque es material nuevo que el
cliente pidió y aprobó:

- Los controles **ID-01, ID-02, ID-03, ID-04 y VG-01** medidos sobre el dato completo, tabla por tabla → van al **punto 7**
- El **cotejo contra el parquet real de Stratio** bajado por Rocket → va al **punto 5**
- Los **tiempos de ejecución** tomados del historial de Fabric → van al **punto 4**
- El **enlace al reporte de métricas de cada tabla** → va al **punto 9**
- La **justificación medida de cada diferencia** → va al **punto 8**

Es decir: el contenido del acta 7 es correcto y hay que conservarlo; lo que se
rehace es dónde va cada cosa.

---

## 4 · De dónde sale cada cifra

**Regla que manda sobre todas: nada se estima.** Si una cifra no se puede medir,
no entra en el acta.

| Dato | Fuente | Cómo se obtiene |
|---|---|---|
| Filas, esquema, versión, instante de escritura | `_delta_log` de la tabla en OneLake | `acta.py delta <capa/tabla>` |
| Duración de cada flujo | Historial de corridas de la API de Fabric | `acta.py tiempos` |
| ID-01…ID-04, VG-01 | Los parquet vigentes, leídos con DuckDB | `acta.py perfil` |
| Conteo y esquema de Stratio | Reporte de métricas que publica Stratio, en `resultados/reportes_v3/metricas/descargados/qa/stratio/` | lectura directa de OneLake |
| Cotejo fila por fila contra Stratio | Parquet del origen bajado por Rocket | `acta.py cotejo` |
| Veredicto del validador | `resultados/reportes_v3/validador/flujos/<flujo>/` | lectura directa de OneLake |

### Por qué el registro Delta y no la fecha del archivo

Las fechas de modificación de los parquet mienten cuando Fabric reescribe una
tabla: pueden quedar viejas aunque el commit sea de hoy. El `commitInfo.timestamp`
del `_delta_log` es lo único que dice de verdad qué corrida escribió la tabla.
Esto ya causó un error en el lote 6 y no debe repetirse.

### CP en ingesta: obligatorios, SHA-256 incluido

En ingesta las dos plataformas miden con `EJECUTAR_CP = True` y
`EXIGIR_PARIDAD = True`, y CP-01, CP-02, CP-03 (checksum SHA-256) y CP-05 se
exigen. `EXIGIR_PARIDAD = False` es solo el interruptor que se cambia al probar
analítica, que se aprueba con VG e ID.

Si un reporte de ingesta trae CP-03 en `NO_EJECUTADO`, es un hueco de medición:
se vuelve a medir con checksum; no se da por aprobado ni se declara «no aplica».
`acta.py cotejo` complementa al hash: cuando hay diferencia, dice qué registros
difieren y por qué.

CP-04 (muestreo) es **informativo en los dos grupos**: desde el notebook v18 es
`limit(10)` sin orden, se toma siempre y no aprueba ni rechaza.

---

## 5 · Las gráficas

Se dibujan con Pillow en `graficas.py`. Todas devuelven la ruta del PNG y se
insertan en el documento con `imagen(rId, 640, G.alto(ruta), alt)` seguido de
`pie_grafica("Gráfica N. …")`.

**Los pies se numeran en orden de aparición en el documento**, no en orden de
creación. Es un error fácil de cometer al insertar una gráfica nueva en medio.

### Catálogo

| Función | Qué muestra | Entrada |
|---|---|---|
| `cobertura(pasos, ruta)` | Embudo de etapas de la verificación | `[(etiqueta, valor, nota), …]` |
| `resultado(idn, casi, dif, ruta)` | Reparto idénticas / casi / con diferencia | tres enteros |
| `ejecucion(total, ok, valida, bloq, filas, ruta)` | Resultado de la corrida | enteros |
| `duracion(filas, ruta)` | Barra por flujo, de mayor a menor | `[{"flujo","segundos"}, …]` |
| `volumen(filas, ruta)` | Filas origen vs destino, log | `[{"flujo","filas_a","filas_b"}, …]` |
| `paridad(filas, ruta)` | % de identidad por flujo | `[{"flujo","pct"}, …]` |
| `controles(ok, tot, ruta)` | Controles de paridad que coinciden | dos enteros |
| `justificadas(casos, ruta)` | Diferencias con su causa | `[(flujo, pct, causa), …]` |
| `transformacion(filas, ruta)` | Filas de entrada y de salida, log | `[{"flujo","filas_in","filas_out"}, …]` |
| `pruebas(ok, omitidas, avisos, ruta)` | Pruebas del validador | tres enteros |
| `paridad_analitica(idn, dif, sin, ruta)` | Reparto del cotejo de analítica | tres enteros |
| `orquestadores(orq, ruta)` | Invocaciones de cada orquestador | `[{"nombre","actividades":[…]}, …]` |
| `controles_integridad(res, ruta)` | ID y VG sobre las tablas del lote | `[(cod, título, ok, tot, nota, informativo?), …]` |
| `cotejo_conteo(pares, ruta)` | Filas Stratio vs Fabric por tabla | `[(tabla, stratio, fabric), …]` |
| `repetidas(pares, ruta)` | Filas repetidas a cada lado | `[(tabla, pct_stratio, pct_fabric), …]` |
| `volumen_salidas(filas, ruta)` | Volumen escrito, log, etiquetas giradas | `[(tabla, filas), …]` |
| `diferencias_justificadas(casos, ruta)` | Cada diferencia con su causa medida | `[(tabla, stratio, fabric, causa), …]` |

Las cinco últimas se añadieron para el acta 7. Al volver al formato canónico se
siguen usando: son el contenido que el cliente aprobó.

### Reglas de las gráficas

- **Un control informativo no se pinta como falla.** ID-04 (existe llave única) y VG-01 no aprueban ni rechazan: van en azul con la etiqueta «informativo», no en ámbar. Stratio los trata igual.
- **Leyenda siempre que haya dos series.** Y el color de la barra no cambia con el resultado; el que cambia es el color de la cifra.
- **Decimales con coma**, como el resto del acta.
- **Las etiquetas no se encabalgan.** Si no caben en horizontal, se giran (ver `volumen_salidas`).
- Los textos largos se parten en líneas dentro de la caja; no se dejan salir por el borde derecho.

### Paleta

En la cabecera de `graficas.py`: azul Comfandi `#1A3A5C` para la identidad,
`#3268CB` para las barras, ámbar `#F5A623` para el acento, verde `#1E7A46` para
lo que cumple. Se dibuja al doble y se reduce, para que el texto quede nítido.

---

## 6 · Las herramientas y dónde están

Todo vive en `~/Projects/comfandi/cea-analytics-comfandi/qa-etl-validador-agent-v2/actas/`.

### El documento

| Archivo | Qué hace |
|---|---|
| `estilo.py` | El `.docx`: Calibri, paleta, logo de Quind, filete ámbar en los títulos. Expone `h1`, `h2`, `parrafo`, `run`, `tabla`, `tabla_enlaces`, `imagen`, `pie_grafica`, `firmas`, `salto`, `guardar` |
| `graficas.py` | Las gráficas, con Pillow |
| `datos.py`, `datos_analitica.py` | Leen la evidencia y calculan los totales. `url()` arma el enlace al portal de Fabric |
| `generar.py` | Acta de ingesta |
| `generar_analitica.py` | Acta de analítica |
| `generar_mixto.py` | Acta mixta — **la referencia de formato: es el del lote 5**. `bloque_8` (línea 59) arma cada caso del punto 8 |
| `generar_acta7.py` | El generador del lote 7. Se conserva por trazabilidad; **no es el modelo a seguir** |
| `descargar.py` | Baja la evidencia de OneLake a partir de la especificación |
| `verificar.py` | Comprueba que el `.docx` salió sano |
| `autoprueba.py` | Prueba con evidencia sintética, sin red |

### La medición · CLI

`acta.py` es el punto de entrada. Todo lo que produce se publica en el lakehouse
de QA, **no en disco temporal**: la evidencia tiene que sobrevivir a la sesión.

```bash
# estado del registro Delta de una tabla
python3 acta.py delta silver/agrupadoras_ape_repleg

# reporte de métricas de cada tabla, publicado en OneLake
python3 acta.py metricas --tablas tablas.txt --fecha 2026-09-23

# controles ID-01..04 y VG-01 sobre el dato completo
python3 acta.py perfil --tablas tablas.txt --fecha 2026-09-23 --salida perfil.json

# duración real de cada flujo
python3 acta.py tiempos --flujos flujos.txt --ventana 2026-09-22 2026-09-24 \
    --salida tiempos.json

# cotejo fila por fila contra el dato de Stratio
python3 acta.py cotejo --hdfs /data/prod/trusted/agrupadoras/ape_repleg \
    --tabla silver/agrupadoras_ape_repleg --llave PARTNER_E
```

`--tablas` y `--flujos` reciben un archivo con un nombre por línea; las líneas
que empiezan por `#` se ignoran. `perfil` necesita DuckDB: usar el intérprete de
`~/Projects/.venv/bin/python`.

Los módulos están en `herramientas/`:

| Módulo | Qué hace |
|---|---|
| `acceso.py` | OneLake, API de Fabric y Rocket en un solo sitio. Los ids de workspace y la lectura de secretos |
| `delta.py` | Lee el `_delta_log`: commits, estado, parquet vigentes, descarga |
| `metricas.py` | Construye y publica el reporte de métricas por tabla |
| `perfil.py` | Mide ID-01..04 y VG-01 con DuckDB y los añade al reporte publicado |
| `tiempos.py` | Duración de cada flujo desde el historial de Fabric |
| `stratio.py` | Lista y baja de Rocket, y cotéja contra Fabric con anti-join |

### Credenciales

Nunca se escriben en el código ni se imprimen.

| Qué | Dónde | Cómo se obtiene |
|---|---|---|
| OneLake y API de Fabric | CLI `fab` ya autenticado, o `notebookutils` dentro de un notebook | automático |
| Cookie de Rocket (Stratio) | `~/Projects/.rocket_cookie`, `chmod 600` | la pega el usuario desde el navegador; caduca |
| SAS del bucket de métricas | `~/Projects/.azure_metricas_sas`, `chmod 600` | sale del notebook de Stratio |

### Rutas fijas

```
Workspace del lakehouse   f46ef407-ab98-4741-8a4e-25d1d42ab145   datalake-qa
Lakehouse                 eae58d30-8ffe-4de2-b4d4-91e1734d0fd2   lh_transversal
Workspace de analítica    52aaec56-102a-4b7a-b3c5-6859f6421308   orchestration-qa
Workspace de ingesta      689d798c-2d22-42a1-a970-a19def0881bf   ingestion-qa
Rocket                    https://datafabric.comfandi.com.co/rocket

Files/resultados/actas/                                     las actas publicadas
Files/resultados/comparaciones/                             cotejos del validador
Files/resultados/flujos/<fecha>/                            corridas
Files/resultados/reportes_v3/validador/flujos/<flujo>/      veredicto
Files/resultados/reportes_v3/validador/analitica/<flujo>/   reporte analítico
Files/resultados/reportes_v3/metricas/descargados/qa/fabric/<clave>/
Files/resultados/reportes_v3/metricas/descargados/qa/stratio/<clave>/
```

---

## 7 · El agente

`~/.claude/agents/acta-entrega.md`. Recibe el detalle de una ejecución y
devuelve el `.docx` verificado, en cuatro pasos: arma la especificación JSON,
baja la evidencia, genera el acta, la verifica.

**El agente está desactualizado respecto a este documento.** Sigue describiendo
solo el camino de `generar.py` con reportes de comparación, y no conoce el CLI de
medición ni los controles de integridad. Antes de usarlo para un lote de
analítica hay que añadirle: el CLI `acta.py`, los controles ID/VG, el cotejo por
Rocket y la corrección de formato de §3.

---

## 8 · Reglas que no se negocian

Vienen del cliente y de errores ya cometidos.

1. **Ninguna cifra sin medir.** Si no se pudo medir, no entra.
2. **Toda diferencia lleva causa medida.** No basta con decir «desfase de tiempo»: hay que mostrar qué registros difieren. En el lote 7, los 11 registros que faltaban en `ape_repleg` resultaron ser los BP `0070062180`–`0070062190`, un bloque consecutivo por encima del máximo de Fabric, y en sentido contrario no faltaba ninguno. Eso es una causa; «desfase» no lo era.
3. **No se mencionan negativas.** El acta habla de lo que se entrega. Lo que no pasó va a un informe aparte, no al acta.
4. **Sin celdas vacías ni guiones.** Se escribe qué pasa: «no la publica el commit», «la corrida la dejó en cero», «verificado en destino».
5. **No se fija fecha de producción.** El acta aprueba el despliegue; la fecha la pone el cliente.
6. **No se comparan corridas entre sí.** ID-07, ID-08 y VG-08 miden un objeto contra su corrida anterior: eso es evolución en el tiempo, no paridad. Quedan fuera del cómputo.
7. **Se distingue «no cumple» de «no se evaluó».** Decir «1 de 21 con esquema compatible» sugiere un fallo que no existe cuando en realidad 20 no se evaluaron.
8. **El reporte de comparación lo designa el equipo.** No se sustituye por una corrida más reciente: ir a una posterior fabrica diferencias que no existen.
9. **Las salidas de fotos no llevan exigencia de conteo.** Son snapshots; el número de filas depende de cuándo se ejecutó. El histórico acumulado de fotos queda fuera de alcance.
10. **Los orquestadores se aprueban por ejecución**, no por cotejo de tablas: no escriben nada.

---

## 9 · Procedimiento para el próximo lote

0. **Abra el acta del lote 5** y téngala al lado. Es el modelo (§2 bis).
1. **Inventario.** Qué flujos entran, y cuáles ya pasaron en un acta anterior. El cruce se hace contra los pipelines reales de los dos workspaces, no contra listas sueltas. En el lote 7 se colaron 6 flujos que ya estaban en el lote 6.
2. **Tiempos.** `acta.py tiempos` sobre la lista de flujos, con la ventana de la corrida.
3. **Métricas.** `acta.py metricas` sobre las tablas de salida. Publica un reporte por tabla.
4. **Controles.** `acta.py perfil` sobre las mismas tablas. Añade ID y VG al reporte ya publicado.
5. **Cotejo.** Para las tablas que tengan contraparte en Stratio, `acta.py cotejo`. Si hay diferencia, buscar la llave y caracterizar qué registros faltan a cada lado.
6. **Decidir qué entra.** Una tabla con diferencia sin causa medida no entra en el acta.
7. **Generar** con el generador que corresponda al tipo de lote, con la estructura de §2 y el detalle del punto 8 como en §2 bis: una subsección por diferencia, con su bloque de pasos.
8. **Verificar** con `verificar.py`, y revisar cada gráfica a ojo: leyendas, etiquetas, numeración de los pies.
9. **Publicar** en `Files/resultados/actas/` **solo cuando el usuario lo pida.**

---

## 10 · Otros documentos de la misma familia

Además del acta de entrega, el proyecto produce **actas técnicas e informes**
—por ejemplo un informe de salida a producción—. Comparten la identidad visual y
los helpers de `estilo.py`, pero **no comparten la estructura de diez puntos**:
esa es del acta de entrega.

Cuando el usuario pida uno de esos documentos, **él define su alcance y sus
puntos**. No los supongas. Lo que sí se hereda:

- La paleta, el logo, los helpers de `estilo.py` y el catálogo de `graficas.py`
- La medición con `acta.py`: ninguna cifra sin medir
- Las reglas del §8, salvo la de no mencionar negativas, que es propia del acta
  de entrega: un informe técnico sí habla de lo que falla
- `verificar.py` antes de entregar

---

## 11 · Estado al 24 de septiembre de 2026

| | Universo | Aprobados | Pendientes |
|---|---|---|---|
| Ingesta · `ingestion-qa` | 103 | 78 | 25 |
| Analítica · `orchestration-qa` | 242 | 96 | 146 |

Actas firmadas: lotes 1 a 4 de ingesta (71 flujos), lote 5 mixto (6 + 11), lote 6
mixto (1 + 18), lote 7 de analítica (73). **174 flujos distintos**; la suma
simple da 180 porque el lote 7 repite 6 flujos del lote 6.

De los 146 de analítica pendientes, 21 son orquestadores, 2 son fotos y 1 es un
pipeline de prueba: quedan 122 flujos de negocio. El alcance con el que se venía
trabajando es de 143 flujos de analítica, no 242 — conviene fijar ese denominador
con el cliente antes del próximo lote, porque cambia el porcentaje de avance que
se reporta.

Pendiente de revisar: `last_partner` quedó aprobado en el lote 6, y el cotejo del
23-Sep le encontró 195.732 filas menos que Stratio (−9,70 %).
