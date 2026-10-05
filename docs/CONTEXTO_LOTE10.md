# Contexto para la validación del Lote 10 · Comfandi · Stratio → Microsoft Fabric

> **Cómo usar este documento.** Pégalo completo como primer mensaje de una ventana nueva. No hace
> falta nada más para arrancar, salvo la cookie de Rocket y la VPN, que te paso aparte. Al final hay
> una plantilla de mensaje para pedir la validación de cada flujo.

---

## 1. Qué hay que hacer

Validar los **20 flujos que quedaron pendientes del Lote 9** y cerrarlos en un **acta de entrega del
Lote 10**. Los flujos se van pasando **uno por uno**: por cada uno, medirlo en las dos plataformas,
cotejar, y dejar el resultado escrito. Al final todo se consolida en el acta.

Hay una diferencia importante con el Lote 9: **estos 20 ya se midieron una vez**, así que no se parte
de cero. De cada uno hay cifras, hallazgos y en varios casos la causa ya localizada. El trabajo es
**volver a medir y comparar contra lo anterior** para ver si los ajustes que hizo desarrollo
funcionaron.

---

## 2. Dónde está todo

| Qué | Ruta |
|---|---|
| Herramientas de medición y estado del Lote 9 | `~/Projects/validacion_lote9/` |
| Generadores de actas y reportes | `~/Projects/comfandi/cea-analytics-comfandi/qa-etl-validador-agent-v2/actas/` |
| ETL validador | `~/Projects/comfandi/cea-analytics-comfandi/qa-etl-validador-agent-v2/` |
| Notebooks de métricas de referencia | `~/Projects/metricas/auditoria_metricas_{STRATIO,FABRIC}_v17.ipynb` |
| Actas y reportes entregados | `~/Projects/reportes/` |
| Inventario con los códigos FL | `.../qa-etl-validador-agent-v2/inventario/matriz.json` |

**Credenciales** (en archivos, `chmod 600`, nunca imprimirlas ni subirlas a ningún sitio):

- `~/Projects/.rocket_cookie` — cookie de Rocket para bajar de HDFS. **Caduca; el usuario la renueva.**
- `~/Projects/.stratio_conn.json` — Postgres y SFTP de Stratio. **Solo alcanzables por VPN.**
- `~/Projects/.azure_metricas_sas` — SAS del bucket de métricas.

**Comprobar la VPN antes de empezar:**
```bash
H=$(python -c "import json;print(json.load(open('/home/quind/Projects/.stratio_conn.json'))['postgres']['host'])")
timeout 15 bash -c "</dev/tcp/$H/5432" && echo "VPN ok"
```

---

## 3. Estado del Lote 9, para no repetir trabajo

**51 flujos entregados** — 14 de ingesta, 29 de analítica, 8 orquestadores. Están en el acta
`~/Projects/reportes/Acta_Entrega_Flujos_Lote9_2026-09-26.docx` (versión 1.7) y **no hay que volver a
tocarlos**. El listado completo está en `estado/listado_lote9_lote10.json`, clave `aprobados`.

**20 pendientes**, que son el alcance del Lote 10. Están en el mismo archivo, clave `pendientes`.

---

## 4. Los 20 pendientes, con lo que ya sabemos de cada uno

Formato: **flujo · código FL** · objetos con `filas Stratio → filas Fabric` y lo que se midió.

### Ingesta · 2

**`zsub_c011_prescr` · FL-0250**
- `sap_pscd_zsub_c011_prescr` · 546.348 → 1.092.696 (el doble exacto)
- **YA CORREGIDO Y VERIFICADO.** El sink estaba en `Append`; se cambió a `Overwrite` y al reejecutar
  quedó en 546.348 filas, 546.348 distintas, ratio 1,000000. Origen: CSV.gz en el SFTP
  `/home/comfandi/01_cargas_qlik/pscd/ZSUB_C011_PRESCR`. Destino: `silver.sap_pscd_ZSUB_C011_PRESCR`.
- **Qué falta:** validarlo formalmente con el motor v15 y meterlo al acta 10.

**`15-landing-sappscd-dfkkop` · FL-0133**
- `servicios_dfkkop` · Postgres `Servicios.DFKKOP` en los dos lados · 345.362.999 filas y 108 GB en Fabric
- **SIGUE SIN CORREGIR.** Duplica la ventana de recarga. El flujo tiene un `IfCondition` sobre el
  parámetro `reprocess_flag`, cuyo **valor por defecto es `"false"`**, y esa rama ejecuta
  `DFKKOP_To_Postgres_Append`: inserta sin borrar. La rama `true` sí hace lo correcto
  (`TRUNCATE` del staging y un script que borra por `OPBEL` antes de insertar).
