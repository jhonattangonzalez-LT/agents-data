"""Revision del codigo de los dos lados: el workflow de Stratio (Rocket) contra el flujo de Fabric (zip en OneLake).

Corre al comienzo, en paralelo a los niveles 0/1 y 2. Sirve para clasificar las diferencias del dato:
  regla igual en los dos lados  -> la diferencia es de dato (insumo, corte, fecha del dia o formato): justificable
  regla distinta                -> error del flujo: se devuelve a desarrollo (lo confirma una persona)

  bajar     baja el codigo: la VERSION de Stratio la da el usuario (nunca se supone la ultima); sin version, lista las
            versiones del workflow y se detiene. Guarda codigo/<flujo>/fuente.json (nombres, version, fechas, huellas),
            el JSON de Rocket y su texto por nodo, y el zip de Fabric extraido con su texto por paso.
  regla     registra una regla de negocio comparada (stratio: nodo y extracto · fabric: archivo y extracto · resultado)
  cerrar    cierra la revision: IGUAL (todas las reglas iguales) o CON_DIFERENCIAS (alguna DISTINTA o en un solo lado)
  estado    resumen por flujo del trabajo

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

RESULTADOS = ("IGUAL", "DISTINTA", "SOLO_STRATIO", "SOLO_FABRIC")
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


def regla(trabajo, flujo, texto, stratio, fabric, resultado, impacto=None, rid=None):
    """Registra (o corrige, con el mismo id) una regla de negocio comparada en los dos lados."""
    assert resultado in RESULTADOS, resultado
    if not L.leer(trabajo, f"codigo/{flujo}/fuente.json"):
        raise ValueError("primero: pc codigo bajar (la revision cita la version de Stratio y el zip de Fabric descargados)")
    r = revision(trabajo, flujo)
    rid = rid or f"R{len(r['reglas']) + 1}"
    r["reglas"] = [x for x in r["reglas"] if x["id"] != rid] + [{
        "id": rid, "regla": texto, "stratio": stratio, "fabric": fabric, "resultado": resultado, "impacto": impacto,
        "registrado_por": L.usuario(), "registrado_utc": _ahora()}]
    r["reglas"].sort(key=lambda x: int(x["id"][1:]) if x["id"][1:].isdigit() else 0)
    r["veredicto"] = None                       # cualquier cambio reabre la revision
    L.guardar(trabajo, f"codigo/{flujo}/revision.json", r)
    L.bitacora(trabajo, "revisor-codigo", "regla", {"id": rid, "resultado": resultado}, flujo=flujo,
               estado="OK" if resultado == "IGUAL" else "AVISO")
    return r


def cerrar(trabajo, flujo, veredicto, resumen):
    assert veredicto in VEREDICTOS, veredicto
    r = revision(trabajo, flujo)
    if not r["reglas"]:
        raise ValueError("no hay reglas registradas: una revision sin reglas no se cierra")
    distintas = [x["id"] for x in r["reglas"] if x["resultado"] != "IGUAL"]
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
                                                                       if x["resultado"] != "IGUAL"]})
    return out


def aviso_semaforo(trabajo, flujo):
    """Avisos del semaforo por la revision de codigo (nunca ROJO solo: la regla distinta la confirma una persona)."""
    r = L.leer(trabajo, f"codigo/{flujo}/revision.json")
    if not r or not r.get("veredicto"):
        return ["revision de codigo Stratio <-> Fabric sin cerrar: sin ella no se puede clasificar una diferencia como dato"]
    if r["veredicto"] == "CON_DIFERENCIAS":
        return [f"regla de negocio distinta entre Stratio y Fabric ({', '.join(r['reglas_distintas'])}): si se confirma es "
                "error del flujo y se devuelve a desarrollo"]
    return []
