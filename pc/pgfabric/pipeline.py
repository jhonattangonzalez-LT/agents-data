"""La Postgres de Fabric solo se alcanza desde una DataPipeline de QA (conexion por gateway).

Este modulo es la herramienta del agente `postgres-fabric`: crea/actualiza la pipeline
qa_v2_postgres en datalake-qa, la ejecuta con SQL libre y baja el resultado (parquet en Files/).

Pipeline qa_v2_postgres
  parametros: consulta, carpeta, archivo, timeout (hh:mm:ss)
  actividad : Copy AzurePostgreSqlSource -> Parquet en lh_transversal/Files/<carpeta>/<archivo>

Trampas conocidas: la Copy escribe `date` como timestamp (castear al tipo declarado); hay un corte
de ~140 s por socket TCP en consultas pesadas (trocear por columnas o por rango de llave).
"""
import copy
import io
import json
import os
import time
import uuid

from ..acceso import fabric, onelake as ol
from ..config import CFG, FAB, RAIZ

NOMBRE = FAB["pipeline_postgres"]
WS = FAB["ws_datalake"]
CARPETA_BASE = "resultados/qa_v2_temporal/_pg"   # resultados de la pipeline: temporales, no son reportes


def definicion(nombre=NOMBRE, conexion=None, timeout_actividad="0.02:00:00"):
    """pipeline-content.json de qa_v2_postgres."""
    con = conexion or FAB["conexion_postgres_qa"]
    return {"properties": {
        "description": "QA v2 · lectura de la Postgres de Fabric. SQL libre -> parquet en Files/. Lo administra el agente postgres-fabric.",
        "parameters": {
            "consulta": {"type": "string", "defaultValue": "select 1 as uno"},
            "carpeta": {"type": "string", "defaultValue": f"{CARPETA_BASE}/prueba"},
            "archivo": {"type": "string", "defaultValue": "datos.parquet"},
            "timeout": {"type": "string", "defaultValue": CFG["postgres"]["timeout_consulta"]}},
        "activities": [{
            "name": "postgres_a_parquet", "type": "Copy", "dependsOn": [],
            "policy": {"timeout": timeout_actividad, "retry": 1, "retryIntervalInSeconds": 30,
                       "secureOutput": False, "secureInput": False},
            "typeProperties": {
                "source": {"type": "AzurePostgreSqlSource",
                           "query": {"value": "@pipeline().parameters.consulta", "type": "Expression"},
                           "queryTimeout": {"value": "@pipeline().parameters.timeout", "type": "Expression"},
                           "datasetSettings": {"annotations": [], "type": "AzurePostgreSqlTable", "schema": [],
                                               "typeProperties": {}, "externalReferences": {"connection": con}}},
                "sink": {"type": "ParquetSink", "storeSettings": {"type": "LakehouseWriteSettings"},
                         "formatSettings": {"type": "ParquetWriteSettings", "enableVertiParquet": True},
                         "datasetSettings": {
                             "annotations": [], "type": "Parquet", "schema": [],
                             "linkedService": {"name": "lh_transversal", "properties": {
                                 "annotations": [], "type": "Lakehouse",
                                 "typeProperties": {"workspaceId": WS, "artifactId": FAB["lh_transversal"],
                                                    "rootFolder": "Files"}}},
                             "typeProperties": {"location": {
                                 "type": "LakehouseLocation",
                                 "fileName": {"value": "@pipeline().parameters.archivo", "type": "Expression"},
                                 "folderPath": {"value": "@pipeline().parameters.carpeta", "type": "Expression"}},
                                 "compressionCodec": "snappy"}}},
                "enableStaging": False}}]}}


def buscar(nombre=NOMBRE):
    return next((i for i in fabric.items(WS, "DataPipeline") if i["displayName"] == nombre), None)


def asegurar(nombre=NOMBRE, conexion=None):
    """Crea la pipeline si no existe; si existe, actualiza su definicion. Devuelve el item."""
    d = json.dumps(definicion(nombre, conexion), ensure_ascii=False)
    it = buscar(nombre)
    if it:
        c, b = fabric.actualizar_definicion(WS, it["id"], {"pipeline-content.json": d})
        if c not in (200, 202):
            raise RuntimeError(f"updateDefinition: HTTP {c} {str(b)[:300]}")
        return it
    c, b = fabric.crear_item(WS, nombre, "DataPipeline", {"pipeline-content.json": d},
                             "QA v2 · lectura de la Postgres de Fabric (agente postgres-fabric)")
    if c not in (200, 201):
        raise RuntimeError(f"crear pipeline: HTTP {c} {str(b)[:300]}")
    return b if isinstance(b, dict) and b.get("id") else buscar(nombre)


def duplicar(nombre_nuevo, conexion=None):
    """Variante con otra conexion u otro timeout, para un flujo que lo necesite. No toca la base."""
    return asegurar(nombre_nuevo, conexion)


def ejecutar(consulta, carpeta=None, archivo="datos.parquet", timeout=None, nombre=NOMBRE, max_s=7200):
    """Lanza la consulta y espera. Devuelve {estado, run, segundos, ruta_onelake, error}."""
    it = buscar(nombre)
    if not it:
        raise RuntimeError(f"no existe la pipeline {nombre}: correr asegurar()")
    carpeta = carpeta or f"{CARPETA_BASE}/{time.strftime('%Y%m%d')}/{uuid.uuid4().hex[:10]}"
    params = {"consulta": consulta, "carpeta": carpeta, "archivo": archivo,
              "timeout": timeout or CFG["postgres"]["timeout_consulta"]}
    t0 = time.time()
    run = fabric.lanzar(WS, it["id"], "Pipeline", params)
    r = fabric.esperar(WS, it["id"], run, max_s=max_s, cada=10)
    return {"estado": r.get("status"), "run": run, "segundos": round(time.time() - t0),
            "ruta_onelake": f"Files/{carpeta}/{archivo}", "error": r.get("failureReason"),
            "inicio_utc": r.get("startTimeUtc"), "fin_utc": r.get("endTimeUtc")}


def resultado(ruta_onelake, local=None):
    """Baja el parquet del resultado. Con `local` lo deja en disco; sin el, devuelve pyarrow.Table."""
    import pyarrow.parquet as pq
    rel = ruta_onelake
    if local:
        return ol.bajar(rel, local)
    return pq.read_table(io.BytesIO(ol.leer(rel)))


def consultar(consulta, timeout=None, nombre=NOMBRE):
    """Consulta corta -> lista de dicts (agregados, information_schema). Falla si la pipeline falla."""
    r = ejecutar(consulta, timeout=timeout, nombre=nombre)
    if r["estado"] != "Completed":
        raise RuntimeError(f"pipeline {nombre} {r['estado']}: {json.dumps(r.get('error'))[:400]}")
    t = resultado(r["ruta_onelake"])
    return t.to_pylist(), r