- Medido por día de `BUDAT` sobre la llave primaria `(MANDT, OPBEL, OPUPW, OPUPK, OPUPZ)`:
  histórico limpio (2016-06-25 coincide exacto), ventana reciente al doble
  (2026-09-01 ×1,905 · 2026-09-15 ×1,891 · 2026-09-23 ×1,991).
- **Arreglo:** poner `reprocess_flag` en `true` por defecto, o que la rama `false` borre su ventana.
- **Ojo:** comparte `Servicios.DFKKOP` con `06-trusted-sappscd-dfkkop`. **No pueden correr en el mismo horario.**

### Analítica · 18

**`ssf_afiliados_ssf_afiliados_02` · FL-0340** — el caso más avanzado, ver la sección 5.

**`ssf_afiliados_ssf_pacs_03` · FL-0341**
- `ssf_pacs` 571.783 → 423.443 · `ssf_sftp_ssf_pac_csv` 568.604 → 423.443 · `ssf_errores_pacs` 0 → 0
- **Dos problemas distintos.** (1) Pérdida pareja del 26% en todas las categorías, así que no es un
  filtro de negocio; la fuente `silver.afiliados_pacs` tiene 4,53 M en QA contra 5,37 M en HDFS.
  (2) **Dos columnas llegan con los valores mal**: `PAR_PERSONA_A_CARGO` pierde todos sus valores
  (en Stratio toma 7, en Fabric solo queda el `4` y aparecen 392.783 nulos que no existen en origen) y
  `TIP_CUOTA_MONETARIA_PERSONA_A_CARGO` se remapea (el `1`, el más frecuente con 290.596, desaparece;
  el `3` pasa de 9.374 a 229.458).
- **`PAR_PERSONA_A_CARGO` falla en tres sitios distintos de la familia SSF**: aquí al 100%, en
  `ssf_pac_historico` al 92,78%, y en `gold.afiliados_ssf_pacs_historico` pierde 244.443 filas. Conviene
  tratarlo como un solo problema de mapeo, no como tres incidentes.

**`td_fosfec_estadoPostulaciones_05` · FL-0407** — el más grave del lote
- `cliente_estadopostulaciones` 77.241 → 48.573 · `servicios_postulaciones_himalia` 77.241 → 48.573 ·
  `corporativo_fosfec_novedades` 4.952 → 4.894
- 37% menos filas y **30 de 57 columnas llegan 100% NULAS** teniendo dato en Stratio
  (`tipo_de_documento`, `numero_de_telefono`, `ciudad`, `centro_recepcion`…), más `Nombres` y
  `Apellidos` colapsados a cadena vacía. Verificado que **no es un problema de lectura**: en la misma
  fila la pipeline devuelve `id` y `numero_de_documento` con dato y esas 30 en NULL.
- **Además no ejecuta**: ver la sección 6, causa `placeholder`.

**`core_validaciones_afiliados_02` · FL-0428**
- `corporativo_validacion_afiliado` 640.694 → 638.060
- **4 banderas de validación llegan constantes en 0**: `ValSexoCRM`, `EsTrabajador`, `EsEmpresa`,
  `ValEsEmpresa`. Que las cuatro colapsen a la vez apunta al paso de validación. Y `SalarioCRM` pasa de
  0,03% de nulos a 18,39%: 119.741 filas pierden el salario de CRM.

**`core_validaciones_validador_subsidio_06b` · FL-0646**
- `corporativo_log_liquidacion_subsidio` 32.021.042 → 31.601.118
- `Sueldo` y `Discapacidad` llegan **100% nulas**. Y el bloque del PAC (`BPPac`, `Parentesco`,
  `FechaFinPac`, `FechaInicioPac`, `FechaNacimientoPac`) pasa de 11,89% a 29,71% de nulos: unas
  **5,6 millones de filas** sin el PAC, muy por encima de las 419.924 de diferencia de conteo.

**`envios` · sin código FL** y **`reenvios` · sin código FL**
- 7 tablas cada uno. **6 de 7 llegan vacías** a Fabric teniendo dato en Stratio
  (`sat.envio_inicio_relacion_laboral` 1.343.050 → 0, `fin_relacion_laboral` 2.055.520 → 0, etc.).
- **No es código: es un bloqueo de datos.** Las 7 tablas `sat.respuesta_*` de la Postgres de QA no las
  escribe ningún pipeline del workspace: vienen del sistema SAT. Se comprobó repoblando 3 de las
  `sat.reporte_*` y reejecutando: siguieron dando 0.
