# Prompt · prueba del coordinador v3 · homologacion_correos (lote 6)

Pegar en un chat nuevo abierto en `/home/quind/Projects/pipeline-comfandi`, con la VPN arriba.

---

Eres el coordinador (CLAUDE.md). Prueba del coordinador v3 con UN flujo, de punta a punta.

Trabajo: prueba-v3-homologacion-correos (créalo con --pruebas; responsable del acta: yo).
Flujo: homologacion_correos · Stratio «homologacion_correos» (Rocket, grupo /home/contactabilidad/productivo/landing/raw-files)
· FL-0574 · analítica · lote 6.
- Fabric: salida silver.contactabilidad_homologacion_correos (overwrite); entrada
  Files/bronze/raw-files/contactabilidad/homologacion_correos/homologacion_correos.parquet.
- Stratio: la ruta de salida no la tengo; sácala del código del workflow en Rocket (revisor-codigo) y confírmamela
  antes de medir. La versión de Rocket que se trae: pregúntamela (lista las versiones).

Antes de tocar Stratio: la VPN ya está arriba (ya se comprobó; NO la vuelvas a probar en bucle). Las cookies vencieron:
pídeme 1 o 2 nuevas y guárdalas sin imprimirlas. Si algo de Rocket falla dos veces seguidas, detente y avísame.

Cómo quiero verlo:
1. Arranca el panel (`python -m pc panel --asegurar`), preséntate con tu ave y dame el enlace del panel.
2. Pregúntame si ejecuto el flujo en Fabric o si valido su última corrida.
3. Trabaja en carriles paralelos: revisión de código + bajar y medir Stratio por adelantado mientras el ETL de Fabric
   corre o se valida; después Fabric, nivel 2, `pc diferenciar` y cotejo.
4. Avísame antes de cada descarga (tablas, MB, vía, tiempo).
5. Cada agente cierra con su parte; dame cifras solo de `pc trabajo resumen` o de los partes.
6. Decisiones con la herramienta de preguntas (tarjeta corta, agrupadas por causa); no decidas por mí.
7. Publica con el publicador (va a _pruebas/).
8. Al final, `pc cierre` y dime en 5 líneas qué quedó en EXITOSOS y en PENDIENTES, con sus rutas, y qué mensajes quedaron
   en el buzón. Después lanzaré el agente de actas con un acta de prueba sobre ese EXITOSOS.
Al terminar, dime qué viste lento, confuso o repetido.
