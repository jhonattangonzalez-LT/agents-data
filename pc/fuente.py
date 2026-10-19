"""Evidencia de que la fuente de Fabric es la equivalente de la de Stratio: todo medido, nada supuesto.

Stratio lee su origen (HDFS, CSV, Postgres); Fabric lee su capa (bronze, silver, Postgres), que a su vez puede venir
de HDFS, SFTP, Postgres o Stratio. Son la misma fuente solo si se mide, en cada plataforma:
  contenido  filas y SHA-256 (o 0 diferencias por llave) entre la fuente de Stratio y la de Fabric  [del cotejador]
  linaje     que elemento de Fabric escribe esa fuente y desde que origen: INGESTA (copia de un pipeline, con su
             origen, corridas y programacion) · CODIGO (un notebook o Spark la nombra) · MANUAL (nada la escribe)
  frescura   fecha de la fuente de Fabric (OneLake), fecha del origen en Stratio (Rocket) y que la refresca
             (ultimas corridas y programacion del pipeline que la escribe)

  python -m pc fuente medir --trabajo T --flujo F --fabric Files/bronze/…/archivo.parquet
                            [--stratio /ruta/hdfs/archivo.csv] [--contenido "filas S|F … SHA-256 …"]
Guarda trabajos/<T>/codigo/<F>/fuentes/<nombre>.json y lo cita la regla (`pc codigo regla --evidencia-fuente`).
Lee definiciones de pipelines de Fabric (cache local de un dia) y, solo con --stratio, hace UNA consulta a Rocket.
"""
import datetime
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from . import lote as L
from .config import FAB

CACHE = os.path.join(os.path.expanduser("~"), ".cache", "pc", "definiciones")
WSS = ("ws_datalake", "ws_ingesta", "ws_orquestacion")


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _definiciones(ws, tipo="DataPipeline"):
    """[(item, texto de su definicion)] de un workspace, con cache de un dia por item. Pipelines: su JSON; notebooks y
    definiciones de Spark: el texto de todas sus partes (codigo)."""
    from .acceso import fabric
    os.makedirs(os.path.join(CACHE, ws), exist_ok=True)
    its = fabric.items(ws, tipo)

    def una(it):
        p = os.path.join(CACHE, ws, f"{it['id']}.txt")
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < 86400:
            return it, open(p, encoding="utf8").read()
        try:
            if tipo == "DataPipeline":
                t = json.dumps(fabric.pipeline_json(ws, it["id"]), ensure_ascii=False)
            else:
                t = "\n".join(v.decode("utf8", "replace") for v in fabric.definicion(ws, it["id"]).values())
        except Exception:
            return it, ""
        open(p, "w", encoding="utf8").write(t)
        return it, t
    with ThreadPoolExecutor(8) as ex:            # tope de OneLake/Fabric: 8 hilos
        return list(ex.map(una, its))


def _actividades(pj):
    out = []

    def rec(acts):
        for a in acts or []:
            out.append(a)
            tp = a.get("typeProperties") or {}
            for k in ("activities", "ifTrueActivities", "ifFalseActivities", "defaultActivities"):
                rec(tp.get(k))
            for c in tp.get("cases") or []:
                rec(c.get("activities"))
    rec((pj.get("properties") or {}).get("activities"))
    return out


def _origen(a):
    """Tipo y ruta del origen de una actividad de copia (lo que se pueda leer de su definicion)."""
    tp = a.get("typeProperties") or {}
    src = tp.get("source") or {}
    ds = src.get("datasetSettings") or {}
    dtp = ds.get("typeProperties") or {}
    loc = dtp.get("location") or {}
    ruta = "/".join(str(loc.get(k)) for k in ("folderPath", "fileName") if loc.get(k))
    if not ruta:
        ruta = dtp.get("table") or dtp.get("tableName")
    return {"tipo": src.get("type") or ds.get("type"), "ruta": ruta,
            "conexion": (ds.get("externalReferences") or {}).get("connection")}