- **Acción:** sembrar las `sat.respuesta_*` en QA. Hasta entonces no hay nada que cotejar.

**`mdt_final` · FL-0494** y **`predicciones_k_means` · FL-0497**
- `credito_mdt_final` 127.877 → **184** · `credito_predicciones_kmeans` 62.992 → **184**
- El notebook entra con las filas de Stratio y escribe 184. `predicciones_k_means` consume la salida de
  `mdt_final`, así que es la misma causa. Revisar el join o filtro final.

**`trusted_datamart_credito_niveles_fact` · FL-0490**
- `credito_tablas_finales_niveles_historico` 2.460.610 → **760**
- Faltan **~380 columnas** pivoteadas por línea de crédito (`saldo_capital_*`, `interes_cte_*`,
  `abonos_*`, `fec_vencto_*`, `calificacion_*` por NORMALIZACION, LIBRANZA, HIPOTECARIO…). No es
  comparable con columnas nulas: aquí falta el cuerpo de la tabla.
- **Aviso de medición:** el esquema de Stratio es inconsistente entre particiones en las 5 columnas
  `fec_vencto_*` (entero en unas, fecha en otras). Hay que leer con `cast_varchar` por archivo.

**`trusted_datarmat_credito_cartera_fact` · FL-0489**
- `credito_tablas_finales_cartera` 52.215.849 → 50.294.592 (3,68%) · 56 de 58 columnas con perfil
  idéntico · el corte lo explica `periodo`. Solo `pk_empresa` excede la cota: 2.217.514 de cambio contra
  1.921.257 de delta.
- El objeto hermano `credito_tablas_finales_cartera_cartera_desembolso` ya quedó aprobado.

**`ssf_facts_20` · FL-0441**
- `ssf_pa_facts` 68.133.572 → 592.937.958
- La tabla **crece por append** en cada corrida en vez de reemplazar el periodo. Se comprobó con un
  experimento controlado: backup del `_delta_log`, dos corridas, y la tabla creció.

**`reporte_cuota_consolidado_ssf` · FL-0388**
- `corporativo_cuotas_pacs_consolidado_ssf` 47.205.608 → 10.887.624 (77% menos)

**`periodo_contable_cierre` · FL-0400**
- `corporativo_periodo_cierre_prueba` 7.925.648 → 8.196.274 (Fabric escribe **más**)
- El hermano `corporativo_aporte_reportes_pivot_dian` ya quedó aprobado.

**`tableros_web_service_16` · FL-0364**
- `subsidios_informeexperiencia` 31.163 → 77.695 · `subsidios_informeexperienciahistorico` 31.918 → 79.730
- Fabric escribe **más del doble**, y hay columnas que quedan vacías o colapsadas. Además en Delta
  faltan columnas: `CodigoInterno`, `Categoria`, `Sexo`, `BP_Endosante`.

**Los tres que no ejecutan** — ver sección 6:
**`estado_postulaciones_fovis_33` · FL-0374** · sus 3 objetos ya salen aprobados por dato
**`ra2_usuarios_sus_18` · FL-0417** · su único objeto ya sale aprobado por dato (36 → 36)
**`sabana_sub_especie_dinamico` · FL-0375** · sus 4 objetos ya salen aprobados por dato

---

## 5. El caso `ssf_afiliados_ssf_afiliados_02` · cómo hay que declararlo

Este flujo **se aprueba**, con las diferencias declaradas. Hay tres cosas distintas y conviene no
mezclarlas:

**a) La ejecución es correcta.** Se ejecutó el 2026-09-28 y terminó `Completed` en 9,1 minutos.

**b) Diferencia de datos, real y medida.** Hoy escribe **657.460** filas contra **668.713** de Stratio:
**98,32%**, faltan **11.253** (1,68%). Dos corridas seguidas dieron el mismo número, así que el flujo es
determinista.
- La causa del déficit grande estaba **en la fuente, no en la lógica**: `silver.afiliados_trabajadores`
  tenía 5.166.859 filas contra 5.861.223 del HDFS trusted. Al repararla, el flujo pasó de 539.740 (80,7%)
  a 657.460 (98,3%).
- **Esto lo va a pisar su productor.** `silver.afiliados_trabajadores` la escribe
  `core/silver/tableros_afiliados_trabajadores_03` con `createOrReplace`. En su próxima corrida vuelve el
  déficit. **El arreglo de fondo está en ese productor**, y es transversal: pasa igual con
  `silver.afiliados_pacs` y con los tres históricos.
