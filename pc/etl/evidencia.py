"""Evidencia de ejecucion y de dependencias de un flujo, MEDIDA en Fabric (API + _delta_log), guardada en disco.

Responde, con dato y no con supuesto, lo que el cotejo de flujo debe mostrar:
  · que corrida se valido (la que escribio la version Delta que se midio), sus actividades y las demas corridas del dia;
  · cada entrada: version y hora del commit que el flujo leyo, quien lo produjo y si cambio despues de la corrida;
  · cada salida: commits dentro de la ventana, version vigente y si es la version medida en el nivel 2;
  · la cadena del orquestador: cada actividad con su estado y su ventana.

`medir(trabajo, flujo)` escribe etl/evidencia/<flujo>.json. `v4.construir_cotejo_flujo` lo lee; no toca la red.
"""
import datetime

from .. import lote as L
from ..acceso import fabric
from ..acceso import onelake as ol
from ..config import FAB
from ..rapido import delta_remoto as dr

SIN_DATO = {"OPTIMIZE", "VACUUM START", "VACUUM END", "SET TBLPROPERTIES", "FSCK"}
HOLGURA_S = 120


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(d):
    return d.isoformat(timespec="seconds") if d else None


def _buscar(nombre, tipos):
    """En los workspaces del proyecto (orquestacion, ingesta, datalake), no en todos los visibles."""
    for ws in (FAB.get("ws_orquestacion"), FAB.get("ws_ingesta"), FAB.get("ws_datalake")):
        if ws:
            h = fabric.buscar_item(nombre, tipos=tipos, ws=ws)
            if h:
                return h
    return []


def _es_delta(ruta):
    return bool(ruta) and "." in ruta and "/" not in ruta


def _corridas(item, desde):
    out = []
    for c in fabric.corridas(item["workspaceId"], item["id"]):
        ini = dr.a_utc(c.get("startTimeUtc"))
        if ini and ini >= desde:
            out.append({"run_id": c.get("id"), "estado": c.get("status"), "inicio_utc": _iso(ini),
                        "fin_utc": _iso(dr.a_utc(c.get("endTimeUtc"))), "invocacion": c.get("invokeType"),
                        "falla": (c.get("failureReason") or {}).get("message") if isinstance(c.get("failureReason"), dict)
                        else c.get("failureReason")})
    return sorted(out, key=lambda c: c["inicio_utc"])


