"""Dependencias REALES de un flujo: quien escribe cada una de sus entradas y si va en cascada con el.

  python -m pc dependencias --trabajo T [--flujo F] [--refrescar]   -> etl/dependencias/<F>.json (lo cita la evidencia
                                                                       del ETL y el cotejo de flujo; el acta lo lee de ahi)

Antes el cotejo de flujo solo veia la cadena del orquestador de ESA corrida: 229 de 241 cotejos de analitica decian
«sin dependencias» aunque sus entradas las escribe otro flujo. Ahora se mide sobre las definiciones de Fabric:

  DIRECTA    el flujo que escribe una entrada va en la MISMA cascada: un orquestador invoca a los dos y el productor
             corre antes (dependsOn, transitivo). Se ejecutan si o si juntos, en ese orden.
  INDIRECTA  el flujo que escribe una entrada corre por su cuenta (otra programacion u otro orquestador): alimenta la
             entrada, pero no se dispara con este flujo.
  SIN PRODUCTOR  ninguna copia ni flujo de los workspaces de QA escribe la entrada (copia manual u origen externo):
             se dice asi, nunca «sin dependencias».

Quien escribe sale del CODIGO, no del nombre de la bandera: en analitica, las banderas de salida segun el zip del flujo
(load.py, pc.inventario.roles) con el valor que les da la Variable Library; en ingesta, el destino (sink) de cada Copy.
«Sin dependencias» solo se escribe cuando el flujo no tiene entradas del lakehouse o ninguna la escribe otro flujo y
todas tienen origen identificado.

Indice: ~/.cache/pc/dependencias/indice.json (un dia; --refrescar lo rehace). Lee definiciones con la cache de
pc.fuente (8 hilos) y los zips de Files/assets/flows (cache por lastModified).
"""
import datetime
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from .. import lote as L
from ..config import FAB, PAR

CACHE = os.path.join(os.path.expanduser("~"), ".cache", "pc", "dependencias")
WSS = ("ws_datalake", "ws_ingesta", "ws_orquestacion")
_TOK = re.compile(r"'((?:[^']|'')*)'|pipeline\(\)\.libraryVariables\.(\w+)|pipeline\(\)\.parameters\.(\w+)")


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def norm(r):
    """Una sola forma para comparar rutas: files/… sin barra final, tablas esquema.tabla, en minusculas."""
    if not r:
        return None
    r = str(r).strip().strip("'\"").replace("\\", "/")
    m = re.search(r"/(Files|Tables)/(.+)$", r)
    if m and "://" in r:
        r = f"{m.group(1)}/{m.group(2)}"
    r = r.rstrip("/.").lower()          # el validador a veces deja un punto final («gold.tabla.»)
    if r.startswith("tables/"):
        r = r[7:].replace("/", ".", 1)
    if r.startswith("files/"):
        r = r[6:]
    if r.startswith("/"):
        r = r[1:]
    return r or None


def _coincide(entrada, escrita):
    e, w = norm(entrada), norm(escrita)
    if not e or not w:
        return False
    return e == w or w.startswith(e + "/") or e.startswith(w + "/")


# ------------------------------------------------------------------ definiciones
def _bibliotecas():
    """{libreria: {variable: valor}} de todas las Variable Library (valor por defecto)."""
    from ..fuente import _definiciones
    out = {}
    for w in WSS:
        ws = FAB.get(w)
        if not ws:
            continue
        for it, txt in _definiciones(ws, "VariableLibrary"):
            vs = out.setdefault(it["displayName"], {})
            for m in re.finditer(r'"name"\s*:\s*"([^"]+)"(?:(?!"name").)*?"value"\s*:\s*"([^"]*)"', txt or "", re.S):
                vs.setdefault(m.group(1), m.group(2))
    return out


def _resolver(expr, decl, libs):
    """Texto de una expresion de pipeline con las variables de biblioteca sustituidas (lo que no se resuelve: {param})."""
    if isinstance(expr, dict):
        expr = expr.get("value")
    if expr is None:
        return None
    expr = str(expr)
    if not expr.startswith("@"):
        return expr
    partes = []
    for m in _TOK.finditer(expr):
        if m.group(1) is not None:
            partes.append(m.group(1).replace("''", "'"))
        elif m.group(2):
            d = decl.get(m.group(2)) or {}
            v = (libs.get(d.get("libraryName")) or {}).get(d.get("variableName") or m.group(2))
            partes.append(v if v is not None else "{" + m.group(2) + "}")
        else:
            partes.append("{" + m.group(3) + "}")
    if "split(" in expr and len(partes) == 1:          # @split(variable,'.')[0] → esquema.tabla completo
        return partes[0]
    return "".join(partes)


