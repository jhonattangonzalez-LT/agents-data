> **Reemplazada por `REPORTES_V4.md`** (2026-10-04): de esta propuesta quedaron solo cinco archivos. Se conserva como antecedente.

# Propuesta de estructuras · JSON publicados, bitácora de agentes y acta

Estado: **PROPUESTA** (2026-10-04). Nada de esto está implementado como formato definitivo: hoy
`pc/reportes/publicar.py` publica en una ruta provisional. Cuando se apruebe, se implementa y
`config/pipeline.json → publicacion.formato_definitivo` pasa a `true`.

Tres principios:
1. **Un sobre común** para todo JSON: cualquiera (persona o agente) sabe qué es, de qué lote, de qué
   tabla, quién lo hizo y de qué otros archivos salió, sin abrir el cuerpo.
2. **Trazabilidad por huella**: cada JSON lista sus insumos con la huella SHA-256 del archivo. El acta
   cita huellas, no solo rutas.
3. **Las diferencias son datos, no párrafos**: viven en una lista estructurada del cotejo, con id. El
   acta las lee de ahí; un agente puede añadir o justificar una diferencia sin tocar el documento.

---

## 1. Dónde se publica

```
OneLake · lh_transversal/Files/resultados/pipeline_v2/
  lotes/<lote>/
    lote_<lote>.json                                   definición final del lote
    flujos/<flujo>/
      ejecucion_<flujo>_<run8>_v<N>.json               ETL Validator + roles corregidos
    tablas/<clave>/
      rapido_stratio_<clave>_v<N>.json                 nivel 0/1 Stratio
      rapido_fabric_<clave>_v<N>.json                  nivel 0/1 Fabric
      cotejo_rapido_<clave>_v<N>.json                  Stratio ↔ Fabric nivel 0/1
      metrica_stratio_<clave>_v<N>.json                nivel 2 Stratio (motor v15)
      metrica_fabric_<clave>_v<N>.json                 nivel 2 Fabric (motor v15)
      cotejo_<clave>_v<N>.json                         Stratio ↔ Fabric nivel 2 + diferencias
    revision/
      resumen_<lote>_<huella>.json                     lo que se aprueba
      RESUMEN_LOTE_<huella>.md
      compuertas_<lote>.json
    bitacora/
      bitacora_<lote>.jsonl                            log de agentes (se sube al cerrar)
    acta/
      acta_<lote>_v<ver>.json                          el acta como datos
      Acta_Entrega_Flujos_Lote<lote>_<fecha>_v<ver>.docx
      acta_<lote>_v<ver>.evidencia.json                manifiesto de enlaces (HEAD)

Bucket · comfqametricsdevqaeus2  (solo métricas: es el punto de encuentro entre plataformas)
  metricas-stratio/v4/qa/<clave>/{rapido,metrica}_stratio_<clave>_v<N>.json
  metricas-fabric/v4/qa/<clave>/{rapido,metrica}_fabric_<clave>_v<N>.json
```
- `<N>` cuenta por tabla en toda su historia (como hoy en v3), se calcula de lo que ya existe; nunca se sobrescribe.
- `<run8>` = primeros 8 caracteres del id de la corrida del flujo en Fabric.
- Prefijo `v4/` en el bucket para no mezclar con lo de los notebooks (`v3/`).

**4 reportes por tabla** (lo que pide la entrega): `metrica_stratio`, `metrica_fabric`, `cotejo` y la
`ejecucion` de su flujo. Los rápidos se publican también: son la evidencia del semáforo.

---

## 2. El sobre común