- Las 11.253 que faltan: hipótesis no comprobada de desfase entre las tres fuentes que cruza con
  `left join` — `afiliados_trabajadores` es la foto recién bajada, mientras `afiliados_empresas` y
  `subsidios_subsidio` son las de QA del 26 y el 23 de septiembre.

**c) Diferencia de código: campos extra.** Fabric tiene **5 columnas que Stratio no tiene**:
`BP_EMPRESA`, `FECHA_INICIO`, `FECHA_FIN`, `ID_GRUPO_FAMILIAR` y **`ZZ_TEST_MARKER`**.
- Esto se declara como **«Campos extra en flujos»**, que es como se comunicó por correo.
- **`ZZ_TEST_MARKER` es una columna de prueba con el valor `test123` en el 100% de las filas, y sigue
  presente al 2026-09-28.** Hay que eliminarla antes de producción. Verificar en cada corrida.
- Dato útil: 657.447 `BP_AFILIADO` distintos sobre 657.460 filas, o sea **13 sobrantes**. Prácticamente
  un afiliado por fila, así que **el `DISTINCT` no está inflando el conteo** y no hay que tocarlo.

**Cómo redactarlo en el acta:** ejecución correcta · diferencia de datos del 1,68% con su causa en la
fuente y el productor que la pisa · campos extra declarados, con `ZZ_TEST_MARKER` señalada para retirar.

---

## 6. Los tres flujos que no ejecutan, y su causa común

`estado_postulaciones_fovis_33`, `ra2_usuarios_sus_18`, `sabana_sub_especie_dinamico` y también
`td_fosfec_estadoPostulaciones_05` fallan con `Spark_System_OLC_BadRequestOperationFailed`.

**No es defecto del flujo ni del código.** Los cuatro reciben al menos un argumento de **ruta de datos**
cuyo valor en la Variable Library `vl_core` es la cadena literal `placeholder`. El error completo de
Fabric lo dice: *«A OneLake ABFS operation failed with HTTP 400 Bad Request … Verify whether the
requested OneLake path and operation are supported»*. El job abre una ruta que no es una ruta.

Se probó ejecutando cada uno con su dependencia delante y en `Completed` (`keycloak_prod`,
`proteco-core-full-ingesta`): los tres volvieron a fallar igual.

**El dato ya existe en OneLake. Son 6 valores por poner en `vl_core`:**

| Variable | Valor que debe tener | Dato que ya hay |
|---|---|---|
| `vl_core_keycloak_role_path` | `Files/bronze/keycloak-prod/keycloak_role` | 30 KB |
| `vl_core_keycloak_user_role_mapping_path` | `Files/bronze/keycloak-prod/user_role_mapping` | 42 MB |
| `vl_core_fovis_comments_path` | `Files/bronze/fovis/postulations_commentspostulation` | 11 MB |
| `vl_core_fovis_soaplog_path` | `Files/bronze/fovis/soap_soaplog` | 317 MB |
| `vl_core_parquet_sub_especie_status_path` | `Files/bronze/proteo_core_sub_especie/Status` | 2 KB |
| `vl_core_parquet_sub_especie_requests_audit_path` | `Files/bronze/proteo_core_sub_especie/RequestsAudit` | 50 MB |

Los `placeholder` de `sftp-host` y `postgres-sp-client-id` **no se tocan**: los reciben muchos flujos
que corren bien.

**Correlación:** de los 71 flujos del Lote 9, los únicos que reciben una ruta en `placeholder` son
exactamente esos 4. Ninguno que corre bien recibe una.

---

## 7. Las herramientas, y cómo se usa cada una

### 7.1 Motor de medición v15 · `~/Projects/validacion_lote9/`

Reproduce la especificación de los notebooks `auditoria_metricas_*_v17` en DuckDB, mucho más rápido que
correr los notebooks. **No hay que ejecutar los notebooks**: se usan como referencia del formato.