def _ubicacion(ds, decl, libs):
    """Ruta (Files/…) o tabla (esquema.tabla) de un dataset de Copy (origen o destino)."""
    ds = ds or {}
    tp = (ds.get("datasetSettings") or {}).get("typeProperties") or ds.get("typeProperties") or {}
    loc = tp.get("location") or {}
    if loc:
        carpeta = _resolver(loc.get("folderPath"), decl, libs) or ""
        archivo = _resolver(loc.get("fileName"), decl, libs) or ""
        raiz = ((ds.get("datasetSettings") or {}).get("linkedService") or {}).get("properties", {}).get("typeProperties", {}).get("rootFolder") or ""
        r = "/".join(x.strip("/") for x in (raiz, carpeta, archivo) if x and x.strip("/"))
        return r or None
    esq = _resolver(tp.get("schema"), decl, libs)
    tab = _resolver(tp.get("table") or tp.get("tableName"), decl, libs)
    if tab and esq and esq != tab and "." not in tab:
        return f"{esq}.{tab}"
    return tab or esq


def _actividades(pj):
    from ..fuente import _actividades as act
    return act(pj)


def _args(texto):
    """--bandera valor … → {bandera: valor}."""
    out, k = {}, None
    for t in (texto or "").split():
        if t.startswith("--"):
            k = t[2:]
            out[k] = None
        elif k and out.get(k) is None:
            out[k] = t
    return out


def _roles_zips(zips):
    """{zip: roles del codigo} con cache por lastModified."""
    from ..acceso import onelake as ol
    from ..inventario.roles import leer_zip, roles_desde_zip
    os.makedirs(os.path.join(CACHE, "zips"), exist_ok=True)
    lista = {p["name"]: p for p in ol.listar(FAB["assets_flujos"], True) if p["name"].endswith(".zip")}

    def uno(z):
        p = lista.get(z)
        if not p:
            return z, None
        cache = os.path.join(CACHE, "zips", re.sub(r"[^\w.-]", "_", z) + ".json")
        if os.path.exists(cache):
            d = json.load(open(cache))
            if d.get("lastModified") == p["lastModified"]:
                return z, d["roles"]
        try:
            r = roles_desde_zip(leer_zip(z))
        except Exception as e:
            return z, {"error": f"{type(e).__name__}: {str(e)[:120]}"}
        json.dump({"lastModified": p["lastModified"], "roles": r}, open(cache, "w"))
        return z, r
    with ThreadPoolExecutor(PAR["onelake_hilos"]) as ex:
        return dict(ex.map(uno, sorted(set(zips))))


