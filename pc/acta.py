"""Acta de entrega en el FORMATO NORMALIZADO (el del agente acta-entrega, 2026-10-22), para todo el equipo.

  python -m pc acta generar --lote N --exitosos <carpeta o EXITOSOS_*.md> [--version 1.0] [--fecha AAAA-MM-DD]
  python -m pc acta generar --lote N [--trabajos T1,T2]
  python -m pc acta capa --lote N --clave <tabla o flujo> --capa "Silver"     respuesta a una capa ambigua

De dónde salen los flujos:
  · con lotes/<N>/lote.json (lote armado con `pc lote armar`): sus expedientes, y solo con las 3 compuertas aprobadas
    y por el responsable del acta (como siempre);
  · con --exitosos (o --trabajos): los EXITOSOS_<T>.md que los QA ya generaron y le pasan al responsable del acta, de
    cualquier equipo. Entran todos (son flujos exitosos); solo no se repite un flujo que venga en dos.
El dato se lee de los reportes v4 que cita cada EXITOSOS (copia local del trabajo si es la misma versión; si no, de
OneLake a lotes/<N>/acta/evidencia/) con pc/docx/lector_formato2.py;
el .docx lo dibuja pc/docx/acta_normalizada.py (copia del generador de qa-etl-validador-agent-v2/actas, con capas
medallón, dependencias medidas, gráficas completas, CP-05 con motivo, punto 7 resumido y punto 8 sin firmas).
Nada detiene el acta: pc/revisor_acta.py revisa cada JSON citado (HEAD 200, enlace correcto y vigente, nada pendiente)
y deja advertencias.json y un mensaje por QA (mensajes/<trabajo>.md) para corregir sobre ese mismo enlace. Solo la capa
que no se puede fijar se pregunta (en el acta sale «por confirmar»; `pc acta capa`).
Todo queda local en lotes/<N>/acta/ (el acta nunca se publica).
"""
import datetime
import glob
import json
import os
import re
import shutil
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from . import lote as T
from . import lote_final as LF
from .acceso import onelake as ol
from . import revisor_acta as RV
from .config import RAIZ

DOCX = os.path.join(RAIZ, "pc", "docx")
CFG = json.load(open(os.path.join(RAIZ, "config", "acta.json"), encoding="utf8"))
GRUPO = {"ingesta": "ingesta", "analitica": "analitica", "orquestador": "orquestadores", "orquestadores": "orquestadores"}


def _mods():
    if DOCX not in sys.path:
        sys.path.insert(0, DOCX)
    import acta_normalizada as GN
    import capas as CAPAS
    import lector_formato2 as F2
    return GN, CAPAS, F2


def leer_md(p):
    """Un EXITOSOS (cierre-v1): su lista de flujos y las rutas de OneLake que cita."""
    s = open(p, encoding="utf8").read().replace("\r\n", "\n")      # llegado por correo o chat desde Windows
    if not s.startswith("---\n") or "\n---\n" not in s[4:]:
        raise ValueError(f"{p}: no es un cierre-v1 (sin front-matter)")
    fm, cuerpo = s[4:].split("\n---\n", 1)
    g = lambda k: (re.search(rf'^{k}:\s*"?([^"\n]*)"?', fm, re.M) or [None, None])[1]
    flujos = [dict(re.findall(r'(\w+): "?([^",}]*)"?', ln)) for ln in fm.splitlines() if ln.strip().startswith("- {flujo")]
    return {"ruta": p, "formato": g("formato"), "tipo": g("tipo"), "trabajo": g("trabajo"), "generado_utc": g("generado_utc"),
            "generado_por": g("generado_por"), "flujos": flujos,
            "rutas": [urllib.parse.unquote(x) for x in re.findall(r"selectedPath=([^&)\s]+)", cuerpo)]}


def _mds(rutas):
    """Archivos o carpetas (se buscan los EXITOSOS_*.md adentro, en cualquier nivel)."""
    out = []
    for r in rutas:
        r = os.path.expanduser(r)
        if os.path.isdir(r):
            out += sorted(glob.glob(os.path.join(r, "**", "EXITOSOS_*.md"), recursive=True))
        elif os.path.exists(r):
            out.append(r)
        else:
            raise FileNotFoundError(r)
    return list(dict.fromkeys(os.path.abspath(x) for x in out))


def _nom(p):
    return os.path.join(os.path.basename(os.path.dirname(p)), os.path.basename(p))