```json
{
  "formato": "pc.v2/cotejo@1",
  "id": "8d1c…uuid",
  "lote": "12",
  "flujo": {"fabric": "moves", "stratio": "03-moves", "fl": "FL-0123", "grupo": "analitica", "orquestador": "orq_agrupadoras"},
  "clave": "agrupadoras_moves_agrup",
  "plataforma": "AMBAS",
  "nivel": 2,
  "version": 3,
  "generado_utc": "2026-10-12T14:03:22Z",
  "generado_por": {"usuario": "Jhonattan-LT", "agente": "cotejador", "herramienta": "pc/cotejo/completo.py", "version_pc": "2.0.0"},
  "insumos": [
    {"formato": "pc.v2/metrica@1", "ruta": "Files/resultados/pipeline_v2/lotes/12/tablas/…/metrica_stratio_…_v2.json", "sha256": "…"},
    {"formato": "pc.v2/metrica@1", "ruta": "…/metrica_fabric_…_v2.json", "sha256": "…"}
  ],
  "resultado": {"estado": "APROBADO_CON_JUSTIFICACION", "resumen": "dato DIFERENTE; filas 2.460.610 → 2.460.590; 1 diferencia justificada"},
  "cuerpo": { }
}
```
`formato` = `pc.v2/<tipo>@<version del formato>`. Tipos: `lote`, `ejecucion`, `rapido`, `cotejo_rapido`,
`metrica`, `cotejo`, `resumen`, `compuertas`, `acta`. `resultado` siempre trae `estado` y una línea `resumen`.

---

## 3. Cuerpos por tipo

### ejecucion
```json
"cuerpo": {
  "corrida": {"item": "moves", "tipo_item": "DataPipeline", "workspace": "orchestration-qa", "run_id": "…",
              "inicio_utc": "…", "fin_utc": "…", "estado": "Completed", "duracion_s": 601},
  "validador": {"notebook": "qa_v2_etl_validator", "run": "…", "resultado": "PASA_CON_OMISIONES",
                "pruebas": {"corrida_exitosa": "OK", "…": "…"}, "bloqueantes": [], "advertencias": []},
  "roles": {"desde": "codigo_del_flujo+_delta_log", "zip": "Files/assets/flows/agrupadoras/silver/moves/moves.zip",
            "invertidos_por_validador": true,
            "entradas": [{"tabla": "silver.agrupadoras_origenes", "parametro": "origenes_output_path", "commits_en_corrida": 0}],
            "salidas":  [{"tabla": "silver.agrupadoras_moves_agrup", "parametro": "moves_agrup_table", "commits_en_corrida": 1,
                          "version_delta": 12, "commit_utc": "…", "operacion": "CREATE OR REPLACE TABLE AS SELECT"}]},
  "dependencias_ejecutadas": [{"flujo": "destinos", "run_id": "…", "estado": "Completed", "motivo": "entrada sin datos"}]
}
```

### rapido (nivel 0/1, un lado)
```json
"cuerpo": {
  "objeto": {"ubicacion": "silver.agrupadoras_moves_agrup", "tipo_fuente": "DELTA|PARQUET_FILES|POSTGRES|HDFS_PARQUET|SFTP_PARQUET",
             "ventana_fechas": {"columna": "FECHA", "desde": "2026-01-01", "hasta": "2026-09-30"}},
  "nivel0": {"columnas": [{"orden": 0, "nombre": "PARTNER", "tipo": "string", "nullable": true}],
             "hash_esquema_tipos": "…", "version_delta": 12, "ultimo_commit": {"utc": "…", "operacion": "…"}},
  "nivel1": {"filas": 106782, "fuente": "pies_parquet|sql_en_base",
             "columnas": {"PARTNER": {"nulos": 0, "pct_nulos": 0.0, "minimo": "…", "maximo": "…", "es_constante": false}},
             "sin_estadisticas": []},
  "controles": {"VG-01": {"estado": "OK", "nivel": 0}, "CP-01": {"estado": "OK", "valor": 106782, "nivel": 1},
                "CP-03": {"estado": "PENDIENTE_NIVEL_2", "nivel": 2}},
  "costo": {"segundos": 6.0, "bytes_leidos": 65536, "bytes_objeto": 1605791}
}
```