def construir(refrescar=False, avisar=print):
    p = os.path.join(CACHE, "indice.json")
    if not refrescar and os.path.exists(p) and time.time() - os.path.getmtime(p) < 86400:
        return json.load(open(p))
    from ..fuente import _definiciones
    from ..inventario.roles import NO_RUTA, bandera
    os.makedirs(CACHE, exist_ok=True)
    t0 = time.time()
    libs = _bibliotecas()
    pipes, spark = {}, []
    for w in WSS:
        ws = FAB.get(w)
        if not ws:
            continue
        for it, txt in _definiciones(ws):
            try:
                pj = json.loads(txt) if txt else {}
            except ValueError:
                continue
            decl = (pj.get("properties") or {}).get("libraryVariables") or {}
            x = {"nombre": it["displayName"], "ws": w, "escribe": [], "lee": [], "sin_rol": [], "zips": [], "copias": [], "invoca": []}
            acts = _actividades(pj)
            por_nombre = {a.get("name"): a for a in acts}
            for a in acts:
                tp = a.get("typeProperties") or {}
                if a.get("type") == "Copy":
                    o, d = _ubicacion(tp.get("source"), decl, libs), _ubicacion(tp.get("sink"), decl, libs)
                    if d:
                        x["escribe"].append({"ruta": d, "via": f"copia «{a.get('name')}»", "origen": o})
                    if o:
                        x["lee"].append({"ruta": o, "via": f"copia «{a.get('name')}»"})
                    x["copias"].append({"actividad": a.get("name"), "origen": o, "destino": d})
                elif a.get("type") in ("FabricSparkJobDefinition", "SparkJobDefinition"):
                    args = _args(_resolver(tp.get("commandLineArguments"), decl, libs))
                    z = args.pop("flow-code-zip", None)
                    z = ("Files/" + z.split("/Files/", 1)[1]) if z and "/Files/" in z else z
                    if z:
                        x["zips"].append(z)
                        spark.append((it["id"], z, args, a.get("name")))
                elif a.get("type") in ("InvokePipeline", "ExecutePipeline"):
                    # quien corre antes de esta actividad dentro del orquestador (dependsOn, transitivo)
                    antes, pila = set(), [d_["activity"] for d_ in a.get("dependsOn") or []]
                    while pila:
                        n = pila.pop()
                        if n in antes:
                            continue
                        antes.add(n)
                        pila += [d_["activity"] for d_ in (por_nombre.get(n) or {}).get("dependsOn") or []]
                    x["invoca"].append({"actividad": a.get("name"), "pipeline_id": tp.get("pipelineId"),
                                        "antes": sorted(antes)})
            pipes[it["id"]] = x
    avisar(f"dependencias: {len(pipes)} pipelines leídos; roles por código de {len(set(z for _, z, _, _ in spark))} zips…")
    roles = _roles_zips([z for _, z, _, _ in spark])
    for pid, z, args, act in spark:
        r = roles.get(z) or {}
        if not r or r.get("error"):
            pipes[pid]["sin_rol"] += [{"bandera": k, "ruta": v, "motivo": (r or {}).get("error") or "zip no encontrado"} for k, v in args.items()]
            continue
        sal = {bandera(p) for p in r.get("salidas", []) + r.get("lee_y_escribe", [])}
        ent = {bandera(p) for p in r.get("entradas", []) + r.get("lee_y_escribe", [])}
        for k, v in args.items():
            if not v or v.startswith("{"):
                continue
            if k in sal:
                pipes[pid]["escribe"].append({"ruta": v, "via": f"código del flujo ({z.rsplit('/', 1)[-1]}, --{k})"})
            if k in ent:
                pipes[pid]["lee"].append({"ruta": v, "via": f"código del flujo ({z.rsplit('/', 1)[-1]}, --{k})"})
            if k not in sal and k not in ent and ("/" in v or "." in v) and not NO_RUTA.search(k.replace("-", "_")):
                pipes[pid]["sin_rol"].append({"bandera": k, "ruta": v, "motivo": "el código del zip no usa esta bandera ni en extract ni en load"})
    # quien invoca a quien
    invocado = {}
    for oid, x in pipes.items():
        for inv in x["invoca"]:
            antes_ids = [i["pipeline_id"] for i in x["invoca"] if i["actividad"] in inv["antes"]]
            invocado.setdefault(inv["pipeline_id"], []).append({"orquestador_id": oid, "orquestador": x["nombre"],
                                                                "actividad": inv["actividad"], "antes": antes_ids})
    doc = {"generado_utc": _ahora(), "segundos": round(time.time() - t0, 1), "pipelines": pipes, "invocado_por": invocado}
    json.dump(doc, open(p, "w"), ensure_ascii=False)
    return doc


def _tipo(x):
    return "ingesta" if x["ws"] == "ws_ingesta" else "orquestación" if x["invoca"] and not x["zips"] else "analítica"