| Archivo | Para qué |
|---|---|
| `armar_plan.py` | declara los objetos: clave, flujo, grupo, ruta de Stratio y de Fabric. Genera `plan.json` |
| `fuentes.py` | baja de HDFS por Rocket, de OneLake, de Postgres y del SFTP. Limpia la caché de obsoletos |
| `motor.py` | mide un lado: hash canónico, hash por columna, perfil de 23-34 métricas, ID/VG/CP |
| `motor_pg.py` | mide **dentro** de la Postgres de Stratio, sin extraer el dato (la VPN da <1 MB/s) |
| `ejecutar.py` | orquesta: baja, mide, coteja y publica. Estado por objeto, paralelo, reanudable |
| `cotejo.py` | veredicto: exigencias, justificaciones, CP/ID/VG, contrato |
| `cotejo_perfil.py` | **cotejo de valor columna a columna** sin volver a leer las fuentes |
| `resumen.py` | consolida el lote, genera `LOTE9.md` y publica. `--publicar` sube a OneLake y al bucket |
| `reportes_equipo.py` | los dos reportes cortos para integración y analítica |
| `publicar.py` | sube a OneLake y al bucket |
| `fabpg.py` | lee la Postgres de Fabric por la pipeline de QA |
| `ejecutar_paso.py` | ejecuta un flujo con sus dependencias delante y guarda el error completo |
| `anexo_rutas.py` | inventario de todas las rutas publicadas |

**Criterios de aprobación**, que no hay que cambiar:
- **Ingesta**: paridad exacta — mismas filas y mismo `hash_dataset`.
- **Analítica**: pruebas de integración — contrato de columnas y tipos, VG sin fallas, ID sin
  regresiones. **Las filas son informativas**, no se exige igualdad.
- **Orquestadores**: solo ejecución.

### 7.2 Las métricas · qué produce cada medición y cómo se lee

Esto es el corazón de la validación, así que conviene tenerlo claro antes de medir nada. Por cada objeto
y por cada plataforma se produce **un reporte JSON con la misma estructura en los dos lados**, y luego un
tercer archivo que los enfrenta.

**Nombres de archivo**, que es como se reconocen:
- `stratio_<clave>_<fecha>_<run8>_v<n>.json` — medición del origen
- `fabric_<clave>_<fecha>_<run8>_v<n>.json` — medición del destino
- `metrica_<clave>_<fecha>_<run8>_v<n>.json` — el cotejo de los dos
- `perfil_<clave>_<fecha>_<hhmm>.json` — el cotejo de valor columna a columna

**Las 17 secciones del reporte:** `version_reporte`, `ejecucion`, `objeto`, `errores`, `perfilado`,
`conteos`, `esquema`, `hash`, `desglose_particiones`, `metricas_columnas`, `valores_frecuentes`,
`muestra`, `validaciones`, `comparacion_corrida_previa`, `puntos_control`, `estado_general`,
`contrato_propuesto`.

**La huella del dato** (sección `hash`), que es lo que decide la paridad en ingesta:
- Fila: `sha256(concat_ws(chr(1), columnas_canónicas_en_ORDEN_FÍSICO))`
- Nulo: centinela `chr(0) || 'NULL' || chr(0)`, para que un nulo no se confunda con una cadena vacía
- Agregado **independiente del orden de las filas**: se suman 4 rebanadas de 60 bits del hash de fila,
  tomadas en las posiciones 1, 16, 31 y 46 con ancho 15
- `hash_dataset = sha256("SHA256-CANON-v1|" + filas + "|" + s1 + "|" + s2 + "|" + s3 + "|" + s4)`
- Por columna: `sha256("SHA256-COL-v2|" + filas + "|" + suma)`
- De conjunto de columnas: `sha256("SHA256-SET-v1|" + ordenadas)`
- De esquema: tres hashes —estricto, de tipos y de nombres— sobre los campos ordenados por nombre

**El perfil por columna** (`metricas_columnas`): **23 campos** en la medición por SQL y hasta 34 en la
completa. Los que se usan para cotejar: `no_nulos`, `nulos`, `pct_nulos`, `valores_distintos` con su
método, `es_constante`, `minimo`, `maximo`, `longitud_minima`, `longitud_maxima`, `cadenas_vacias`,
`suma_exacta`, `ceros`, `negativos`, `valor_minimo_lexicografico`, `valor_maximo_lexicografico`.

**Los controles**, que van en el cotejo:
- **ID-01 a ID-07** — integridad y conteos: filas > 0, duplicados de fila completa, columnas 100% nulas…
- **VG-01 a VG-08** — esquema y metadata: nombres, tipos, gobierno del dato
- **CP-01 a CP-05** — puntos de control: conteo, esquema y tipos, checksum, muestreo, reejecución por fecha

Un control **no se compara en absoluto, se compara entre lados**: lo que importa es si un control que
estaba OK en Stratio **empeoró** en Fabric. Eso es una *regresión*, y es lo que bloquea la aprobación en
analítica. Un control en ERROR a los dos lados es una característica heredada del contrato de Stratio, no
un defecto de la migración, y se declara como tal.

