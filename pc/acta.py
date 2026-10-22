"""Acta de entrega en el FORMATO NORMALIZADO (el del agente acta-entrega, 2026-10-22), para todo el equipo.

  python -m pc acta generar --lote N --exitosos <carpeta o EXITOSOS_*.md> [--version 1.0] [--fecha AAAA-MM-DD]
  python -m pc acta generar --lote N [--trabajos T1,T2]
  python -m pc acta capa --lote N --clave <tabla o flujo> --capa "Silver"     respuesta a una capa ambigua

De dónde salen los flujos:
  · con lotes/<N>/lote.json (lote armado con `pc lote armar`): sus expedientes, y solo con las 3 compuertas aprobadas
    y por el responsable del acta (como siempre);
  · con --exitosos (o --trabajos): los EXITOSOS_<T>.md de los coordinadores, de cualquier equipo, COTEJADOS entre sí
    (cotejar_exitosos: completo, PENDIENTES, repetidos) y contra el cotejo de flujo publicado (versión y estado). La huella
    del markdown solo informa: el cuerpo se puede anotar a mano y las cifras no salen de él sino de los reportes publicados.
El dato se lee de los reportes v4 que cita cada EXITOSOS (copia local del trabajo si es la misma versión; si no, de
OneLake a lotes/<N>/acta/evidencia/) con pc/docx/lector_formato2.py;
el .docx lo dibuja pc/docx/acta_normalizada.py (copia del generador de qa-etl-validador-agent-v2/actas, con capas
medallón, dependencias medidas, gráficas completas, CP-05 con motivo, punto 7 resumido y punto 8 sin firmas).
Cada enlace del anexo se comprueba con HEAD. El generador se niega (código 2) y deja en lotes/<N>/acta/preguntas.json
lo que hay que PREGUNTAR o medir: capas ambiguas, dependencias no medidas, diferencias sin ejemplo real.
Todo queda local en lotes/<N>/acta/ (el acta nunca se publica).
"""
import datetime
import glob
import hashlib
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
    """Un EXITOSOS/PENDIENTES (cierre-v1): front-matter, huella comprobada y las rutas de OneLake que cita."""
    s = open(p, encoding="utf8").read().replace("\r\n", "\n")      # llegado por correo o chat desde Windows
    if not s.startswith("---\n") or "\n---\n" not in s[4:]:
        raise ValueError(f"{p}: no es un cierre-v1 (sin front-matter)")
    fm, cuerpo = s[4:].split("\n---\n", 1)
    g = lambda k: (re.search(rf'^{k}:\s*"?([^"\n]*)"?', fm, re.M) or [None, None])[1]
    flujos = [dict(re.findall(r'(\w+): "?([^",}]*)"?', ln)) for ln in fm.splitlines() if ln.strip().startswith("- {flujo")]
    return {"ruta": p, "formato": g("formato"), "tipo": g("tipo"), "trabajo": g("trabajo"), "generado_utc": g("generado_utc"),
            "generado_por": g("generado_por"), "completo": (g("completo") or "true").lower() != "false",
            "huella_ok": hashlib.sha256(cuerpo.encode()).hexdigest() == g("huella_sha256"), "flujos": flujos,
            "rutas": [urllib.parse.unquote(x) for x in re.findall(r"selectedPath=([^&)\s]+)", cuerpo)]}


def _mds(rutas):
    """Archivos o carpetas (se buscan EXITOSOS_*.md y PENDIENTES_*.md adentro, en cualquier nivel)."""
    out = []
    for r in rutas:
        r = os.path.expanduser(r)
        if os.path.isdir(r):
            out += sorted(glob.glob(os.path.join(r, "**", "EXITOSOS_*.md"), recursive=True))
            out += sorted(glob.glob(os.path.join(r, "**", "PENDIENTES_*.md"), recursive=True))
        elif os.path.exists(r):
            out.append(r)
        else:
            raise FileNotFoundError(r)
    # el PENDIENTES hermano de cada EXITOSOS entra al cotejo aunque no lo hayan pasado
    for x in list(out):
        h = os.path.join(os.path.dirname(x), os.path.basename(x).replace("EXITOSOS_", "PENDIENTES_", 1))
        if os.path.basename(x).startswith("EXITOSOS_") and os.path.exists(h) and h not in out:
            out.append(h)
    return list(dict.fromkeys(os.path.abspath(x) for x in out))


