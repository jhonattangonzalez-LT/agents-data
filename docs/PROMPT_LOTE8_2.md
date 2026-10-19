Trabajo nuevo: **L8.2** — cierre de los flujos «Pendiente» del lote 8 (hallazgos del reporte 8.1) para el **acta 8.2**. Eres el coordinador (CLAUDE.md). No retomes otros trabajos.

## Qué quiero al final
Cada flujo pendiente con su cotejo de flujo y sus cotejos de tabla en formato 2, completos y publicados, y cada hallazgo del documento respondido con dato: cerrado con causa medida, o abierto diciendo qué falta y de quién depende. El criterio de cierre de cada hallazgo es el del documento; no lo cambies. Prefiero un flujo en revisión a uno aprobado sin causa medida.

## Lee antes de empezar
- `~/Projects/reportes/Hallazgos_Lote8.1.md` — los hallazgos, flujo por flujo, con «para cerrarlo / se cierra cuando».
- `~/Projects/reportes/datos_acta_lote8.json` — acta 8 v2.1 (de ahí salen las rutas de abajo).
- `docs/PROMPTS.md`, `.claude/agents/etl-validador.md`, `.claude/agents/cotejador.md`, `pc/reportes/formato2.py` (formato 2: cada control con la medición de los dos lados; toda advertencia o falla exige una diferencia registrada con ejemplo y explicación).
- `docs/RESUMEN_SESION_2026-10-07.md` — lo aprendido ayer (rodeos y criterios).

## Ya resueltos en la revalidación del 2026-10-07 (NO los vuelvas a ejecutar)
Están aprobados con justificación, publicados y verificados. Tráelos al Markdown del lote 8.2 con sus resultados y enlaces:
- **FL-0156 `07-landing-sappscd-zsub-p-tab-ctrl`** · `sap_pscd_zsub_p_tab_ctrl` — trabajo `trabajos/L11-complemento` (ciclo v3). 9.067.667 filas en los dos lados; SHA-256 distinto solo por `NOMBRE_APO` en 30 filas (comillas); llave compuesta única en ambos. Cumple el criterio del hallazgo (SHA-256 medido, conteo igual).
- **FL-0462 `info_salarial`** · `agrupadoras_ingresos` (idéntica fila a fila, 108.225, misma huella) y `agrupadoras_variacion_salarial` (94.276 iguales; diferencias de coma flotante, ninguna material) — trabajo `trabajos/L11-resto` (v1).
Para cada uno: estado y resumen en `v4/flujos/<flujo>.json` y `v4/cotejos/<clave>.json`; enlaces en `v4/publicado.json`; también figuran en `~/Projects/reportes/Links_Lote6.2_2026-10-07.md` (info_salarial) y `Links_Lote11_2026-10-07.md` (TAB_CTRL). Responde en el Markdown cada punto del hallazgo con esas cifras.

Otros datos de ayer que te sirven (no los copies como resultado; mídelos de nuevo):
- `info_total_empresas` (FL-0463) corrió el 07-10 dentro de `orq_agrupadoras` (06:22–08:17 UTC, Completed) pero no se validó.
- `vivienda_solicitudes_01` (FL-0433): su salida `silver.vivienda_vivienda_solicitudes` es la entrada de subsidio_vivienda; ayer se midió en Fabric (versión del 2026-09-29, 299.695 filas, foto del origen al 2026-09-18) y en Stratio la Postgres `corporativo.vivienda_solicitudes` (300.290 filas, FechaEstado hasta 2026-10-05).
- `ssf_afiliados_ssf_afiliados_02` (FL-0340) también está en los hallazgos del lote 10.1 (corridas de fechas distintas, ruta SFTP de pruebas, `ZZ_TEST_MARKER`).

## Flujos a validar (17 flujos, 19 tablas)
Rutas del acta 8 v2.1. Confírmalas contra el código del flujo (`pc roles --flujo F`) antes de medir: varias se ven mal escritas (las Postgres de `poblacion_afiliada_*` terminan en `_`; las Postgres de Fabric vienen como «PG_ANALITICA_DEV_QA · analitica · …»; PLANACCION trae una ruta abfss completa). Dime cuáles corriges y por qué.