**Tres arreglos pendientes en los notebooks** `auditoria_metricas_*`, que están igual en v15, v16 y v17.
Si los aplicas, hazlo sobre v17 y déjalo como v18:

1. **El HLL enmascara su error.** `filas_duplicadas_estimadas` se calcula con
   `max(0, filas_hasheadas - filas_distintas)`, y ese recorte convierte un resultado imposible en un
   "0 duplicados" que parece medido. Debe emitir `null` con motivo `ESTIMADOR_SOBREPASA_EL_CONTEO` cuando
   `distintas > filas`, y publicar el margen de error del estimador.
2. **Mín y máx de booleanos no se calculan**, así que un lado queda en null y no hay nada que comparar.
   Castear a entero para el agregado.
3. **Mín y máx de texto no son comparables entre plataformas** por la colación. Marcar
   `extremos_comparables: false` en las columnas de texto, para que ningún comparador los tome como
   evidencia.

### 7.3 ETL validador · `.../qa-etl-validador-agent-v2/`

Sirve para **entender el flujo antes de medirlo**: qué entradas declara, qué salidas promete, y si el
contrato se cumple. Complementa la medición, no la sustituye.

```bash
cd ~/Projects/comfandi/cea-analytics-comfandi/qa-etl-validador-agent-v2
python3 cli.py --listar --flujo ""        # inventario de flujos del repo
python3 cli.py --plan                     # qué reglas se correrían, sin correr nada
python3 cli.py --fase transform           # transform() sobre fixtures, en memoria
python3 cli.py --fase job                 # el job completo contra fuentes reales (solo en Fabric)
```

Cinco pruebas, en cadena de cortocircuitos:
`T2 metadata → T1 inputs → ejecutar → T3 outputs → T4 función → reconciliación → T5 veredicto`

- **T2 metadata** — ¿el flujo está bien declarado? No necesita nada.
- **T1 inputs** — ¿tiene todo lo que necesita para arrancar? Aquí se ven las rutas de entrada, que es
  donde saltaron los `placeholder`.
- **T3 outputs** — ¿lo que produjo tiene la forma que promete el contrato?
- **T4 función** — ¿hace lo que el contrato dice?
- **Reconciliación** — ¿produjo lo mismo que la corrida anterior? **Esto es lo más útil para el Lote 10**,
  porque el trabajo es precisamente comparar contra lo ya medido.

Si se pide `transform` o `job` sin PySpark, la fase se degrada a `contrato` y las pruebas sobre datos
salen `OMITIDO`, **nunca OK**.

### 7.4 La pipeline de QA para leer la Postgres de Fabric

`qa_validacion_lectura_postgres` en el workspace `datalake-qa` (id `4c510924-3f39-42c2-9912-1bb7bb637d58`).
La creó el equipo de QA, **se puede editar**. Ejecuta una consulta y deja el resultado en parquet.
Se usa desde `fabpg.py`.

---

## 8. Trampas conocidas · lee esto antes de medir

**8.1 El corte de ~140 s es del socket TCP, no del `queryTimeout`.** Se subió el `queryTimeout` de la
pipeline de 2 minutos a 2 horas y **el corte no cambió**: la conexión se cae igual con
`Npgsql: Exception while reading from stream` / `SocketException`, porque el servidor calcula sin enviar
datos. **Pasa igual del lado de Stratio**: una consulta de agregados sobre `Servicios.DFKKOP` murió con
`psycopg2: SSL connection has been closed unexpectedly` tras 1 h 09 min.
→ **Una tabla de cientos de millones de filas no se perfila en una sola consulta en ninguna de las dos
plataformas.** Calibración medida: en Fabric un mes con `count(*)` cabe en 70-84 s, un día en 42 s, y un
mes con `count(distinct)` **no cabe**; en Stratio un día con `GROUP BY` sale en 6-36 s. **La unidad de
trabajo es el día, en paralelo.**

**8.2 El conteo aproximado de distintas (HLL) no prueba duplicación.** En DFKKOP, Stratio devolvió
362.325.256 filas distintas sobre 342.780.202 filas: imposible, +5,7% de error. El notebook recorta con
`max(0, filas - distintas)` y eso convierte el resultado imposible en un **"0 duplicados" que parece
medido**. Con eso otra sesión concluyó que Fabric duplicaba, y no era cierto.
→ **Si `filas_distintas_metodo` dice `APROXIMADO_HLL`, no afirmes duplicación.** La señal de que el
estimador se fue: distintas > filas. Para duplicación real, usar `GROUP BY llave HAVING count(*) > 1`
sobre la llave de negocio, por día.

