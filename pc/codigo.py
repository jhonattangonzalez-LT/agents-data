"""Revision del codigo de los dos lados: el workflow de Stratio (Rocket) contra el flujo de Fabric (zip en OneLake).

Corre al comienzo, en paralelo a los niveles 0/1 y 2. Sirve para clasificar las diferencias del dato:
  regla igual en los dos lados  -> la diferencia es de dato (insumo, corte, fecha del dia o formato): justificable
  regla distinta                -> error del flujo: se devuelve a desarrollo (lo confirma una persona)

  bajar     baja el codigo: la VERSION de Stratio la da el usuario (nunca se supone la ultima); sin version, lista las
            versiones del workflow y se detiene. Guarda codigo/<flujo>/fuente.json (nombres, version, fechas, huellas),
            el JSON de Rocket y su texto por nodo, y el zip de Fabric extraido con su texto por paso.
  regla     registra una regla de negocio comparada (stratio: nodo y extracto · fabric: archivo y extracto · resultado)
            y, si no es IGUAL, POR QUE difiere (clase + porque):
              EQUIVALENTE · PLATAFORMA  misma regla de negocio escrita distinto por la plataforma o el lenguaje (HDFS vs
                                        Delta/Postgres, Spark SQL vs PySpark, coalesce vs nvl, casts del destino):
                                        justificable, con el porque escrito; no bloquea
              DISTINTA · FUENTE         Fabric lee otra entrada, version o ventana de origen: se pregunta (justificable
                                        solo si se mide que esa fuente es la equivalente migrada)
              DISTINTA · LOGICA         otro join, filtro, agregacion, calculo, deduplicacion, valor por defecto o
                                        mapeo de codigos: grave, se propone devolver; decide una persona
  cerrar    cierra la revision: IGUAL (todas las reglas iguales) o CON_DIFERENCIAS (alguna DISTINTA o en un solo lado)
  estado    resumen por flujo del trabajo
  comentar  respuesta de desarrollo / verificacion de QA / decision (ACEPTADA · DEVOLVER · PENDIENTE) sobre una regla
  cotejo    escribe la llave `revision_codigo` en el cotejo de flujo de la version vigente (--publicar: en sitio + HEAD)

`revision_codigo` en el cotejo de flujo: cerrar y comentar la actualizan solos en local (misma vN). Si la revision no
bloquea (ninguna regla a DEVOLVER) las fases siguientes siguen; las aclaraciones posteriores quedan en esa misma version
con su historial.

Solo lectura en Rocket y en OneLake. La cookie de Rocket nunca se imprime. La API de Rocket se usa con GET:
  /assets (workflows) · /assets/findAllVersions/{assetId} · /workflows/findById/{versionId} (o /workflows/download/{id})
"""
import datetime
import hashlib
import io
import json
import os
import re
import urllib.error
import urllib.request
import zipfile

from . import lote as L
from .acceso import onelake as ol, rocket

RESULTADOS = ("IGUAL", "EQUIVALENTE", "DISTINTA", "SOLO_STRATIO", "SOLO_FABRIC")
CLASES = ("PLATAFORMA", "FUENTE", "LOGICA")
PROPUESTA = {"PLATAFORMA": "EQUIVALENTE: misma regla, distinta forma de leer, escribir o expresar; con efecto medido nulo sigue sin preguntar",
             "FUENTE": "PREGUNTAR: aceptable como fuente equivalente si el contenido se midió igual; si no, reportar a desarrollo",
             "LOGICA": "DEVOLVER: reglas de negocio desalineadas (grave); lo confirma una persona"}


def es_igual(g):
    """IGUAL o EQUIVALENTE (misma regla de negocio): no bloquea ni cuenta como diferencia del flujo."""
    return (g or {}).get("resultado") in ("IGUAL", "EQUIVALENTE")