def cotejar_exitosos(rutas):
    """Junta los EXITOSOS que los QA ya generaron y pasaron al responsable del acta: son flujos exitosos y entran todos,
    sin exigirles nada. Solo se evita repetir un flujo que viene en dos markdowns (se toma la versión mayor).
    Devuelve ([(md, flujo)], avisos, informe)."""
    avisos, inf, elegidos = [], {"exitosos": [], "ignorados": []}, {}
    for p in _mds(rutas):
        try:
            m = leer_md(p)
        except ValueError:                     # sin front-matter no hay lista de flujos que leer
            inf["ignorados"].append(p)
            avisos.append(f"{_nom(p)}: sin front-matter (no trae la lista de flujos): se ignora")
            continue
        inf["exitosos"].append({"ruta": m["ruta"], "trabajo": m["trabajo"], "generado_utc": m["generado_utc"],
                                "generado_por": m["generado_por"], "flujos": len(m["flujos"])})
        for f in m["flujos"]:
            n = f["flujo"]
            if n in elegidos:
                m0, f0 = elegidos[n]
                if int(f["version"] or 0) <= int(f0["version"] or 0):
                    continue
                avisos.append(f"{n}: viene en {_nom(m0['ruta'])} y en {_nom(m['ruta'])}: se toma v{f['version']}")
            elegidos[n] = (m, f)
    return list(elegidos.values()), avisos, inf