**8.3 Mín y máx de texto no son comparables entre plataformas.** PostgreSQL ordena con las reglas del
locale —ignora puntuación, acentos y caja— y DuckDB ordena por bytes. `'ZYNKO'` contra `'ÁVILA'` no
prueba nada. `cotejo_perfil.py` lo resuelve con una prueba de doble ordenación: solo cuenta como
diferencia si **las dos** ordenaciones coinciden en cuál es mayor.

**8.4 El `information_schema` de Fabric llega con `NaN` donde va nulo**, porque viaja en parquet. Como
`NaN != NaN`, `text` se compara contra `text` y sale como cambio de tipo. En una tabla inflaba **37
diferencias falsas**. Ya está corregido en `cotejo.py` con `_num()`.

**8.5 La actividad Copy escribe `date` como `timestamp`** en el parquet intermedio. Al cotejar hay que
castear al tipo declarado en `information_schema`, o sale un falso cambio de tipo y de hash.

**8.6 Rocket es frágil y lento.** ~10 s de latencia por archivo, así que el rendimiento sale de los
hilos: 4 hilos 0,55 MB/s · 16 hilos 1,43 · 32 hilos 2,76. **No paralelizar entre objetos**, sino dentro
del objeto. Y **la caché se ensucia**: Stratio reescribe particiones intradía con UUID nuevos, así que
hay que borrar los obsoletos antes de medir (`_limpiar_obsoletos` en `fuentes.py`).

**8.7 Las definiciones de `fabric_defs/` son una foto.** Para afirmar cómo está configurado un pipeline
**hoy**, hay que consultarlo contra Fabric con `getDefinition`, no contra la caché. Me pasó con
`zsub_c011_prescr`: la caché decía `Append` y el pipeline ya estaba en `Overwrite`.

**8.8 Sinks en `Append` y ventanas de recarga.** Antes de ejecutar un flujo, revisar el sink:
`tableActionOption` en los Delta y `preCopyScript` en los Postgres. Si el `ddl_*` hace `TRUNCATE`, es
seguro. Si no hay ni `TRUNCATE` ni `preCopyScript`, **ejecutar duplica**.

**8.9 Las tablas trusted de QA están sistemáticamente por debajo de HDFS.** Confirmado en
`silver.afiliados_trabajadores` (5,17 M contra 5,86 M), `silver.afiliados_pacs` (4,53 M contra 5,37 M) y
los tres históricos. **La raíz está en sus productores**, no en los flujos que las consumen. Antes de
culpar a un flujo de analítica, medir su fuente contra HDFS.

---

## 9. El proceso, flujo por flujo

Por cada flujo que el usuario pase:

1. **Entender el flujo.** Leer su definición actual con `getDefinition` (no la caché) y, si aporta,
   pasarle el ETL validador para ver entradas, salidas y contrato. Anotar el sink y el modo de escritura.
2. **Revisar el historial.** Buscar el flujo en la sección 4 de este documento y en
   `~/Projects/validacion_lote9/estado/hallazgos.json`. **Nunca partir de cero si ya hay medición.**
3. **Medir la fuente si el flujo es de analítica y perdió filas.** Comparar la tabla `silver.*` que
   consume contra su equivalente en HDFS. Es la causa más frecuente (trampa 8.9).
4. **Ejecutar el flujo**, solo después de verificar el sink (trampa 8.8). Con `ejecutar_paso.py`, que
   corre las dependencias delante y guarda el error completo.
5. **Medir los dos lados** con el motor v15: `armar_plan.py` para declarar el objeto y `ejecutar.py`
   para medir, cotejar y publicar.
6. **Cotejar el valor columna a columna** con `cotejo_perfil.py`.
7. **Comparar contra lo anterior**: ¿mejoró, empeoró, igual? Esa comparación es el entregable del Lote 10.
8. **Escribir el resultado en `LOTE10.md`** con su check, sus rutas y sus cifras (ver sección 10).
9. **Publicar** con `resumen.py --publicar`.

---

## 10. `LOTE10.md` · el registro que alimenta el acta

Por cada flujo, un bloque con esta forma. La idea es que al final el acta se arme de aquí sin tener que
reconstruir nada.