### cotejo_rapido
```json
"cuerpo": {
  "filas": {"stratio": 106782, "fabric": 106782, "delta": 0},
  "esquema": {"solo_en_stratio": [], "solo_en_fabric": [], "tipos_distintos": {}, "renombradas_forma": {}},
  "nulos_distintos": {}, "vacias_solo_en_fabric": [], "constantes_solo_en_fabric": [],
  "controles": {"CP-01": {"criterio": "igual", "stratio": "OK", "fabric": "OK", "resultado": "CUMPLE"}},
  "no_cumple": [], "pendiente_nivel2": ["CP-03", "ID-02", "ID-05", "CP-04"]
}
```

### metrica (nivel 2, un lado)
El reporte del motor v15 **tal cual** (17 secciones: conteos, esquema, hash, perfil, frecuentes, muestra,
validaciones, puntos de control, contrato…) dentro de `cuerpo`. No se cambia: es el formato que ya
entienden el comparador y los lotes anteriores.

### cotejo (nivel 2) · con la lista de diferencias
```json
"cuerpo": {
  "criterio": "integración: contrato, VG sin fallas, ID sin regresiones; filas informativas",
  "exigencias": {"mismas_columnas": true, "tipos_iguales": true, "vg_sin_fallas": true, "id_sin_regresiones": true},
  "veredictos": {"dato": "DIFERENTE", "filas": {…}, "hash": {…}, "esquema": {…}, "nulos": {…},
                 "cardinalidad": {…}, "perfil": {…}, "contrato": {…}, "controles": {…}},
  "controles_por_nivel": {"0": {"cumple": 8, "total": 8}, "1": {"cumple": 5, "total": 5}, "2": {"cumple": 3, "total": 4}},
  "diferencias": [
    {"id": "D1",
     "tipo": "conteo | nulos | tipo | columna_ausente | columna_nueva | valor | duplicados | constante | vacia",
     "columna": "Sueldo",
     "cifra": {"stratio": 431800, "fabric": 0, "delta": -431800, "metrica": "no_nulos"},
     "ejemplo": {"llave": {"PARTNER": "0070062180"}, "stratio": "1.300.000", "fabric": null},
     "causa": "La columna llega vacía: el paso de join no proyecta Sueldo.",
     "causa_medida": true,
     "evidencia": ["…/cotejo_…_v3.json#diferencias/D1", "consulta anti-join en lotes/12/diferencias/D1.sql"],
     "decision": "JUSTIFICADA | HALLAZGO | PENDIENTE",
     "decidido_por": {"usuario": "…", "utc": "…"}}
  ]
}
```
Regla: una diferencia sin `causa_medida: true` no puede quedar `JUSTIFICADA`. Una `HALLAZGO` saca la
tabla del acta y va al reporte técnico.

---

## 4. Bitácora de agentes (log)

Un archivo por lote, `lotes/<lote>/bitacora.jsonl` (una línea = un evento; se sube al cerrar el lote).
Hoy ya existe en forma mínima (`pc/lote.py → bitacora`); la propuesta lo completa:

```json
{"ts": "2026-10-12T14:03:22Z", "lote": "12", "evento": "e-000231",
 "usuario": "Jhonattan-LT", "agente": "medidor-rapido-fabric", "fase": 1, "nivel": 1,
 "accion": "medir_rapido", "flujo": "moves", "clave": "agrupadoras_moves_agrup",
 "estado": "INICIO | OK | ERROR | AVISO | DECISION",
 "duracion_s": 6.0,
 "detalle": {"filas": 106782, "bytes_leidos": 65536},
 "salidas": ["lotes/12/rapido/FABRIC/agrupadoras_moves_agrup.json"],
 "error": null,
 "relacionado": "e-000229"}
```
- `INICIO` y `OK/ERROR` de cada acción larga (descargas, nivel 2, corridas del ETL), con duración real.
- `DECISION`: toda decisión de una persona (semáforo forzado, justificación aceptada, compuerta,
  ejecutar un productor, borrar caché). Lleva `usuario` y el texto que dio en el chat en `detalle.motivo`.