VEREDICTOS = ("IGUAL", "CON_DIFERENCIAS")


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _get(endpoint, timeout=240):
    """GET a Rocket con la siguiente cookie del turno; un 401 aparta esa cookie y reintenta con otra."""
    for _ in range(3):
        ruta_c, valor = rocket._cookie()
        req = urllib.request.Request(f"{rocket.URL}/{endpoint.lstrip('/')}",
                                     headers={"Cookie": valor, "Accept": "application/json"})
        try:
            return urllib.request.urlopen(req, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code == 401:
                with rocket._LK:
                    rocket._VENCIDAS.add(ruta_c)
                continue
            raise
    raise rocket.CookieVencida("Rocket respondio 401 con todas las cookies: pedir cookies nuevas")


def buscar_workflow(nombre_stratio):
    """Workflows de Rocket con ese nombre (exacto, sin distinguir mayusculas); si no hay, los que lo contienen."""
    todos = [a["workflowAsset"] for a in json.loads(_get("/assets")) if a.get("workflowAsset")]
    exactos = [w for w in todos if (w.get("name") or "").lower() == nombre_stratio.lower()]
    return exactos or [w for w in todos if nombre_stratio.lower() in (w.get("name") or "").lower()]


def versiones(asset_id):
    return sorted(json.loads(_get(f"/assets/findAllVersions/{asset_id}")), key=lambda v: v.get("version", 0))


def _definicion(version_id):
    try:
        return _get(f"/workflows/findById/{version_id}")
    except urllib.error.HTTPError:
        return _get(f"/workflows/download/{version_id}")


def _plano(c, pref=""):
    out = []
    if isinstance(c, dict):
        for k, v in c.items():
            out += _plano(v, f"{pref}.{k}" if pref else k)
    elif isinstance(c, list):
        for i, v in enumerate(c):
            out += _plano(v, f"{pref}[{i}]")
    elif c not in (None, "", [], {}):
        out.append((pref, c))
    return out


def texto_rocket(j):
    """Texto legible del workflow: un bloque por nodo con su tipo y su configuracion (SQL incluido), y las aristas."""
    g = j.get("pipelineGraph") or {}
    out = [f"# {j.get('name')} v{j.get('version')} · grupo {(j.get('group') or {}).get('name')} · actualizado {j.get('lastUpdateDate')}",
           "# aristas: " + " ; ".join(f"{e.get('origin')} -> {e.get('destination')}" for e in g.get("edges", []))]
    for n in g.get("nodes", []):
        out.append(f"\n===== NODO {n.get('name')} | {n.get('className') or n.get('classPrettyName')} | {n.get('stepType')}")
        out += [f"{k} = {v}" for k, v in _plano({"cfg": n.get("configuration") or {}, "writer": n.get("outputsWriter") or {}})]
    return "\n".join(out)


def _dir(trabajo, flujo):
    return os.path.join(L.dir_lote(trabajo), "codigo", flujo)


def bajar(trabajo, flujo, version=None, nombre_stratio=None, asset_id=None):
    """Baja el codigo de los dos lados. Devuelve fuente.json, o {'pide_version': [...]} si falta la version de Stratio."""
    f = L.flujo(trabajo, flujo)
    if not f:
        raise ValueError(f"{flujo} no esta en el trabajo {trabajo}")
    nombre_stratio = nombre_stratio or f.get("nombre_stratio")
    version = version if version is not None else f.get("version_stratio")
    if not nombre_stratio:
        return {"pide": "nombre del workflow en Stratio (Rocket)", "flujo": flujo}
    cand = [w for w in buscar_workflow(nombre_stratio) if not asset_id or w["id"] == asset_id]
    if not cand:
        return {"pide": f"no hay workflow en Rocket con el nombre «{nombre_stratio}»: confirmar el nombre", "flujo": flujo}
    if len(cand) > 1:
        return {"pide": "varios workflows con ese nombre: elegir uno (--asset)", "flujo": flujo,
                "candidatos": [{"asset": w["id"], "nombre": w.get("name"), "grupo": (w.get("group") or {}).get("name"),
                                "actualizado": w.get("lastUpdateDate")} for w in cand]}
    w = cand[0]
    V = versiones(w["id"])
    lista = [{"version": v.get("version"), "actualizado": v.get("lastUpdateDate"), "id": v.get("id")} for v in V]
    if version is None:
        return {"pide": "version de Stratio que se trae (no se supone la ultima)", "flujo": flujo, "workflow": w.get("name"),
                "versiones": lista}
    elegida = next((v for v in V if int(v.get("version", -1)) == int(version)), None)
    if not elegida:
        return {"pide": f"la version {version} no existe en Rocket", "flujo": flujo, "versiones": lista}
    d = _dir(trabajo, flujo)
    os.makedirs(os.path.join(d, "stratio"), exist_ok=True)
    os.makedirs(os.path.join(d, "fabric"), exist_ok=True)
    raw = _definicion(elegida["id"])
    j = json.loads(raw)
    p_json = os.path.join(d, "stratio", f"{re.sub(r'[^A-Za-z0-9_-]', '_', w['name'])}_v{version}.json")
    open(p_json, "wb").write(raw)
    open(os.path.join(d, f"stratio_v{version}.txt"), "w", encoding="utf8").write(texto_rocket(j))
    ultima = max(V, key=lambda v: v.get("lastUpdateDate") or "")
    fuente = {"flujo": flujo, "nombre_stratio": w.get("name"), "grupo_rocket": (w.get("group") or {}).get("name"),
              "stratio": {"version": int(version), "version_id": elegida["id"], "actualizado": elegida.get("lastUpdateDate"),
                          "nodos": len((j.get("pipelineGraph") or {}).get("nodes", [])),
                          "sha256": hashlib.sha256(raw).hexdigest(), "archivo": os.path.relpath(p_json, d),
                          "versiones_en_rocket": lista,
                          "es_la_mas_reciente": ultima.get("id") == elegida["id"]},
              "fabric": None, "descargado_utc": _ahora(), "descargado_por": L.usuario()}
    from .inventario import roles
    zs = roles.candidatos_zip(flujo)
    if zs:
        z = zs[0]
        b = ol.leer(z["name"])
        zf = zipfile.ZipFile(io.BytesIO(b))
        pasos = []
        for n in sorted(zf.namelist()):
            if n.endswith("/") or ".." in n:
                continue
            p = os.path.join(d, "fabric", n)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(zf.read(n))
            if n.endswith((".py", ".sql", ".json")):
                pasos.append(f"\n===== ARCHIVO {n}\n" + zf.read(n).decode("utf8", "replace"))
        open(os.path.join(d, "fabric.txt"), "w", encoding="utf8").write(f"# {z['name']}\n" + "".join(pasos))
        fuente["fabric"] = {"zip": z["name"], "modificado": z.get("lastModified"), "sha256": hashlib.sha256(b).hexdigest(),
                            "archivos": len(zf.namelist()), "otros_zip": [x["name"] for x in zs[1:]]}
    L.guardar(trabajo, f"codigo/{flujo}/fuente.json", fuente)
    L.bitacora(trabajo, "revisor-codigo", "bajar", {"stratio": f"{w.get('name')} v{version}",
                                                  "fabric": (fuente["fabric"] or {}).get("zip")},
               estado="OK" if fuente["fabric"] else "AVISO", flujo=flujo)
    return fuente


def revision(trabajo, flujo):
    return L.leer(trabajo, f"codigo/{flujo}/revision.json") or {"flujo": flujo, "reglas": [], "veredicto": None}


def regla(trabajo, flujo, texto, stratio, fabric, resultado, impacto=None, rid=None, clase=None, porque=None,
          medido=None, no_medido=None, evidencia_fuente=None):
    """Registra (o corrige, con el mismo id) una regla de negocio comparada en los dos lados. Si no es IGUAL exige la
    clase (por que difiere) y el porque: es lo que decide si se justifica, se pregunta o se devuelve."""
    assert resultado in RESULTADOS, resultado
    if resultado == "EQUIVALENTE":
        clase = "PLATAFORMA"
    if resultado != "IGUAL":
        if clase not in CLASES:
            raise ValueError(f"una regla {resultado} exige --clase {CLASES}")
        if resultado != "EQUIVALENTE" and clase == "PLATAFORMA":
            raise ValueError("una diferencia solo de plataforma o lenguaje se registra como EQUIVALENTE")
        if not porque:
            raise ValueError("una regla que no es IGUAL exige --porque (por que difiere y por que es o no la misma regla)")
        if not medido:
            raise ValueError("una regla que no es IGUAL exige --medido con las cifras que la sostienen")
        if resultado == "EQUIVALENTE" and no_medido:
            raise ValueError("EQUIVALENTE exige que todo este medido: mide lo que falta antes de registrarla")
        if clase == "FUENTE" or evidencia_fuente:
            ev = L.leer(trabajo, evidencia_fuente) if evidencia_fuente else None
            if not ev:
                raise ValueError("una diferencia de fuente exige --evidencia-fuente (pc fuente medir: contenido, linaje y frescura)")
            if resultado == "EQUIVALENTE" and not ev.get("completa"):
                raise ValueError("la evidencia de fuente no esta completa: " + " · ".join(ev.get("falta") or []))
            no_medido = no_medido or ("; ".join(ev.get("falta") or []) or None)
    if not L.leer(trabajo, f"codigo/{flujo}/fuente.json"):
        raise ValueError("primero: pc codigo bajar (la revision cita la version de Stratio y el zip de Fabric descargados)")
    r = revision(trabajo, flujo)
    rid = rid or f"R{len(r['reglas']) + 1}"
    r["reglas"] = [x for x in r["reglas"] if x["id"] != rid] + [{
        "id": rid, "regla": texto, "stratio": stratio, "fabric": fabric, "resultado": resultado, "impacto": impacto,
        "clase": clase if resultado != "IGUAL" else None, "porque": porque,
        "medido": medido, "no_medido": no_medido, "evidencia_fuente": evidencia_fuente,
        "propuesta": PROPUESTA.get(clase) if resultado != "IGUAL" else None,
        "registrado_por": L.usuario(), "registrado_utc": _ahora()}]
    r["reglas"].sort(key=lambda x: int(x["id"][1:]) if x["id"][1:].isdigit() else 0)
    r["veredicto"] = None                       # cualquier cambio reabre la revision
    L.guardar(trabajo, f"codigo/{flujo}/revision.json", r)
    L.bitacora(trabajo, "revisor-codigo", "regla", {"id": rid, "resultado": resultado, "clase": clase}, flujo=flujo,
               estado="OK" if resultado in ("IGUAL", "EQUIVALENTE") else "AVISO")
    return r


def cerrar(trabajo, flujo, veredicto, resumen):
    assert veredicto in VEREDICTOS, veredicto
    r = revision(trabajo, flujo)
    if not r["reglas"]:
        raise ValueError("no hay reglas registradas: una revision sin reglas no se cierra")
    distintas = [x["id"] for x in r["reglas"] if not es_igual(x)]
    if veredicto == "IGUAL" and distintas:
        raise ValueError(f"no puede cerrar IGUAL con reglas distintas o en un solo lado: {distintas}")
    if veredicto == "CON_DIFERENCIAS" and not distintas:
        raise ValueError("CON_DIFERENCIAS exige al menos una regla DISTINTA, SOLO_STRATIO o SOLO_FABRIC")
    fu = L.leer(trabajo, f"codigo/{flujo}/fuente.json") or {}
    r.update(veredicto=veredicto, resumen=resumen, reglas_distintas=distintas,
             version_stratio=(fu.get("stratio") or {}).get("version"), zip_fabric=(fu.get("fabric") or {}).get("zip"),
             cerrado_por=L.usuario(), cerrado_utc=_ahora())
    L.guardar(trabajo, f"codigo/{flujo}/revision.json", r)
    L.bitacora(trabajo, "revisor-codigo", "cerrar", {"veredicto": veredicto, "distintas": distintas}, flujo=flujo,
               estado="OK" if veredicto == "IGUAL" else "AVISO")
    actualizar_cotejo(trabajo, flujo)      # la misma vN del cotejo de flujo queda con la revision vigente
    return r


def estado(trabajo):
    out = []
    for f in (L.leer(trabajo, "lote.json") or {}).get("flujos", []):
        n = f["nombre_fabric"]
        fu = L.leer(trabajo, f"codigo/{n}/fuente.json")
        r = L.leer(trabajo, f"codigo/{n}/revision.json")
        out.append({"flujo": n, "stratio": f.get("nombre_stratio"), "version_stratio": f.get("version_stratio"),
                    "bajado": bool(fu), "version_bajada": ((fu or {}).get("stratio") or {}).get("version"),
                    "fabric_zip": ((fu or {}).get("fabric") or {}).get("zip"),
                    "reglas": len((r or {}).get("reglas", [])), "veredicto": (r or {}).get("veredicto"),
                    "distintas": (r or {}).get("reglas_distintas") or [x["id"] for x in (r or {}).get("reglas", [])
                                                                       if not es_igual(x)]})
    return out


def aviso_semaforo(trabajo, flujo):
    """Avisos del semaforo por la revision de codigo (nunca ROJO solo: la regla distinta la confirma una persona)."""
    r = L.leer(trabajo, f"codigo/{flujo}/revision.json")
    if not r or not r.get("veredicto"):
        return ["revision de codigo Stratio <-> Fabric sin cerrar: sin ella no se puede clasificar una diferencia como dato"]
    if r["veredicto"] == "CON_DIFERENCIAS":
        reglas = {g["id"]: g for g in r["reglas"]}
        dev = [i for i in r["reglas_distintas"] if (reglas.get(i) or {}).get("decision") == "DEVOLVER"]
        logica = [i for i in r["reglas_distintas"] if (reglas.get(i) or {}).get("clase") == "LOGICA"
                  and (reglas.get(i) or {}).get("decision") in (None, "PENDIENTE")]
        pend = [i for i in r["reglas_distintas"] if (reglas.get(i) or {}).get("decision") in (None, "PENDIENTE")]
        if dev:
            return [f"reglas de negocio desalineadas a devolver a desarrollo ({', '.join(dev)})"]
        if logica:
            return [f"lógica de negocio distinta entre Stratio y Fabric ({', '.join(logica)}: join, filtro o cálculo): "
                    "grave; se propone devolver a desarrollo y lo confirma una persona"]
        if pend:
            return [f"regla de negocio distinta entre Stratio y Fabric ({', '.join(pend)}): si se confirma es "
                    "error del flujo y se devuelve a desarrollo; si se aclara, se registra con pc codigo comentar"]
    return []


# ----------------------------------------------------------------- revision_codigo en el cotejo de flujo (M-019)
DECISIONES_REGLA = ("ACEPTADA", "DEVOLVER", "PENDIENTE")


def comentar(trabajo, flujo, rid, decision, comentario, verificado_qa=None, por=None):
    """Comentario y decision sobre una regla que no es IGUAL (respuesta de desarrollo, verificacion de QA, aceptacion).
    No reabre la revision: deja el historial en la regla y actualiza el cotejo de flujo de la MISMA version."""
    assert decision in DECISIONES_REGLA, decision
    r = revision(trabajo, flujo)
    x = next((g for g in r["reglas"] if g["id"] == rid), None)
    if not x:
        raise ValueError(f"{flujo}: no existe la regla {rid}")
    if decision == "ACEPTADA" and x.get("no_medido"):
        raise ValueError(f"no se acepta con algo sin medir: {x['no_medido']}")
    c = {"decision": decision, "comentario": comentario, "verificado_qa": verificado_qa,
         "por": por or L.usuario(), "utc": _ahora()}
    x.setdefault("comentarios", []).append(c)
    x["decision"] = decision
    L.guardar(trabajo, f"codigo/{flujo}/revision.json", r)
    L.bitacora(trabajo, "revisor-codigo", "comentar", {"id": rid, "decision": decision}, flujo=flujo,
               estado="OK" if decision == "ACEPTADA" else "AVISO")
    actualizar_cotejo(trabajo, flujo)
    return x


def para_cotejo(trabajo, flujo):
    """La llave `revision_codigo` del cotejo de flujo: version de Stratio y zip revisados, conteo de reglas, cada regla
    que no es IGUAL con la cita de los dos lados, su impacto, decision y comentarios, y si bloquea las fases siguientes."""
    fu = L.leer(trabajo, f"codigo/{flujo}/fuente.json")
    r = L.leer(trabajo, f"codigo/{flujo}/revision.json")
    if not fu and not r:
        return {"estado": "SIN_REVISION", "bloquea": False,
                "nota": "sin revision de codigo registrada en este trabajo; no se evaluo («no se evaluo» no es «cumple»)"}
    r = r or {"reglas": []}
    st, fb = (fu or {}).get("stratio") or {}, (fu or {}).get("fabric") or {}
    no_ig = [g for g in r["reglas"] if not es_igual(g)]
    equiv = [g for g in r["reglas"] if g["resultado"] == "EQUIVALENTE"]
    devolver = [g["id"] for g in no_ig if g.get("decision") == "DEVOLVER"]
    pendientes = [g["id"] for g in no_ig if g.get("decision") in (None, "PENDIENTE")]
    estado = ("ABIERTA" if not r.get("veredicto") else r["veredicto"])
    return {
        "estado": estado,
        "bloquea": bool(devolver),
        "por_que_bloquea": (f"reglas a devolver a desarrollo: {', '.join(devolver)}" if devolver else None),
        "aclaraciones_pendientes": pendientes,
        "stratio": {"workflow": (fu or {}).get("nombre_stratio") or st.get("nombre"), "version": st.get("version"),
                    "actualizado": st.get("actualizado"), "es_la_mas_reciente": st.get("es_la_mas_reciente"),
                    "sha256": st.get("sha256")},
        "fabric": {"zip": fb.get("zip"), "modificado": fb.get("modificado"), "sha256": fb.get("sha256")},
        "reglas": {"total": len(r["reglas"]), "igual": len(r["reglas"]) - len(no_ig) - len(equiv),
                   "equivalente": len(equiv), "no_igual": len(no_ig)},
        "reglas_equivalentes": [{"id": g["id"], "regla": g["regla"], "porque": g.get("porque"),
                                 "stratio": g["stratio"], "fabric": g["fabric"]} for g in equiv],
        "reglas_no_iguales": [{"id": g["id"], "regla": g["regla"], "resultado": g["resultado"], "clase": g.get("clase"),
                               "porque": g.get("porque"), "propuesta": g.get("propuesta"), "impacto": g.get("impacto"),
                               "stratio": g["stratio"], "fabric": g["fabric"], "decision": g.get("decision") or "PENDIENTE",
                               "comentarios": g.get("comentarios") or []} for g in no_ig],
        "resumen": r.get("resumen"), "cerrado_por": r.get("cerrado_por"), "cerrado_utc": r.get("cerrado_utc"),
        "actualizado_utc": _ahora(),
    }


def actualizar_cotejo(trabajo, flujo, publicar=False):
    """Escribe `revision_codigo` en el cotejo de flujo local de la version vigente (la misma vN: aclarar el codigo no
    re-ejecuta nada) y, con publicar=True, lo reescribe en sitio en OneLake con HEAD. None si aun no hay cotejo."""
    rel = f"v4/flujos/{flujo}.json"
    doc = L.leer(trabajo, rel)
    if not doc:
        return None
    ant = doc.get("revision_codigo") or {}
    nuevo = para_cotejo(trabajo, flujo)
    hist = list(ant.get("historial") or [])
    if ant and {k: v for k, v in ant.items() if k not in ("historial", "actualizado_utc")} != \
            {k: v for k, v in nuevo.items() if k != "actualizado_utc"}:
        hist.append({"utc": nuevo["actualizado_utc"], "por": L.usuario(), "estado_anterior": ant.get("estado"),
                     "estado": nuevo["estado"], "bloqueaba": ant.get("bloquea"), "bloquea": nuevo["bloquea"],
                     "pendientes_antes": ant.get("aclaraciones_pendientes"), "pendientes": nuevo["aclaraciones_pendientes"]})
    nuevo["historial"] = hist
    doc["revision_codigo"] = nuevo
    doc.setdefault("encabezado", {})["revision_codigo_actualizada_utc"] = nuevo["actualizado_utc"]
    L.guardar(trabajo, rel, doc)
    out = {"flujo": flujo, "estado": nuevo["estado"], "bloquea": nuevo["bloquea"], "local": rel}
    if publicar:
        from .reportes import v4 as V4
        datos = json.dumps(doc, ensure_ascii=False, indent=1).encode("utf8")
        dest = V4.ruta_ol("cotejo_flujo", flujo, V4.version(trabajo, flujo), pruebas=V4._pruebas(trabajo))
        ol.escribir(dest, datos)
        h = ol.head(dest)
        out.update(publicado=dest, head_ok=bool(h) and h["bytes"] == len(datos))
        pub = L.leer(trabajo, "v4/publicado.json", {}) or {}
        pub.setdefault("archivos", []).append({"ruta": dest, "head_ok": out["head_ok"], "tipo": "cotejo_flujo",
                                               "version": V4.version(trabajo, flujo), "motivo": "revision_codigo",
                                               "utc": nuevo["actualizado_utc"]})
        L.guardar(trabajo, "v4/publicado.json", pub)
    L.bitacora(trabajo, "revisor-codigo", "cotejo_flujo", out, flujo=flujo)
    return out