```markdown
## <flujo> · <FL-0XXX> · <ingesta|analitica|orquestadores>

- [ ] Definición leída desde Fabric · sink: <tableActionOption / preCopyScript>
- [ ] Fuente verificada contra HDFS · <tabla silver>: <filas QA> contra <filas HDFS>
- [ ] Flujo ejecutado · <estado> · <duración>
- [ ] Medido en las dos plataformas · Stratio <filas> → Fabric <filas>
- [ ] Cotejo de plataformas · <veredicto> · CP <n>% ID <n>% VG <n>%
- [ ] Cotejo de valor columna a columna · <n> de <n> columnas con perfil idéntico
- [ ] Publicado en OneLake y bucket

**Comparación contra el Lote 9:** <antes> → <ahora> · <mejoró / igual / empeoró>

**Diferencias y su justificación:** <cada diferencia con la cifra que la sostiene>

**Rutas:**
- Reporte de Stratio: `Files/resultados/reportes_v3/metricas/descargados/qa/stratio/<clave>/`
- Reporte de Fabric: `Files/resultados/reportes_v3/metricas/descargados/qa/fabric/<clave>/`
- Cotejo de plataformas: `Files/resultados/reportes_v3/metricas/cotejos/<clave>/`
- Cotejo de valor: `Files/resultados/reportes_v3/metricas/cotejos/<clave>/perfil_*.json`
- Cotejo del flujo: `Files/resultados/reportes_v3/flujos/cotejos/<flujo>/`

**Veredicto:** <APROBADO | APROBADO_CON_JUSTIFICACION | REVISAR> · <motivo en una línea>
```

---

## 11. El acta del Lote 10

La genera el agente `acta-entrega`, que ya tiene los generadores. **Molde: el Lote 9 en su versión 1.7**,
`~/Projects/reportes/Acta_Entrega_Flujos_Lote9_2026-09-26.docx`.

Reglas que costó fijar en el Lote 9 y que hay que respetar:

- **Sin campos vacíos, sin números incompletos, sin guiones sueltos.** Si un dato no aplica, decir por qué.
- **Toda diferencia justificada con la cifra que la sostiene.** No vale "hay una diferencia menor".
- **El acta habla solo de los flujos que entrega.** Nada de flujos fallidos ni devueltos: eso va en los
  dos reportes técnicos, uno de integración y uno de analítica, cortos y sin portada.
- **El acta no lleva la línea de tiempo general del trabajo** (que la prueba arrancó tal día y cerró tal
  otro). Eso va solo en el correo. **Sí lleva la duración de ejecución por flujo.**
- **El punto 9 tiene que enlazar TODA la evidencia publicada**: reporte de Stratio, reporte de Fabric,
  cotejo de plataformas y cotejo de valor por objeto, el cotejo consolidado **por flujo**, y todos los
  documentos del lote. `verificar.py` ahora falla si algo publicado queda sin citar — en los lotes 6, 7,
  8 y 9 faltaban el cotejo por flujo y el cotejo de valor.
- **Entregar también un anexo de rutas en Word**, documento aparte, solo enlaces.
- **Decimales con coma, miles con punto.**

---

## 12. Plantilla para pedir cada flujo

> Valida el flujo **`<nombre>`** para el Lote 10.
> Está en la sección 4 del contexto con su historial: revísalo antes de medir.
> Sigue el proceso de la sección 9 y deja el bloque en `LOTE10.md` con el formato de la sección 10.
> Cuando termines dime el veredicto, la comparación contra el Lote 9, y si hay algo que reportar.

---

## 13. Lo que queda abierto de otros equipos

No bloquea la validación, pero conviene tenerlo presente porque explica varios pendientes:

1. **Los 6 valores de `vl_core`** — desbloquean 4 flujos de una vez.
2. **Los dos sinks que duplican** — `reprocess_flag` en `15-landing-sappscd-dfkkop`.
3. **Las tablas trusted de QA por debajo de HDFS** — el arreglo está en sus productores, que usan
   `createOrReplace`.
4. **`ZZ_TEST_MARKER`** en `SSF.AFILIADOS`, con `test123` en el 100% de las filas. Retirar antes de producción.
5. **Las 7 tablas `sat.respuesta_*`** sin sembrar en QA, que bloquean `envios` y `reenvios`.
6. **`silver.mercadeo_medios_pago.valor` declarada `decimal(8,0)`** — sin decimales y con tope
   99.999.999, cuando el máximo medido ya es 99.721.000. Ampliar el tipo.
7. **El acta del Lote 8** declara 40 flujos cuando fueron 38: otro agente le añadió
   `06-landing-sappscd-zsub-p-det-apo` y `06-trusted-sappscd-dfkkop` sin subir la versión.
8. **`~/Projects/reportes/Acta_Entrega_Flujos_Lote9_2026-09-25.docx`** — un acta del mismo lote con otra
   fecha en el nombre, que no generó este equipo. Decidir si se retira.