def _nom(p):
    return os.path.join(os.path.basename(os.path.dirname(p)), os.path.basename(p))


def cotejar_exitosos(rutas):
    """Coteja los markdowns entre sí antes de armar el acta: formato, completo, flujos que están también en un
    PENDIENTES y flujos repetidos entre EXITOSOS (se toma la versión mayor; a igual versión, el cierre más reciente).
    Devuelve ([(md, flujo)], avisos, informe)."""
    mds, avisos, inf, elegidos = [], [], {"exitosos": [], "excluidos": [], "ignorados": []}, {}
    for p in _mds(rutas):
        try:
            mds.append(leer_md(p))
        except ValueError:                     # resúmenes o copias a mano: no son evidencia del cierre
            inf["ignorados"].append(p)
            avisos.append(f"{os.path.basename(p)}: no es un cierre-v1 (sin front-matter): se ignora")
    ex = [m for m in mds if m["tipo"] == "EXITOSOS"]
    pend = {f["flujo"]: m for m in mds if m["tipo"] == "PENDIENTES" for f in m["flujos"]}
    for m in ex:
        motivo = ("no es cierre-v1" if m["formato"] != "cierre-v1" else
                  "completo: false (faltantes en salidas/cierre_faltantes.json del trabajo)" if not m["completo"] else None)
        inf["exitosos"].append({"ruta": m["ruta"], "trabajo": m["trabajo"], "generado_utc": m["generado_utc"],
                                "generado_por": m["generado_por"], "flujos": len(m["flujos"]), "entra": not motivo, "motivo": motivo})
        if not motivo and not m["huella_ok"]:
            # el cuerpo cambió despues del cierre (notas a mano, otro editor): no excluye, porque el acta no toma cifras del
            # markdown sino de los reportes publicados, que se cotejan flujo por flujo (version y estado)
            avisos.append(f"{_nom(m['ruta'])}: el cuerpo cambió después del cierre (huella distinta); se usa su lista de flujos "
                          "y las cifras de los reportes publicados")
        inf["exitosos"][-1]["huella_igual"] = m["huella_ok"]
        if motivo:
            avisos.append(f"{_nom(m['ruta'])}: no entra · {motivo}")
            continue
        for f in m["flujos"]:
            n = f["flujo"]
            if n in pend and (pend[n]["generado_utc"] or "") >= (m["generado_utc"] or ""):
                inf["excluidos"].append({"flujo": n, "motivo": f"también está en {os.path.basename(pend[n]['ruta'])} (más reciente)"})
                avisos.append(f"{n}: está en {_nom(m['ruta'])} y en {os.path.basename(pend[n]['ruta'])} (más reciente): no entra")
                continue
            if n in elegidos:
                m0, f0 = elegidos[n]
                nuevo = (int(f["version"]), m["generado_utc"] or "") > (int(f0["version"]), m0["generado_utc"] or "")
                (m_k, f_k), (m_d, f_d) = ((m, f), (m0, f0)) if nuevo else ((m0, f0), (m, f))
                avisos.append(f"{n}: en {_nom(m0['ruta'])} y {_nom(m['ruta'])}: se toma v{f_k['version']} de "
                              f"{_nom(m_k['ruta'])}")
                inf["excluidos"].append({"flujo": n, "motivo": f"repetido: v{f_d['version']} de {_nom(m_d['ruta'])}"})
                if not nuevo:
                    continue
            elegidos[n] = (m, f)
    return list(elegidos.values()), avisos, inf