| FL | Flujo en Fabric | Flujo en Stratio | Grupo | Tabla | Ruta Stratio | Ruta Fabric | Filtro | Dependencias (acta) |
|---|---|---|---|---|---|---|---|---|
| FL-0227 | 00-landing-sts-full | 00-landing-sts-full | ingesta | sts_public_otp_codigo | `/data/prod/landingraw/sts/public/otp_codigo` | `Files/bronze/sts/public/otp_codigo` |  |  |
| FL-0227 | 00-landing-sts-full | 00-landing-sts-full | ingesta | sts_public_llave_privada | `/data/prod/landingraw/sts/public/llave_privada` | `Files/bronze/sts/public/llave_privada` |  |  |
| FL-0011 | 01-landing-feco-tpos-itementry | 01-landing-feco-tpos-itementry | ingesta | feco_sgdatos_tpos_itementry | `/data/prod/landingraw/feco/sgdatos/TPOS_ITEMENTRY` | `Files/bronze/feco/sgdatos/TPOS_ITEMENTRY` |  |  |
| FL-0013 | 01-landing-feco-tpos-user-data | 01-landing-feco-tpos-user-data | ingesta | feco_sgdatos_tpos_user_data | `/data/prod/landingraw/feco/sgdatos/TPOS_USER_DATA` | `Files/bronze/feco/sgdatos/TPOS_USER_DATA` |  |  |
| FL-0025 | 18-landing-globales-planaccion | 18-landing-globales-planaccion | ingesta | globales_default_planaccion | `/data/prod/landingraw/globales/default/PLANACCION` | `abfss://fabric-comfandi-datalake-qa@onelake.dfs.fabric.microsoft.com/lh_transversal.Lakehouse/Files/bronze/globales/default/PLANACCION` |  |  |
| FL-0433 | vivienda_solicitudes_01 | 01-vivienda-solicitudes | analitica | vivienda_vivienda_solicitudes | `/data/prod/trusted/vivienda/vivienda_solicitudes` | `Tables/silver/vivienda_vivienda_solicitudes` |  |  |
| FL-0620 | mercadeo_ventas | 01_ventas | analitica | mercadeo_transacciones_en_linea_ventas | `/data/prod/trusted/mercadeo/transacciones_en_linea/ventas` | `Tables/silver/mercadeo_transacciones_en_linea_ventas` |  |  |
| FL-0620 | mercadeo_ventas | 01_ventas | analitica | mercadeo_ventas | `mercadeo.ventas` | `PG_ANALITICA_DEV_QA · analitica · mercadeo.ventas` |  |  |
| FL-0429 | core_validaciones_pac_03 | 03-core-validaciones-pac | analitica | core_validaciones_validacion_pac | `/data/prod/trusted/core/Validaciones/validacion_pac` | `gold.core_validaciones_validacion_pac` |  |  |
| FL-0463 | info_total_empresas | 07-info-total-empresas | analitica | agrupadoras_var_agrupadoras_alt | `/data/prod/trusted/agrupadoras/var_agrupadoras_alt` | `Tables/silver/agrupadoras_var_agrupadoras_alt` |  |  |
| FL-0345 | poblacion_afiliada_empresas_13 | 13-poblacion-afiliada-empresas | analitica | ssf_poblacion_afiliada_empresas | `SSF.poblacion_afiliada_empresas_` | `Tables/gold/ssf_poblacion_afiliada_empresas` |  |  |
| FL-0346 | poblacion_afiliada_afiliados_14 | 14-poblacion-afiliada-afiliados | analitica | ssf_poblacion_afiliada_afiliados | `SSF.poblacion_afiliada_afiliados_` | `Tables/gold/ssf_poblacion_afiliada_afiliados` |  |  |
| FL-0347 | poblacion_afiliada_pacs_15 | 15-poblacion-afiliada-pacs | analitica | ssf_poblacion_afiliada_pacs | `SSF.poblacion_afiliada_pacs_` | `Tables/gold/ssf_poblacion_afiliada_pacs` |  |  |
| FL-0348 | poblacion_afiliada_fact_16 | 16-poblacion-afiliada-fact | analitica | ssf_poblacion_afiliada_fact | `SSF.poblacion_afiliada_fact` | `Tables/gold/ssf_poblacion_afiliada_fact` |  |  |
| FL-0614 | clientes_mercadeo | 02-clientes-mercadeo | analitica | mercadeo_cliente | `mercadeo.cliente` | `PG_ANALITICA_DEV_QA · analitica · mercadeo.cliente` |  |  |
| FL-0612 | recaudos | recaudos | analitica | mercadeo_recaudos | `/data/prod/trusted/mercadeo/recaudos` | `Tables/silver/mercadeo_recaudos` |  |  |
| FL-0340 | ssf_afiliados_ssf_afiliados_02 | 02-ssf-afiliados-ssf-afiliados | analitica | home_comfandi_ssf_ssf_afiliados | `/home/comfandi/SSF/SSF_AFILIADOS/ssf_afiliados.csv` | `/home/comfandi/pruebas_escritura_migracion/dev/SSF/SSF_AFILIADOS/ssf_afiliados.csv` |  |  |
| FL-0402 | tabla_base_reporte_aportes_v6 | tabla-base-reporte-aportes | analitica | public_detalle_aportes | `public.detalle_aportes` | `Tables/silver/public_detalle_aportes` |  |  |
| FL-0484 | Tabla_cosechas | tabla_cosechas | analitica | credito_archivos_planos_datamart_cosechas | `/data/prod/trusted/credito/archivos_planos_datamart/Cosechas` | `Tables/silver/credito_archivos_planos_datamart_cosechas` |  |  |