def linaje(ruta_fabric):
    """Quien escribe la ruta (Files/… o esquema.tabla) en Fabric: pipelines y actividades que la nombran."""
    nombre = ruta_fabric.rstrip("/").rsplit("/", 1)[-1]
    carpeta = ruta_fabric.rstrip("/").rsplit("/", 2)[-2] if "/" in ruta_fabric else nombre
    claves = {nombre, nombre.rsplit(".", 1)[0], carpeta}
    hall = []
    for w in WSS:
        ws = FAB.get(w)
        if not ws:
            continue
        for it, txt in _definiciones(ws):
            if not txt or not any(k and k in txt for k in claves):
                continue
            pj = json.loads(txt)
            for a in _actividades(pj):
                at = json.dumps(a, ensure_ascii=False)
                if not any(k and k in at for k in claves):
                    continue
                hall.append({"workspace": w, "pipeline": it["displayName"], "pipeline_id": it["id"], "actividad": a.get("name"),
                             "tipo_actividad": a.get("type"), "origen": _origen(a) if a.get("type") == "Copy" else None,
                             "nombra": sorted(k for k in claves if k and k in at)})
        for tipo in ("Notebook", "SparkJobDefinition", "VariableLibrary"):   # codigo y rutas armadas con variables
            for it, txt in _definiciones(ws, tipo):
                if not txt or not any(k and len(k) > 4 and k in txt for k in claves):
                    continue
                if tipo == "VariableLibrary":
                    # sigue el rastro: que variable guarda la ruta y quien la usa (una copia que la tiene de destino escribe)
                    for var in _variables_con(txt, {ruta_fabric, nombre}):     # ruta o archivo exactos, no la carpeta
                        hall += _usos_de_variable(var, it["displayName"])
                    continue
                hall.append({"workspace": w, "pipeline": it["displayName"], "pipeline_id": it["id"], "actividad": None,
                             "tipo_actividad": tipo, "origen": None, "nombra": sorted(k for k in claves if k and k in txt)})
    return hall


def _variables_con(txt, claves):
    out = []
    for m in re.finditer(r'"name"\s*:\s*"([^"]+)"(?:(?!"name").)*?"value"\s*:\s*"([^"]*)"', txt, re.S):
        if any(k and k in m.group(2) for k in claves):
            out.append(m.group(1))
    return out


def _usos_de_variable(var, libreria):
    """Pipelines que usan la variable: si es destino (sink) de una copia, la escriben; si no, la leen."""
    out = []
    for w in WSS:
        ws = FAB.get(w)
        if not ws:
            continue
        for it, txt in _definiciones(ws):
            if not txt or f'"variableName": "{var}"' not in txt:
                continue
            alias = re.findall(r'"([\w]+)"\s*:\s*\{[^{}]*"variableName"\s*:\s*"' + re.escape(var) + '"', txt)
            pj = json.loads(txt)
            escribe = False
            for a in _actividades(pj):
                if a.get("type") != "Copy":
                    continue
                sink = json.dumps((a.get("typeProperties") or {}).get("sink") or {}, ensure_ascii=False)
                if any(x in sink for x in alias + [var]):
                    escribe = True
                    out.append({"workspace": w, "pipeline": it["displayName"], "pipeline_id": it["id"], "actividad": a.get("name"),
                                "tipo_actividad": "Copy", "origen": _origen(a), "nombra": [f"{libreria}.{var}"]})
            if not escribe:
                out.append({"workspace": w, "pipeline": it["displayName"], "pipeline_id": it["id"], "actividad": None,
                            "tipo_actividad": "UsaVariable", "origen": None, "nombra": [f"{libreria}.{var}"]})
    return out


def _rol(x, flujo=None):
    """escribe · lee · invoca · variable: una copia que la tiene de destino escribe; el propio flujo y quien lo invoca, no."""
    if x.get("tipo_actividad") == "Copy":
        return "escribe"
    if x.get("tipo_actividad") == "VariableLibrary":
        return "variable"
    if x.get("tipo_actividad") in ("InvokePipeline", "ExecutePipeline"):
        return "invoca"
    if x.get("tipo_actividad") == "UsaVariable" or (flujo and x.get("pipeline") in (flujo,)):
        return "lee"
    return "codigo"


def veredicto_linaje(lin, ruta_fabric, flujo=None):
    """INGESTA (una copia de pipeline la escribe) · CODIGO (un notebook o Spark la nombra) · MANUAL (nada en Fabric la
    escribe: se busco en todos los pipelines, notebooks y definiciones de Spark de los workspaces de QA)."""
    for x in lin:
        x["rol"] = _rol(x, flujo)
    copias = [x for x in lin if x["rol"] == "escribe"]
    if copias:
        return "INGESTA", f"la escribe la copia «{copias[0]['actividad']}» del pipeline «{copias[0]['pipeline']}»"
    var = [x for x in lin if x["rol"] == "variable"]
    if var:
        return "VARIABLE", (f"la ruta está en la Variable Library «{var[0]['pipeline']}»: buscar qué copia usa esa variable "
                            "antes de concluir")
    codigo = [x for x in lin if x["rol"] == "codigo"]
    if codigo:
        return "CODIGO", f"la nombra «{codigo[0]['pipeline']}» ({codigo[0]['tipo_actividad']}): confirmar en su código si la escribe"
    lectores = sorted({x["pipeline"] for x in lin if x["rol"] in ("lee", "invoca")})
    if lectores:
        return "MANUAL", (f"ninguna copia, notebook ni variable de {', '.join(WSS)} escribe {ruta_fabric}; solo la leen o invocan: "
                          f"{', '.join(lectores)}. La copia a Fabric fue manual, no la hace una ingesta")
    return "MANUAL", (f"ningún pipeline, notebook ni definición de Spark de {', '.join(WSS)} escribe {ruta_fabric}: "
                      "la copia a Fabric fue manual, no la hace una ingesta")