def _actividades(ws, run_id, desde):
    cuerpo = {"filters": [], "orderBy": [{"orderBy": "ActivityRunStart", "order": "ASC"}],
              "lastUpdatedAfter": (desde - datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "lastUpdatedBefore": (_ahora() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    c, r, _ = fabric.bruta(f"/workspaces/{ws}/datapipelines/pipelineruns/{run_id}/queryactivityruns", "POST", cuerpo)
    if c != 200 or not isinstance(r, dict):
        return None
    out = []
    for a in r.get("value") or []:
        o = a.get("output") or {}
        fila = {"actividad": a.get("activityName"), "tipo": a.get("activityType"), "estado": a.get("status"),
                "inicio_utc": _iso(dr.a_utc(a.get("activityRunStart"))), "fin_utc": _iso(dr.a_utc(a.get("activityRunEnd"))),
                "duracion_s": round((a.get("durationInMs") or 0) / 1000, 1) if a.get("durationInMs") is not None else None}
        for k_api, k in (("rowsRead", "filas_leidas"), ("rowsCopied", "filas_copiadas"), ("filesRead", "archivos_leidos"),
                         ("filesWritten", "archivos_escritos"), ("dataRead", "bytes_leidos"), ("dataWritten", "bytes_escritos"),
                         ("rowsSkipped", "filas_omitidas")):
            if k_api in o:
                fila[k] = o[k_api]
        if a.get("status") == "Failed":
            fila["error"] = str((a.get("error") or {}).get("message") or a.get("error") or "")[:600]
        out.append(fila)
    return out


def _dentro(utc, c, holgura_s=HOLGURA_S):
    if not utc or not c.get("inicio_utc"):
        return False
    h = datetime.timedelta(seconds=holgura_s)
    fin = dr.a_utc(c.get("fin_utc")) or _ahora()
    return dr.a_utc(c["inicio_utc"]) - h <= dr.a_utc(utc) <= fin + h


def _commit(c):
    m = c.get("metricas") or {}
    return {"version": c["version"], "utc": c["utc"], "operacion": c["operacion"],
            "modo": (c.get("parametros") or {}).get("mode"),
            "filas_escritas": int(m["numOutputRows"]) if str(m.get("numOutputRows", "")).isdigit() else None,
            "archivos_escritos": int(m["numFiles"]) if str(m.get("numFiles", "")).isdigit() else None}


def _log(ruta, cache):
    if ruta not in cache:
        try:
            base = dr.resolver_tabla(ruta)
            cache[ruta] = dr.leer_log(base) if base else None
        except Exception as e:
            cache[ruta] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
    return cache[ruta]


def _escrituras(log):
    return [c for c in log["commits"] if c.get("utc") and (c.get("operacion") or "") not in SIN_DATO]


def _carpeta(ruta, ini, fin):
    """Carpeta de Files (no Delta): cuantos archivos, bytes y cuando se escribieron; cuales dentro de la corrida."""
    from email.utils import parsedate_to_datetime
    arch = [p for p in ol.listar(ruta, recursivo=True) if not p["isDirectory"] and not p["name"].rsplit("/", 1)[-1].startswith(("_", "."))]
    if not arch:
        return {"existe": False}
    fechas = []
    for p in arch:
        try:
            fechas.append((parsedate_to_datetime(p["lastModified"]), p))
        except Exception:
            pass
    h = datetime.timedelta(seconds=HOLGURA_S)
    en = [p for d, p in fechas if ini and fin and ini - h <= d <= fin + h]
    desp = [p for d, p in fechas if fin and d > fin + h]
    partes = sorted({p["name"][len(ruta.strip("/")) + 1:].rsplit("/", 1)[0] for p in en if "/" in p["name"][len(ruta.strip("/")) + 1:]})
    return {"existe": True, "archivos": len(arch), "bytes": sum(p["contentLength"] for p in arch),
            "primera_escritura_utc": _iso(min(d for d, _ in fechas)) if fechas else None,
            "ultima_escritura_utc": _iso(max(d for d, _ in fechas)) if fechas else None,
            "archivos_escritos_en_la_corrida": len(en), "bytes_escritos_en_la_corrida": sum(p["contentLength"] for p in en),
            "particiones_escritas_en_la_corrida": len(partes),
            "particiones_escritas_muestra": partes[:5] + (["…"] if len(partes) > 10 else []) + (partes[-5:] if len(partes) > 10 else partes[5:10]),
            "archivos_escritos_despues_de_la_corrida": len(desp)}


def medir(trabajo, flujo, dias=3):
    f = L.flujo(trabajo, flujo)
    if not f:
        raise KeyError(flujo)
    etl = L.leer(trabajo, f"etl/veredictos/{flujo}.json") or {}
    inv = etl.get("inventario") or {}
    corr = inv.get("correccion") or {}
    desde = _ahora() - datetime.timedelta(days=dias)
    doc = {"flujo": flujo, "medido_utc": _iso(_ahora()), "fuente": "API de Fabric (jobs/instances, queryactivityruns) y _delta_log / listado de OneLake"}
    logs = {}

    # ---- el item y sus corridas
    its = _buscar(flujo, ("DataPipeline", "SparkJobDefinition", "Notebook"))
    item = its[0] if its else None
    doc["item"] = ({"nombre": item["displayName"], "tipo": item["type"], "id": item["id"], "workspace": item["workspaceId"]}
                   if item else None)
    corridas = _corridas(item, desde) if item else []
    doc["corridas"] = corridas

    # ---- salidas: que version se midio y que corrida la escribio
    salidas, entradas = [], []
    rutas_sal = [x["ruta"] for x in corr.get("salidas") or [] if _es_delta(x.get("ruta"))]
    rutas_ent = [x["ruta"] for x in corr.get("entradas") or []]
    medidas = {}
    for o in f["objetos"]:
        m = L.leer(trabajo, f"v4/mediciones/FABRIC/{o['clave']}.json") or {}
        r = (o.get("fabric") or {}).get("ruta")
        medidas[(r or "").lower()] = {"clave": o["clave"], "version_delta": (m.get("nivel_0") or {}).get("version_delta"),
                                      "medido_utc": (m.get("encabezado") or {}).get("medido_utc"),
                                      "filas": (m.get("nivel_2") or m.get("nivel_1") or {}).get("filas")}
        if _es_delta(r) and r not in rutas_sal and f["grupo"] != "ingesta":
            rutas_sal.append(r)
    commit_medido = None
    for r in rutas_sal:
        lg = _log(r, logs)
        fila = {"tabla": r}
        if not lg or lg.get("error"):
            fila["nota"] = (lg or {}).get("error") or "la tabla no existe en el lakehouse"
            salidas.append(fila)
            continue
        esc = _escrituras(lg)
        med = medidas.get(r.lower()) or {}
        fila.update(version_vigente=lg["version"], ultimo_commit=_commit(esc[-1]) if esc else None,
                    version_medida_nivel_2=med.get("version_delta"), filas_medidas_nivel_2=med.get("filas"),
                    commits_recientes=[_commit(c) for c in esc if dr.a_utc(c["utc"]) >= desde])
        if med.get("version_delta") is not None:
            cm = next((c for c in reversed(esc) if c["version"] <= med["version_delta"]), None)
            fila["commit_de_la_version_medida"] = _commit(cm) if cm else None
            fila["la_version_medida_es_la_vigente"] = bool(esc) and (cm or {}).get("version") == esc[-1]["version"]
            if cm and (commit_medido is None or cm["utc"] > commit_medido):
                commit_medido = cm["utc"]
        salidas.append(fila)

    # ---- la corrida validada: la que escribio lo que se midio
    validada, motivo = None, None
    if commit_medido:
        validada = next((c for c in corridas if _dentro(commit_medido, c)), None)
        motivo = (f"es la corrida en cuya ventana cae el commit Delta de la version medida ({commit_medido})" if validada else
                  f"ninguna corrida de `{flujo}` de los ultimos {dias} dias contiene el commit de la version medida ({commit_medido})")
    if not validada:
        cita = (etl.get("resumen") or {}).get("inicio_utc")
        validada = next((c for c in corridas if cita and c["inicio_utc"][:19] == _iso(dr.a_utc(cita))[:19]), None)
        if validada:
            motivo = (motivo + "; " if motivo else "") + "se toma la corrida que registro el validador"
        elif corridas:
            ok = [c for c in corridas if c["estado"] == "Completed"]
            validada = (ok or corridas)[-1]
            motivo = (motivo + "; " if motivo else "") + "se toma la ultima corrida Completed"
    doc["corrida_validada"] = dict(validada, criterio=motivo) if validada else None
    ini = dr.a_utc(validada["inicio_utc"]) if validada else None
    fin = dr.a_utc(validada["fin_utc"]) if validada and validada.get("fin_utc") else None
    cita = (etl.get("resumen") or {}).get("inicio_utc")
    doc["corrida_citada_por_el_validador"] = {"inicio_utc": _iso(dr.a_utc(cita)) if cita else None,
                                              "coincide_con_la_validada": bool(cita and validada and
                                                                               _iso(dr.a_utc(cita))[:19] == validada["inicio_utc"][:19])}
    if validada and item and item["type"] == "DataPipeline":
        doc["actividades"] = _actividades(item["workspaceId"], validada["run_id"], desde)
    for s in salidas:
        if s.get("commits_recientes") is not None and validada:
            en = [c for c in s["commits_recientes"] if _dentro(c["utc"], validada)]
            s["commits_en_la_corrida_validada"] = en
            s["escrita_por_la_corrida_validada"] = bool(en)
            s["commits_posteriores_a_la_corrida"] = [c for c in s["commits_recientes"] if fin and dr.a_utc(c["utc"]) > fin + datetime.timedelta(seconds=HOLGURA_S)]

    # ---- orquestador: la cadena con estados
    orq = None
    if f.get("orquestador") or (etl.get("lanzamiento") and etl.get("lanzamiento") != flujo and "orq" in str(etl.get("lanzamiento"))):
        nombre = f.get("orquestador") or etl.get("lanzamiento")
        io = _buscar(nombre, ("DataPipeline",))
        if io:
            cs = _corridas(io[0], desde)
            pad = next((c for c in reversed(cs) if validada and _dentro(validada["inicio_utc"], c, 0)), None)
            orq = {"nombre": nombre, "corridas": cs, "corrida_que_invoco_al_flujo": pad}
            if pad:
                orq["actividades"] = _actividades(io[0]["workspaceId"], pad["run_id"], desde)
        else:
            orq = {"nombre": nombre, "nota": "no se encontro el pipeline del orquestador"}
    doc["orquestador"] = orq
    acts = (orq or {}).get("actividades") or []

    def productor(utc):
        a = next((x for x in acts if x.get("inicio_utc") and _dentro(utc, x, 30)), None)
        return {"actividad_del_orquestador": a["actividad"], "estado": a["estado"], "inicio_utc": a["inicio_utc"],
                "fin_utc": a["fin_utc"]} if a else None

    # ---- entradas
    aristas = {(x.get("ruta") or "").rsplit("/", 1)[-1].lower(): x.get("productor")
               for x in ((etl.get("veredicto") or {}).get("dependencias") or {}).get("aristas_entrada") or []}
    for r in rutas_ent:
        fila = {"entrada": r}
        if _es_delta(r):
            lg = _log(r, logs)
            if not lg or lg.get("error"):
                fila["nota"] = (lg or {}).get("error") or "la tabla no existe en el lakehouse"
                entradas.append(fila)
                continue
            esc = _escrituras(lg)
            leido = next((c for c in reversed(esc) if ini and dr.a_utc(c["utc"]) <= ini), None)
            desp = [c for c in esc if ini and dr.a_utc(c["utc"]) > ini]
            fila.update(tipo="tabla Delta", version_vigente=lg["version"],
                        commit_leido_por_la_corrida=_commit(leido) if leido else None,
                        antiguedad_al_leer_h=round((ini - dr.a_utc(leido["utc"])).total_seconds() / 3600, 2) if leido and ini else None,
                        productor_segun_validador=aristas.get(r.split(".")[-1].lower()),
                        productor_segun_orquestador=productor(leido["utc"]) if leido else None,
                        cambio_despues_de_iniciar_la_corrida=bool(desp),
                        commits_posteriores=[_commit(c) for c in desp][:5])
        elif r.startswith("Files/"):
            try:
                fila.update(tipo="carpeta de archivos", **_carpeta(r, ini, fin))
            except Exception as e:
                fila["nota"] = f"{type(e).__name__}: {str(e)[:160]}"
        else:
            fila["tipo"] = "origen externo"
            fila["nota"] = "origen fuera del lakehouse: no se mide desde Fabric"
        entradas.append(fila)

    # ---- ingesta: el destino es una carpeta de Files
    if f["grupo"] == "ingesta":
        for o in f["objetos"]:
            r = (o.get("fabric") or {}).get("ruta")
            if r and r.startswith("Files/"):
                try:
                    salidas.append(dict({"destino": r, "tipo": "carpeta de archivos"}, **_carpeta(r, ini, fin)))
                except Exception as e:
                    salidas.append({"destino": r, "nota": f"{type(e).__name__}: {str(e)[:160]}"})
            elif _es_delta(r):
                lg = _log(r, logs)
                if lg and not lg.get("error"):
                    esc = _escrituras(lg)
                    en = [_commit(c) for c in esc if validada and _dentro(c["utc"], validada)]
                    salidas.append({"tabla": r, "version_vigente": lg["version"], "commits_en_la_corrida_validada": en,
                                    "escrita_por_la_corrida_validada": bool(en), "ultimo_commit": _commit(esc[-1]) if esc else None})
    doc["entradas"], doc["salidas"] = entradas, salidas
    L.guardar(trabajo, f"etl/evidencia/{flujo}.json", doc)
    L.bitacora(trabajo, "etl-validador", "medir_evidencia", {"corrida": (validada or {}).get("run_id"), "entradas": len(entradas),
               "salidas": len(salidas)}, flujo=flujo)
    return doc