def _traer(rel_ol, local_v4, destino, version):
    """El reporte v4 en la version del cierre: la copia local del trabajo si es esa misma version; si no, OneLake."""
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if local_v4 and os.path.exists(local_v4):
        d = json.load(open(local_v4, encoding="utf8"))
        if str((d.get("encabezado") or {}).get("version")) == str(version):
            shutil.copyfile(local_v4, destino)
            return d, "local"
    data = ol.leer(rel_ol)
    open(destino, "wb").write(data)
    return json.loads(data), "OneLake"


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
    cf, origen = _traer(rf, os.path.join(loc, "flujos", f"{n}.json"), os.path.join(dv4, "flujos", f"{n}.json"), ver)
    e = cf["encabezado"]
    if str(e.get("version")) != str(ver) or (fd.get("estado") and e.get("estado") != fd["estado"]):
        raise ValueError(f"{n}: el cierre dice v{ver} {fd.get('estado')} y el cotejo de flujo dice v{e.get('version')} {e.get('estado')}")
    links = {"flujo": rf, "tablas": {}}
    for x in cf.get("tablas") or []:
        k = x["clave"]
        rc = cita(rf"/cotejos/{re.escape(k)}/cotejo_{re.escape(k)}_v\d+\.json$")
        vk = int(re.search(r"_v(\d+)\.json$", rc).group(1)) if rc else ver
        rc = rc or f"{base}/cotejos/{k}/cotejo_{k}_v{vk}.json"
        co, _ = _traer(rc, os.path.join(loc, "cotejos", f"{k}.json"), os.path.join(dv4, "cotejos", f"{k}.json"), vk)
        solo_fabric = (co["encabezado"].get("objeto") or {}).get("stratio") is None
        med = lambda lado: cita(rf"/mediciones/{lado}/{re.escape(k)}/medicion_{lado}_{re.escape(k)}_v\d+\.json$") or \
            f"{base}/mediciones/{lado}/{k}/medicion_{lado}_{k}_v{vk}.json"
        links["tablas"][k] = {"metrica_stratio": None if solo_fabric else med("stratio"), "metrica_fabric": med("fabric"),
                              "cotejo_stratio_fabric": rc}
    try:
        lote_flujo = T.flujo(t, n) or {}
    except Exception:                                      # el trabajo no esta en este equipo: basta el cierre
        lote_flujo = {}
    f = F2.flujo(dv4, n, links, lote_flujo)
    f["origen_reportes"] = origen
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
                           "el cotejo de flujo publicado aún no las trae (republicar con pc v4 publicar)")
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
    flujos = []
    for md, fd in pares:
        try:
            flujos.append(_flujo(F2, md, fd, evid))
        except (ValueError, OSError) as x:
            avisos.append(f"{fd['flujo']}: no entra · {x}")
            inf.setdefault("excluidos", []).append({"flujo": fd["flujo"], "motivo": str(x)})
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
    enl = sorted({f["cotejo_flujo"] for f in flujos} | {r for f in flujos for o in f["objetos"] for r in o["enlaces"].values() if r})
    with ThreadPoolExecutor(8) as ex:                      # tope de OneLake: 8 hilos
        ok = dict(zip(enl, ex.map(lambda r: bool(ol.head(r)), enl)))
    grupos = {("analitica" if f["grupo"] == "orquestadores" else f["grupo"]) for f in flujos}
    part = [list(p) for p in CFG["participantes_fijos"]] + [
        [x["nombre"], x["org"], x["rol"]] for g in ("ingesta", "analitica") if g in grupos for x in [CFG["firmantes"][g]]]
    L = {"lote": int(lote) if str(lote).isdigit() else lote, "version": version,
         "fecha": fecha or datetime.date.today().isoformat(), "flujos": flujos, "participantes": part,
         "enlaces_no_resueltos": [f"HEAD sin respuesta: {r}" for r, v in ok.items() if not v],
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


def generar(lote, version="1.0", trabajos=None, fecha=None, exitosos=None):
    """(ruta del .docx, L) o (None, preguntas) si hay algo que preguntar o medir antes."""
    GN, CAPAS, F2 = _mods()
    L = datos(lote, trabajos, version, fecha, exitosos)
    d = os.path.join(LF.dir_lote(lote), "acta")
    os.makedirs(d, exist_ok=True)
    json.dump(L, open(os.path.join(d, f"datos_acta_lote{lote}.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=str)
    preg = [{"tipo": "enlace", "texto": x} for x in L["enlaces_no_resueltos"]] + \
           [{"tipo": tp, "texto": tx} for tp, tx in GN.comprobar(L)]
    if preg:
        json.dump(preg, open(os.path.join(d, "preguntas.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
        return None, preg
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