def _programacion(ws, item_id):
    from .acceso import fabric
    try:
        c, b = fabric.api(f"/workspaces/{ws}/items/{item_id}/jobs/Pipeline/schedules")
        return (b or {}).get("value") if c == 200 and isinstance(b, dict) else None
    except Exception:
        return None


def medir(trabajo, flujo, ruta_fabric, ruta_stratio=None, contenido=None):
    from .acceso import fabric, onelake as ol
    ev = {"medido_utc": _ahora(), "fabric": {"ruta": ruta_fabric}, "stratio": {"ruta": ruta_stratio}, "contenido": contenido}
    if ruta_fabric.startswith(("Files/", "Tables/")):
        h = ol.head(ruta_fabric)
        ev["fabric"].update(existe=h is not None, modificado=(h or {}).get("modificado"), bytes=(h or {}).get("bytes"))
    lin = linaje(ruta_fabric)
    for x in lin:
        ws = FAB[x["workspace"]]
        cs = fabric.corridas(ws, x["pipeline_id"])[:3]
        x["ultimas_corridas"] = [{"inicio": r.get("startTimeUtc"), "fin": r.get("endTimeUtc"), "estado": r.get("status")} for r in cs]
        x["programacion"] = _programacion(ws, x["pipeline_id"])
    ev["linaje"] = lin
    ev["linaje_veredicto"], ev["linaje_explicacion"] = veredicto_linaje(lin, ruta_fabric, flujo)
    if ruta_stratio:
        from .acceso import rocket
        carpeta, archivo = ruta_stratio.rstrip("/").rsplit("/", 1)
        arch = [a for a in rocket.arbol(carpeta, hilos=1) if a[0].rstrip("/").endswith("/" + archivo)]
        ev["stratio"].update(existe=bool(arch), bytes=arch[0][1] if arch else None,
                             modificado=datetime.datetime.fromtimestamp(arch[0][2] / 1000, datetime.timezone.utc).isoformat(timespec="seconds")
                             if arch and arch[0][2] else None)
    falta = []
    if not contenido:
        falta.append("contenido: filas y SHA-256 (o 0 diferencias por llave) entre las dos fuentes")
    # el linaje siempre queda medido: o lo escribe algo (con su origen y corridas) o se concluye copia MANUAL
    if not ev["fabric"].get("modificado") and ruta_fabric.startswith(("Files/", "Tables/")):
        falta.append("frescura: la fuente de Fabric no existe o no da fecha")
    if ruta_stratio and not ev["stratio"].get("modificado"):
        falta.append("frescura: el origen de Stratio no se encontró en HDFS")
    if not ruta_stratio:
        falta.append("frescura: falta la fecha del origen de Stratio (--stratio)")
    ev["falta"] = falta
    ev["completa"] = not falta
    nombre = re.sub(r"[^\w.-]+", "_", ruta_fabric.rstrip("/").rsplit("/", 1)[-1])
    p = L.guardar(trabajo, f"codigo/{flujo}/fuentes/{nombre}.json", ev)
    L.bitacora(trabajo, "revisor-codigo", "medir_fuente", {"fabric": ruta_fabric, "completa": ev["completa"], "falta": falta},
               estado="OK" if ev["completa"] else "AVISO", flujo=flujo, salidas=[os.path.relpath(p, L.dir_lote(trabajo))])
    return ev, os.path.relpath(p, L.dir_lote(trabajo))


def texto(ev, rel):
    out = [f"fuente Fabric {ev['fabric']['ruta']} · modificada {ev['fabric'].get('modificado') or '—'}"]
    if ev["stratio"].get("ruta"):
        out.append(f"origen Stratio {ev['stratio']['ruta']} · modificado {ev['stratio'].get('modificado') or '—'}")
    out.append(f"LINAJE {ev.get('linaje_veredicto')}: {ev.get('linaje_explicacion')}")
    for x in ev["linaje"]:
        o = x.get("origen") or {}
        uc = (x.get("ultimas_corridas") or [{}])[0]
        out.append(f"linaje [{x.get('rol')}]: {x['pipeline']} ({x['workspace']}) · actividad {x['actividad']} [{x['tipo_actividad']}]"
                   + (f" · origen {o.get('tipo')} {o.get('ruta') or ''}" if o else "")
                   + (f" · última corrida {uc.get('inicio')} {uc.get('estado')}" if uc else "")
                   + (" · con programación" if x.get("programacion") else " · sin programación"))
    out.append(f"contenido: {ev.get('contenido') or '—'}")
    out.append("COMPLETA: todo medido" if ev["completa"] else "FALTA MEDIR: " + " · ".join(ev["falta"]))
    out.append(f"evidencia: {rel}")
    return "\n".join(out)