- `AVISO`: cookie vencida, token renovado, VPN caída, reintentos.
- Nunca credenciales ni valores de dato sensibles.
- Vista para el usuario: `python -m pc lote bitacora --lote N [--agente …] [--estado ERROR]` (por implementar).

---

## 5. El acta

El acta pasa a ser **un JSON primero y un .docx después**. El JSON (`acta_<lote>_v<ver>.json`) se arma
solo desde `resumen_<lote>_<huella>.json` y los cotejos; el .docx es su presentación. Así un agente lee
y modifica las tablas en el JSON (por id), no dentro del Word.

Estructura (el formato normalizado vigente, con lo nuevo marcado ★):
```
Portada · Control de versiones (★ huella del resumen aprobado) · Participantes
1. Objeto del acta                 grupos y criterio de cada grupo
2. Resumen de resultados           indicador/resultado + gráfica de flujos por grupo
3. Flujos entregados               3.1 ingesta · 3.2 analítica · 3.3 orquestadores
                                   Fabric | Stratio | FL | capa | tablas (★ solo salidas reales) | veredicto
4. Ejecución                       por flujo: estado, inicio, duración, ★ roles corregidos, dependencias
5. Cotejo de tablas completas      por tabla: capa, filas S/F, columnas idénticas, huella o resultado
6. Controles de calidad            ★ por nivel (0/1/2) y grupo: decide / informa
7. Diferencias y su justificación  ★ una fila por diferencia JUSTIFICADA (id D#): cifra | ejemplo | causa
8. Declaración y aprobación        ★ las 3 compuertas (quién, cuándo, huella) + firmas
9. Anexo de evidencia              ★ los 4 reportes por tabla + ejecución, con huella SHA-256 y HEAD
```

Cada tabla del acta tiene id, columnas fijas y filas con referencia a su fuente:
```json
{"formato": "pc.v2/acta@1", "lote": "12", "version": "1.0", "huella_resumen": "78a7720af8efbe80",
 "secciones": [
   {"id": "S7", "titulo": "Diferencias y su justificación",
    "tablas": [{"id": "T7.1", "titulo": "Diferencias justificadas",
                "columnas": ["tabla", "diferencia", "cifra", "ejemplo", "justificacion"],
                "filas": [{"ref": "agrupadoras_moves_agrup#D1",
                           "celdas": ["agrupadoras_moves_agrup", "nulos · Sueldo", "431.800 → 0", "PARTNER 0070062180: 1.300.000 → vacío", "…"]}]}]}],
 "evidencia": [{"clave": "agrupadoras_moves_agrup", "tipo": "cotejo", "ruta": "…", "sha256": "…", "head_ok": true}]}
```
- Para añadir una diferencia específica, un agente agrega o edita la diferencia en el **cotejo**
  (con causa medida), se re-consolida el resumen (nueva huella) y el acta se regenera: la fila nueva
  aparece en T7.1 con su `ref`. Como la huella cambió, las compuertas piden aprobar de nuevo.
- Las filas de la Word llevan el mismo id en un pie discreto (p. ej. «T7.1·D1»), para que alguien que
  lee el .docx pueda pedir «corrige T7.1·D1» y el agente sepa qué tocar.
- El acta no menciona negativas: las diferencias `HALLAZGO` y los flujos en ROJO van al reporte técnico.

---

## Decisiones que hacen falta

1. ¿Aprobada la ruta `pipeline_v2/lotes/<lote>/…` y el prefijo `v4/` en el bucket?
2. ¿Los rápidos también al bucket, o solo las métricas de nivel 2?
3. ¿Acta como JSON + .docx (propuesto), o solo .docx como hoy?
4. ¿Cuánto detalle en la bitácora pública (se sube a OneLake) frente a la local?
5. ID sin regresión en ingesta: ¿decide o informa? (el catálogo dice decide).