def _traer(rel_ol, local_v4, destino):
    """El reporte PUBLICADO (es lo que enlaza el acta y lo que se revisa). Si no se puede leer de OneLake, la copia local
    del trabajo (si este equipo la tiene). Devuelve (doc publicado o local, origen, copia local o None)."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    loc = json.load(open(local_v4, encoding="utf8")) if local_v4 and os.path.exists(local_v4) else None
    try:
        data = ol.leer(rel_ol)
        open(destino, "wb").write(data)
        return json.loads(data), "OneLake", loc
    except Exception:
        if loc is None:
            raise
        shutil.copyfile(local_v4, destino)
        return loc, "local", None


def _flujo(F2, md, fd, evid):
    t, n, ver = md["trabajo"], fd["flujo"], int(fd["version"])
    rutas = md.get("rutas") or []
    from .reportes import v4 as V4

    def cita(patron):
        return next((r for r in rutas if re.search(patron, r)), None)
    rf = cita(rf"/flujos/{re.escape(n)}/cotejo_flujo_{re.escape(n)}_v{ver}\.json$") or V4.ruta_ol("cotejo_flujo", n, ver)
    base = rf.split("/flujos/")[0]
    loc = os.path.join(RAIZ, "trabajos", t, "v4")
    dv4 = os.path.join(evid, t)
    try:
        cf, origen, cf_loc = _traer(rf, os.path.join(loc, "flujos", f"{n}.json"), os.path.join(dv4, "flujos", f"{n}.json"))
    except Exception as x:
        raise LookupError(RV.hallazgo(md, n, None, "Cotejo del flujo", rf, f"no se pudo leer de OneLake ({type(x).__name__}); "
                                      "el flujo no entra al acta hasta que esté publicado", None, ver))
    hall = RV.flujo(md, fd, cf, rf, cf_loc if origen == "OneLake" else None)
    if origen == "local":
        hall.append(RV.hallazgo(md, n, None, "Cotejo del flujo", rf, "no existe en OneLake: el acta usó la copia local del trabajo",
                                None, ver))
    verificado = (cf.get("verificacion") or {}).get("decision") == "APRUEBA"
    flujos_ok = {n, (cf["encabezado"].get("tablas_en") or {}).get("flujo")}
    links, cotejos = {"flujo": rf, "tablas": {}}, {}
    for x in cf.get("tablas") or []:
        k = x["clave"]
        rc = cita(rf"/cotejos/{re.escape(k)}/cotejo_{re.escape(k)}_v\d+\.json$")
        vk = int(re.search(r"_v(\d+)\.json$", rc).group(1)) if rc else ver
        rc = rc or f"{base}/cotejos/{k}/cotejo_{k}_v{vk}.json"
        try:
            co, o2, co_loc = _traer(rc, os.path.join(loc, "cotejos", f"{k}.json"), os.path.join(dv4, "cotejos", f"{k}.json"))
        except Exception as x:
            raise LookupError(RV.hallazgo(md, n, k, "Cotejo Stratio ↔ Fabric", rc, f"no se pudo leer de OneLake ({type(x).__name__}); "
                                          "el flujo no entra al acta hasta que esté publicado", None, vk))
        if o2 == "local":
            hall.append(RV.hallazgo(md, n, k, "Cotejo Stratio ↔ Fabric", rc, "no existe en OneLake: el acta usó la copia local", None, vk))
        elif co_loc and str((co_loc.get("encabezado") or {}).get("version")) == str(vk) and RV.distinto(co_loc, co):
            hall.append(RV.hallazgo(md, n, k, "Cotejo Stratio ↔ Fabric", rc, RV._cambio(RV.distinto(co_loc, co)), None, vk))
        cotejos[k] = (co, rc, vk)
        solo_fabric = (co["encabezado"].get("objeto") or {}).get("stratio") is None
        med = lambda lado: cita(rf"/mediciones/{lado}/{re.escape(k)}/medicion_{lado}_{re.escape(k)}_v\d+\.json$") or \
            f"{base}/mediciones/{lado}/{k}/medicion_{lado}_{k}_v{vk}.json"
        links["tablas"][k] = {"metrica_stratio": None if solo_fabric else med("stratio"), "metrica_fabric": med("fabric"),
                              "cotejo_stratio_fabric": rc}
    try:
        lote_flujo = T.flujo(t, n) or {}
    except Exception:                                      # el trabajo no esta en este equipo: basta el cierre
        lote_flujo = {}
    try:
        f = F2.flujo(dv4, n, links, lote_flujo)
    except (AssertionError, KeyError, TypeError) as x:
        # la evidencia no cuadra entre sí (p. ej. el cotejo de flujo y los de tabla son de versiones distintas): el flujo
        # no se puede dibujar, pero se dice qué enlace revisar
        for k, (co, rc, vk) in cotejos.items():
            hall += RV.cotejo(md, n, k, vk, co, rc, flujos_ok, verificado, None)
        hall.append(RV.hallazgo(md, n, None, "Cotejo del flujo", rf, "el cotejo del flujo y los cotejos de sus tablas no cuadran "
                                f"entre sí ({type(x).__name__} {str(x)[:120]}): el flujo no entra al acta hasta corregirlo", None, ver))
        raise LookupError(hall)
    f["origen_reportes"] = origen
    det = {o["clave"]: o.get("detalle_diferencias") for o in f["objetos"]}
    for k, (co, rc, vk) in cotejos.items():
        hall += RV.cotejo(md, n, k, vk, co, rc, flujos_ok, verificado, det.get(k))
    f["hallazgos"] = hall
    f["grupo"] = GRUPO.get(f["grupo"], f["grupo"])
    if f["grupo"] == "orquestadores" and not f.get("capa"):
        f["capa"], f["capa_motivo"] = "Orquestación", "orquestador: no escribe tablas"
    f["trabajo"], f["avisos"] = t, []
    te = cf["encabezado"].get("tablas_en")
    if te:
        f["tablas_en"] = te
    dm = f["ejecucion"].get("dependencias_medidas") or {}
    loc = T.leer(t, f"etl/dependencias/{n}.json")
    if dm.get("estado") != "MEDIDO" and loc and loc.get("estado") == "MEDIDO":
        # medidas con `pc dependencias` despues de publicar el cotejo de flujo: valen (son medicion), y se avisa que el
        # cotejo publicado aun no las trae
        f["ejecucion"]["dependencias_medidas"] = {
            "estado": "MEDIDO", "resumen": loc.get("resumen"),
            "directas": sorted({x["flujo"] for x in loc.get("directas") or []}),
            "indirectas": sorted({x["flujo"] for x in loc.get("indirectas") or []}),
            "sin_productor": loc.get("entradas_sin_productor") or [],
            "cascada": sorted({x.get("orquestador") for x in loc.get("directas") or [] if x.get("orquestador")})}
        f["ejecucion"]["dependencias_txt"] = f["ejecucion"]["dependencias_txt"].replace(dm.get("resumen") or "\0", loc.get("resumen") or "")
        f["avisos"].append(f"{n}: dependencias de trabajos/{t}/etl/dependencias/{n}.json ({loc.get('medido_utc', '')[:16]}); "
                           "el cotejo de flujo publicado aún no las trae")
    return f


def fuentes(lote, trabajos=None, exitosos=None):
    """[(md, flujo)] del acta, avisos e informe del cotejo de los markdowns."""
    if trabajos or exitosos:
        rutas = list(exitosos or []) + [os.path.join(RAIZ, "trabajos", t, "cierre", f"EXITOSOS_{t}.md") for t in trabajos or []]
        return cotejar_exitosos(rutas)
    from .compuerta import revision as R
    R.autorizar_acta(lote)
    pares = [({"trabajo": e["trabajo"], "rutas": []}, {"flujo": e["flujo"], "version": e["version"], "estado": e.get("estado")})
             for e in LF.leer(lote, "lote.json")["expedientes"]]
    return pares, [], {"lote": True}


def datos(lote, trabajos=None, version="1.0", fecha=None, exitosos=None):
    GN, CAPAS, F2 = _mods()
    pares, avisos, inf = fuentes(lote, trabajos, exitosos)
    if not pares:
        raise RuntimeError("ningún flujo para el acta: " + "; ".join(avisos))
    evid = os.path.join(LF.dir_lote(lote), "acta", "evidencia")
    flujos, hall, md_de = [], [], {}
    for md, fd in pares:
        try:
            f = _flujo(F2, md, fd, evid)
            flujos.append(f)
            md_de[f["fabric"]] = (md, fd)
            hall += f.pop("hallazgos")
        except LookupError as x:
            hall += x.args[0] if isinstance(x.args[0], list) else [x.args[0]]
        except (ValueError, OSError, KeyError, AssertionError) as x:
            hall.append(RV.hallazgo(md, fd["flujo"], None, "Cotejo del flujo", None,
                                    f"no se pudo leer su evidencia ({type(x).__name__}: {str(x)[:160]})", None, fd.get("version")))
    avisos += [x for f in flujos for x in f.pop("avisos")]
    # un flujo sin tablas propias (tablas_en, M-037) muestra las del flujo donde se cotejan: en el acta cada tabla va una
    # sola vez, con el flujo dueño; el otro queda con su motivo
    duenos = {o["clave"] for f in flujos if not f.get("tablas_en") for o in f["objetos"]}
    for f in flujos:
        if f.get("tablas_en") and all(o["clave"] in duenos for o in f["objetos"]):
            f["objetos"] = []
    # tablas sin lado Stratio (salvedad decidida por una persona, M-036): van a la vista en el punto 7, nunca como «cumple»
    sal = [[f"{o['clave']}\n{f['fabric']}", F2.resumir(o["salvedad_stratio"].get("motivo"), 300),
            f"{o['salvedad_stratio'].get('decidido_por', '')} · {str(o['salvedad_stratio'].get('utc', ''))[:10]}"]
           for f in flujos for o in f["objetos"] if o.get("salvedad_stratio")]
    # revisor: cada enlace con HEAD 200 y en su versión vigente (ninguna mayor publicada en la misma carpeta)
    doc = {f["cotejo_flujo"]: (f, None, "Cotejo del flujo") for f in flujos}
    nom = {"metrica_stratio": "Métrica Stratio", "metrica_fabric": "Métrica Fabric", "cotejo_stratio_fabric": "Cotejo Stratio ↔ Fabric"}
    doc.update({r: (f, o["clave"], nom.get(c, c)) for f in flujos for o in f["objetos"] for c, r in o["enlaces"].items() if r})
    enl = sorted(doc)
    lista = [r for r in enl if doc[r][2] != "Cotejo del flujo"]
    with ThreadPoolExecutor(8) as ex:                      # tope de OneLake: 8 hilos
        ok = dict(zip(enl, ex.map(lambda r: bool(ol.head(r)), enl)))
        mayor = dict(zip(lista, ex.map(RV.version_mayor, lista)))
    for r in enl:
        f, k, d_ = doc[r]
        md, fd = md_de[f["fabric"]]
        v = int(re.search(r"_v(\d+)\.json$", r).group(1))
        if not ok[r]:
            hall.append(RV.hallazgo(md, f["fabric"], k, d_, r, "el enlace no existe en OneLake (HEAD distinto de 200)",
                                    f"publicar el reporte en esta misma ruta: `python -m pc v4 publicar --trabajo {md.get('trabajo')}` (v{v})", v))
        if mayor.get(r) and mayor[r] > v and d_ != "Cotejo del flujo":      # el del flujo lo revisa RV.flujo
            hall.append(RV.hallazgo(md, f["fabric"], k, d_, r, f"hay una versión mayor publicada (v{mayor[r]}) y el EXITOSOS cita v{v}",
                                    "confirmar cuál es la evidencia vigente; si es la mayor, regenerar el EXITOSOS (`pc cierre`) y "
                                    "pasarlo de nuevo", v))
    grupos = {("analitica" if f["grupo"] == "orquestadores" else f["grupo"]) for f in flujos}
    part = [list(p) for p in CFG["participantes_fijos"]] + [
        [x["nombre"], x["org"], x["rol"]] for g in ("ingesta", "analitica") if g in grupos for x in [CFG["firmantes"][g]]]
    L = {"lote": int(lote) if str(lote).isdigit() else lote, "version": version,
         "fecha": fecha or datetime.date.today().isoformat(), "flujos": flujos, "participantes": part,
         "enlaces_no_resueltos": [], "enlaces_en_correccion": [r for r, v in ok.items() if not v], "hallazgos": hall,
         "verificado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "fl_vacio": "sin código FL asignado", "pct_decimales": 2, "ejecucion_verificada": True, "sec7_modo": "tabla",
         "graficas_dir": "graficas", "trabajos": sorted({md["trabajo"] for md, _ in pares}), "avisos": avisos,
         "cotejo_exitosos": inf,
         "capas_decididas": LF.leer(lote, "acta/capas_decididas.json", {}) or {}}
    if sal:
        L["seccion7_extra"] = [{"titulo": "Tablas aprobadas sin lado Stratio (salvedad)", "anchos": [2800, 5000, 2000],
                                "antes": ["Tablas sin contraparte medible en Stratio: se midieron completas en Fabric y los controles que "
                                          "comparan con Stratio quedaron no evaluados con esta salvedad, decidida por una persona."],
                                "cab": ["Tabla · flujo", "Salvedad", "Decidió"], "filas": sal}]
    return L


def generar(lote, version="1.0", trabajos=None, fecha=None, exitosos=None, solo_revisar=False):
    """(ruta del .docx o None si solo se revisa, L). Nada detiene el acta: lo que hay que corregir queda en
    advertencias.json y en un mensaje por QA (mensajes/<trabajo>.md); lo que hay que preguntar, en L["preguntas"]."""
    GN, CAPAS, F2 = _mods()
    L = datos(lote, trabajos, version, fecha, exitosos)
    d = os.path.join(LF.dir_lote(lote), "acta")
    os.makedirs(d, exist_ok=True)
    CAPAS.aplicar_decisiones(L)
    # lo que el revisor ya puso como hallazgo de un QA no se repite como pregunta; queda la capa (la decide el responsable)
    L["preguntas"] = [{"tipo": tp, "texto": tx} for tp, tx in GN.comprobar(L) if tp == "capa"]
    for q in CAPAS.preguntas(L):
        for f in L["flujos"]:
            if q["tabla"] is None and f["fabric"] == q["flujo"] and not CAPAS.valida(f.get("capa"), f.get("grupo")):
                f["capa"] = "por confirmar"
            for o in f["objetos"]:
                if o["clave"] == q["tabla"] and not CAPAS.valida(o.get("capa")):
                    o["capa"] = "por confirmar"
    if L["enlaces_en_correccion"]:
        L["nota_anexo"] = (f"Todos los enlaces abren el archivo en el lakehouse lh_transversal del workspace datalake-qa. Se "
                           f"comprobaron contra OneLake el {L['verificado_utc'][:16].replace('T', ' ')} UTC; "
                           f"{len(L['enlaces_en_correccion'])} están en publicación por el QA responsable, en la misma ruta.")
    L["mensajes"] = RV.guardar(L["hallazgos"], d, lote)
    json.dump(L, open(os.path.join(d, f"datos_acta_lote{lote}.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=str)
    if solo_revisar:
        return None, L
    GN.REP = d
    sal, nl, ng = GN.acta(L)
    L["anexo_enlaces"], L["graficas"] = nl, ng
    return sal, L


def fijar_capa(lote, clave, capa):
    GN, CAPAS, F2 = _mods()
    if not CAPAS.valida(capa, "orquestadores" if capa == "Orquestación" else None):
        raise ValueError(f"«{capa}» no es una capa medallón: Bronze, Silver o Gold (con « · Postgres» o « · SFTP» si es copia)")
    dec = LF.leer(lote, "acta/capas_decididas.json", {}) or {}
    dec[clave] = capa
    p = os.path.join(LF.dir_lote(lote), "acta", "capas_decididas.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(dec, open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return dec