## Plan de ejecución (muéstramelo y espera mi «sí»; nada en paralelo dentro de Fabric)
1. Ingestas: sts-full, feco-tpos-itementry, feco-tpos-user-data, globales-planaccion — una por una.
2. Analítica sin dependencia en el lote: vivienda_solicitudes_01, mercadeo_ventas → recaudos (comparten el cruce de `medio_Pago`: mira el código), clientes_mercadeo, core_validaciones_pac_03, tabla_base_reporte_aportes_v6, Tabla_cosechas.
3. `poblacion_afiliada_*` (13, 14, 15, 16): los hallazgos apuntan a una **entrada compartida parcial**. Identifícala por el código, mide su fecha y conteo, ejecuta antes su productor si está atrasado (dímelo antes) y después los cuatro encadenados.
4. info_total_empresas: decide con dato si basta validar la corrida del orquestador del 07-10 o hay que volver a correr `orq_agrupadoras`; dímelo antes.
5. ssf_afiliados_ssf_afiliados_02: confirma conmigo la ruta SFTP de QA antes de medir; mide el CSV final (conteo, SHA-256, comillas, saltos de línea).
Si una dependencia ya corrió hoy y terminó Completed, no la repitas: compruébalo en Fabric y dime qué corrida tomaste. Si una entrada tiene un productor que no está en el plan, dímelo antes de ejecutar.

## Lo que exige cada hallazgo (además del nivel 2 estándar)
- Medir los dos lados con el **mismo motor y parámetros** (motor v15 con SHA-256 completo y hash por columna); varios hallazgos nacen de comparar el notebook en un lado y DuckDB en el otro.
- **ID-02 (duplicados) en los dos lados**: nada de `NO_EVALUABLE`. Si Fabric tiene duplicados y Stratio no, revisar la llave del flujo.
- **Medir después de la última corrida** y registrar la fecha de escritura de cada lado.
- **Ventanas de fecha** (feco `DAY >= 2024-01-01`, ventas y recaudos): mide la ventana de Fabric (mínimo y máximo) y cuenta Stratio dentro de ella; compara contenido (SHA-256 o sumas de control) en esa misma ventana. No apliques una ventana en silencio: preséntamela con cifras con y sin ella.
- Hallazgos concretos a responder con dato: `medio_Pago` casi vacía en ventas y recaudos; `DATA19`/`DATA20` vacías en feco user-data; `TRABAJADORES`, `VAL_CUOTA_MONETARIA_PERSONA_A_CARGO`, `Beneficiarios` 100 % vacías en poblacion_afiliada_empresas; `PAR_PERSONA_A_CARGO` en pacs; `COD_RESGUARDO`/`COD_PUB_INDIGENA` en ssf_afiliados_02; `departamento`/`municipio`/`direccion` en detalle_aportes; `nombre_empresa` en cosechas; `BP_AFILIADO`/`CATEGORIA` en clientes_mercadeo; ID-05 `otp_id` en sts (OK en Stratio, ALERTA en Fabric); planaccion 181 vs 176 filas.
- **Cambios de tipo** (ventas, poblacion_afiliada_empresas, clientes_mercadeo, cosechas): mide si hay pérdida y preséntamelos para decidir.
- Decisión: si la causa está **medida** y es de fecha o corte del insumo, ventana, representación sin pérdida o periodos no migrados → JUSTIFICADA («Decisión de QA (fecha), causa medida: …»). Defecto del flujo de Fabric (columna que llega vacía, cruce roto, duplicados nuevos) o causa no medida → PENDIENTE con lo medido y la propuesta. No justifiques un defecto. Las decisiones nuevas son mías, una por una.

## Cómo trabajar
Lo de siempre al arrancar (mejoras pendientes, `fab auth status`, VPN, cookies de Rocket: pídemelas). Avísame antes de descargar (tablas, MB, tiempo); son grandes y necesitan mi confirmación `public_detalle_aportes` (~137 M filas), `mercadeo_ventas` y `mercadeo_transacciones_en_linea_ventas` (~57 M), feco itementry (~33 M en la ventana) y `ssf_poblacion_afiliada_afiliados` (~16 M). Las de más de 100 M se miden de a una, con 2 hilos. `pc ciclo` borra la caché de los dos lados. La publicación es lenta, no colgada. Nunca mates procesos por patrón, solo por PID. Usa los agentes de `.claude/agents/` uno por paso; los agentes no deciden por mí.
No toques `trabajos/L11-complemento` ni `trabajos/L11-resto` (solo lectura, para traer lo ya resuelto).

## Qué me entregas
1. Por flujo: estado, corrida validada, comprobaciones que no cumplen y por qué; por tabla: resumen exacto y diferencias registradas.
2. `~/Projects/reportes/Lote8.2_<fecha>.md`: los 19 flujos pendientes (17 de este trabajo + TAB_CTRL e info_salarial ya resueltos), cada uno con FL, nombre en Fabric y en Stratio, estado, la respuesta a cada punto de su hallazgo con cifras, y sus enlaces (1 por flujo y 3 por tabla: cotejo, métrica Stratio, métrica Fabric). Al inicio, el resumen: cuántos quedan aprobados, cuántos en revisión y qué falta de cada uno. Mantenlo actualizado mientras se cierran los casos.
3. El acta 8.2 (.docx) solo cuando yo cierre las decisiones.