def de_flujo(nombre, entradas, salidas=None, idx=None):
    """Directas, indirectas, sin productor y aguas abajo de un flujo (por nombre del pipeline en Fabric)."""
    idx = idx or construir()
    P = idx["pipelines"]
    propios = [pid for pid, x in P.items() if x["nombre"].lower() == nombre.lower()]
    ent = list(dict.fromkeys(e.rstrip(".") for e in entradas or [] if e))
    for pid in propios:                       # lo que el codigo del propio flujo lee, aunque el validador no lo citara
        for r in P[pid]["lee"]:
            if not any(_coincide(e, r["ruta"]) for e in ent):
                ent.append(r["ruta"].rstrip("."))
    sal = list(salidas or []) + [r["ruta"] for pid in propios for r in P[pid]["escribe"]]
    orq = [o for pid in propios for o in idx["invocado_por"].get(pid, [])]
    cascada = {i: o["orquestador"] for o in orq for i in o["antes"]}
    directas, indirectas, sin_prod, origen = [], [], [], []
    # una expresion del pipeline sin resolver (@{concat(...)}) no es una ruta: no se cuenta como entrada sin productor
    no_resueltas = [e for e in ent if "@{" in e or e.startswith("@")]
    ent = [e for e in ent if e not in no_resueltas]
    propias = [e for e in ent if any(_coincide(e, s_) for s_ in sal)]     # lee su propia salida (incremental): no es dependencia
    ent = [e for e in ent if e not in propias]
    for e in ent:
        prod = [(pid, x, r) for pid, x in P.items() if pid not in propios for r in x["escribe"] if _coincide(e, r["ruta"])]
        if not prod:
            (origen if not (norm(e) or "").startswith(("bronze", "silver", "gold", "landing", "trusted", "raw")) and "." not in (norm(e) or "")
             else sin_prod).append(e)
            continue
        for pid, x, r in prod:
            fila = {"flujo": x["nombre"], "tipo": _tipo(x), "entrada": e, "escrita_por": r["via"]}
            if pid in cascada:
                directas.append(dict(fila, orquestador=cascada[pid]))
            else:
                otros_orq = sorted({o["orquestador"] for o in idx["invocado_por"].get(pid, [])})
                indirectas.append(dict(fila, **({"lo_ejecuta": otros_orq} if otros_orq else {})))
    abajo = sorted({x["nombre"] for pid, x in P.items() if pid not in propios
                    for r in x["lee"] for s in sal if _coincide(s, r["ruta"])})
    uniq = lambda xs: sorted({d["flujo"] for d in xs})
    partes = []
    if directas:
        partes.append(f"directas (en cascada con {', '.join(sorted({d['orquestador'] for d in directas}))}): " + ", ".join(uniq(directas)))
    if indirectas:
        partes.append("indirectas (alimentan sus entradas): " + ", ".join(
            f"{n} ({next(d['tipo'] for d in indirectas if d['flujo'] == n)})" for n in uniq(indirectas)))
    if sin_prod:
        partes.append(f"{len(sin_prod)} entrada(s) sin flujo productor en QA (ningún pipeline la escribe: copia manual u origen externo): " + ", ".join(sin_prod[:4])
                      + (" …" if len(sin_prod) > 4 else ""))
    sin_codigo = [pid for pid in propios if P[pid]["zips"] and not P[pid]["lee"] and not P[pid]["escribe"]]
    estado = "MEDIDO"
    if not propios:
        estado, partes = "NO_MEDIDO", [f"dependencias no medidas: no se encontró el pipeline «{nombre}» en los workspaces de QA "
                                       "(pasar el nombre real con item_fabric en el lote)"] + partes
    elif not partes and (sin_codigo or (not ent and not any(P[pid]["zips"] or P[pid]["copias"] for pid in propios))):
        estado, partes = "NO_MEDIDO", ["dependencias no medidas: no se pudo leer qué entradas usa el código del flujo"]
    if not partes:
        partes.append("sin dependencias de otros flujos: " + ("lee solo el origen externo (" + ", ".join(origen[:3]) + ")" if origen
                                                              else "no lee tablas del lakehouse"))
    if orq and not directas:
        partes.append("lo invoca " + ", ".join(sorted({o["orquestador"] for o in orq})))
    return {"medido_utc": _ahora(), "indice_utc": idx["generado_utc"], "flujo": nombre, "estado": estado, "pipeline_encontrado": bool(propios),
            "orquestadores": [{"orquestador": o["orquestador"], "actividad": o["actividad"]} for o in orq],
            "directas": directas, "indirectas": indirectas, "entradas_sin_productor": sin_prod, "entradas_de_origen_externo": origen,
            "entradas_no_resueltas": no_resueltas,
            "que_dependen_de_este": abajo, "entradas_evaluadas": ent, "lee_su_propia_salida": propias,
            "sin_rol": [r for pid in propios for r in P[pid]["sin_rol"]],
            "resumen": " · ".join(partes),
            "criterio": "directa: el productor va en la misma cascada (un orquestador invoca a los dos y el productor corre antes); "
                        "indirecta: el productor alimenta la entrada pero corre por su cuenta; productor por el código del zip "
                        "(load.py) o por el destino de una Copy, nunca por el nombre de la bandera"}


def medir(trabajo, flujo, refrescar=False):
    f = L.flujo(trabajo, flujo)
    if not f:
        raise KeyError(flujo)
    ev = L.leer(trabajo, f"etl/evidencia/{flujo}.json") or {}
    etl = L.veredicto_etl(trabajo, f) or {}
    corr = (etl.get("inventario") or {}).get("correccion") or {}
    ent = [e.get("entrada") for e in ev.get("entradas") or [] if e.get("entrada")] or \
          [x["ruta"] for x in corr.get("entradas") or [] if x.get("ruta")] or list((etl.get("resumen") or {}).get("entradas") or [])
    sal = [(o.get("fabric") or {}).get("ruta") for o in f["objetos"] if (o.get("fabric") or {}).get("ruta")]
    d = de_flujo(L.item_fabric(f), ent, sal, construir(refrescar))
    L.guardar(trabajo, f"etl/dependencias/{flujo}.json", d)
    L.bitacora(trabajo, "etl-validador", "medir_dependencias", {"directas": len(d["directas"]), "indirectas": len(d["indirectas"]),
               "sin_productor": len(d["entradas_sin_productor"])}, flujo=flujo)
    return d
