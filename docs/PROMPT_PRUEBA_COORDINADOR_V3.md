# Prompt · prueba del coordinador v3 (un flujo, de punta a punta)

Pegar en un chat nuevo abierto en `/home/quind/Projects/pipeline-comfandi`, **con la VPN arriba y una o dos cookies
de Rocket recién puestas**. Antes de pegar, abrir http://localhost:8765 para mirar el panel durante la prueba.

---

Eres el coordinador (CLAUDE.md). Esta es una **prueba del coordinador v3** con un solo flujo pequeño. Objetivo:
recorrer código → ETL → niveles 0/1 → semáforo → descarga → nivel 2 → `diferenciar` → veredicto → `pc cierre`, y
terminar con `EXITOSOS_<T>.md` y `PENDIENTES_<T>.md` listos para el agente de actas.

Datos de la prueba (no los cambies; si falta algo, pregúntame):
- Trabajo: `prueba-v3-2026-10-19`, **de pruebas** (`--pruebas`: publica bajo `reportes_v4/_pruebas/`). Responsable del acta: yo.
- Flujo: `info_salarial_fotos` · Stratio `06-info-salarial (fotos)` · FL-0707 · analítica · orquestador `orq_agrupadoras_fotos`.
- Tablas (las mismas de L12): `agrupadoras_fotos_ingresos` y `agrupadoras_fotos_variacion_salarial`.
  Stratio HDFS `/data/prod/trusted/agrupadoras/fotos/<tabla>` con `particion: periodo_foto=202509`; Fabric `silver.agrupadoras_fotos_<tabla>`.
  Fabric genera una sola foto por corrida: se coteja contra la misma partición de Stratio.
- Versión de Stratio (Rocket) que se trae: **pregúntamela** (`pc codigo bajar` sin `--version` lista las versiones).
- **No re-ejecutes el flujo en Fabric** salvo que yo lo pida: valida la última corrida.

Reglas de esta prueba:
1. La VPN es frágil: una sola comprobación (`pc stratio vpn`) y las cookies (`pc stratio cookie`) antes de tocar Stratio;
   nunca más de 8 hilos en Rocket. Si algo de Rocket falla dos veces seguidas, **detente y avísame**; no reintentes en bucle.
2. Usa el modo resumido (ya viene en `PC_RESUMEN=1`), el grafo (`pc grafo contexto … --para <agente>`) en el prompt de
   cada agente, y lanza en un mismo mensaje lo que `pc trabajo siguiente` marque EN PARALELO (revisor-codigo junto con ETL y niveles 0/1).
3. Cada agente termina con su parte (`pc parte`). Dame cifras solo de `pc trabajo resumen` o de los partes.
4. Antes de descargar, avísame tablas, MB, vía y tiempo (`pc estimar`). En el nivel 2, el cotejador empieza por `pc diferenciar`.
5. Cada pregunta, con la tarjeta de `pc decision --nodo …`. Espera mi respuesta; no decidas por mí.
6. Publica con el publicador-reportes (`pc v4 publicar`, que en un trabajo de pruebas va a `_pruebas/`).
7. Al final: `pc cierre --trabajo prueba-v3-2026-10-19` y dime en 5 líneas qué quedó en EXITOSOS y en PENDIENTES,
   con las rutas de los dos archivos. Después lanzaré el agente de actas con un acta de prueba sobre ese EXITOSOS.

Al terminar, dime también qué viste lento, confuso o repetido en el proceso (para la siguiente mejora).
