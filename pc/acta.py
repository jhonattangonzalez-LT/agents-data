"""Acta de entrega en el FORMATO NORMALIZADO (el del agente acta-entrega, 2026-10-22), para todo el equipo.

  python -m pc acta generar --lote N [--trabajos T1,T2] [--version 1.0] [--fecha AAAA-MM-DD]
  python -m pc acta capa --lote N --clave <tabla o flujo> --capa "Silver"     respuesta a una capa ambigua

De dónde salen los flujos:
  · con lotes/<N>/lote.json (lote armado con `pc lote armar`): sus expedientes, y solo con las 3 compuertas aprobadas
    y por el responsable del acta (como siempre);
  · con --trabajos: los flujos del EXITOSOS_<T>.md de cada trabajo (formato cierre-v1). Un EXITOSOS con
    `completo: false` no entra: se resuelve con QA y se regenera el cierre.
El dato se lee de los reportes v4 LOCALES de cada trabajo (trabajos/<T>/v4/, formato 2) con pc/docx/lector_formato2.py;
el .docx lo dibuja pc/docx/acta_normalizada.py (copia del generador de qa-etl-validador-agent-v2/actas, con capas
medallón, dependencias medidas, gráficas completas, CP-05 con motivo, punto 7 resumido y punto 8 sin firmas).
Cada enlace del anexo se comprueba con HEAD. El generador se niega (código 2) y deja en lotes/<N>/acta/preguntas.json
lo que hay que PREGUNTAR o medir: capas ambiguas, dependencias no medidas, diferencias sin ejemplo real.
Todo queda local en lotes/<N>/acta/ (el acta nunca se publica).
"""
import datetime
import json
import os
import re
import sys
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


def _exitosos(trabajo):
    """Front-matter del EXITOSOS: (flujos, completo)."""
    p = os.path.join(RAIZ, "trabajos", trabajo, "cierre", f"EXITOSOS_{trabajo}.md")
    if not os.path.exists(p):
        raise FileNotFoundError(f"{p}: correr `python -m pc cierre --trabajo {trabajo}`")
    fm = open(p, encoding="utf8").read().split("\n---", 1)[0]
    flujos = [dict(re.findall(r'(\w+): "?([^",}]*)"?', ln)) for ln in fm.splitlines() if ln.strip().startswith("- {flujo")]
    m = re.search(r"^completo:\s*(\w+)", fm, re.M)
    return flujos, (m.group(1).lower() != "false") if m else True


def expedientes(lote, trabajos=None):
    """[(trabajo, flujo)] del acta y los avisos de lo que no entra."""
    out, avisos = [], []
    if trabajos:
        for t in trabajos:
            fs, completo = _exitosos(t)
            if not completo:
                avisos.append(f"{t}: EXITOSOS con completo: false (ver trabajos/{t}/salidas/cierre_faltantes.json): no entra")
                continue
            out += [(t, f["flujo"]) for f in fs]
    else:
        from .compuerta import revision as R
        R.autorizar_acta(lote)
        out = [(e["trabajo"], e["flujo"]) for e in LF.leer(lote, "lote.json")["expedientes"]]
    vistos = {}
    for t, n in out:
        if n in vistos:
            avisos.append(f"{n} está en {vistos[n]} y en {t}: se toma el de {vistos[n]}")
        vistos.setdefault(n, t)
    return [(t, n) for n, t in vistos.items()], avisos


def _flujo(F2, t, n):
    v4 = os.path.join(RAIZ, "trabajos", t, "v4")
    from .reportes import v4 as V4
    cf = T.leer(t, f"v4/flujos/{n}.json")
    if not cf:
        raise FileNotFoundError(f"{t}/v4/flujos/{n}.json: falta el cotejo de flujo (pc v4 publicar)")
    ver, pr = cf["encabezado"]["version"], bool((T.leer(t, "lote.json") or {}).get("pruebas"))
    links = {"flujo": V4.ruta_ol("cotejo_flujo", n, ver, pruebas=pr), "tablas": {}}
    for x in cf.get("tablas") or []:
        k = x["clave"]
        enc = (T.leer(t, f"v4/cotejos/{k}.json") or {}).get("encabezado", {})
        vk, solo_fabric = enc.get("version", ver), (enc.get("objeto") or {}).get("stratio") is None
        links["tablas"][k] = {"metrica_stratio": None if solo_fabric else V4.ruta_ol("medicion", k, vk, "STRATIO", pr),
                              "metrica_fabric": V4.ruta_ol("medicion", k, vk, "FABRIC", pr),
                              "cotejo_stratio_fabric": V4.ruta_ol("cotejo", k, vk, pruebas=pr)}
    f = F2.flujo(v4, n, links, T.flujo(t, n) or {})
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


def datos(lote, trabajos=None, version="1.0", fecha=None):
    GN, CAPAS, F2 = _mods()
    pares, avisos = expedientes(lote, trabajos)
    flujos = [_flujo(F2, t, n) for t, n in pares]
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
         "graficas_dir": "graficas", "trabajos": sorted({t for t, _ in pares}), "avisos": avisos,
         "capas_decididas": LF.leer(lote, "acta/capas_decididas.json", {}) or {}}
    if sal:
        L["seccion7_extra"] = [{"titulo": "Tablas aprobadas sin lado Stratio (salvedad)", "anchos": [2800, 5000, 2000],
                                "antes": ["Tablas sin contraparte medible en Stratio: se midieron completas en Fabric y los controles que "
                                          "comparan con Stratio quedaron no evaluados con esta salvedad, decidida por una persona."],
                                "cab": ["Tabla · flujo", "Salvedad", "Decidió"], "filas": sal}]
    return L


def generar(lote, version="1.0", trabajos=None, fecha=None):
    """(ruta del .docx, L) o (None, preguntas) si hay algo que preguntar o medir antes."""
    GN, CAPAS, F2 = _mods()
    L = datos(lote, trabajos, version, fecha)
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
