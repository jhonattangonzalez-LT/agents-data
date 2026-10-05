"""reportes_v4 · formato acordado el 2026-10-05 (docs/REPORTES_V4.md).

Un CICLO = una version vN por flujo. Dentro del ciclo los niveles 0, 1 y 2 escriben el MISMO archivo.
Correccion (re-ejecucion) -> `nuevo_ciclo()` -> vN+1 desde el nivel 0, con el contexto de vN dentro.
Justificacion -> misma vN.

Se PUBLICA solo (OneLake Files/resultados/reportes_v4/ + las dos mediciones al bucket v4):
  mediciones/{fabric|stratio}/<clave>/medicion_<lado>_<clave>_v<N>.json
  cotejos/<clave>/cotejo_<clave>_v<N>.json
  flujos/<flujo>/cotejo_flujo_<flujo>_v<N>.json
Queda LOCAL (no se publica): el log de agentes (trabajos/<T>/bitacora.jsonl), el expediente
(trabajos/<T>/expedientes/expediente_<flujo>_v<N>.md) y el acta .docx (~/Projects/reportes/).

Se ARMAN desde el estado local del trabajo (trabajos/<T>/…). Las diferencias las escribe el agente cotejador
(o una persona) con `registrar_diferencia()`; nada de esto se calcula solo.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import uuid

from .. import lote as L
from ..acceso import onelake as ol
from ..config import CONTROLES, criterio

RAIZ_OL = "Files/resultados/reportes_v4"
RETIRADOS = {"VG-07", "VG-08", "ID-07", "ID-08"}
CAT = [c for c in CONTROLES["controles"] if c["codigo"] not in RETIRADOS]
NIVEL = {c["codigo"]: c["nivel"] for c in CAT}
DECISIONES = ("PENDIENTE", "INFORMATIVA", "JUSTIFICADA", "A_VERIFICAR", "DEVUELTO")


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _sha(doc):
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _rol(cod, grupo):
    c = criterio(cod, grupo)
    return "no_aplica" if c == "no_aplica" else ("informa" if c == "informativo" else "decide")


def _pruebas(trabajo):
    return bool((L.leer(trabajo, "lote.json") or {}).get("pruebas"))


# ----------------------------------------------------------------- rutas
def ruta_ol(tipo, nombre, version, lado=None, pruebas=False):
    b = RAIZ_OL + ("/_pruebas" if pruebas else "")
    lo = (lado or "").lower()
    return {"medicion": f"{b}/mediciones/{lo}/{nombre}/medicion_{lo}_{nombre}_v{version}.json",
            "cotejo": f"{b}/cotejos/{nombre}/cotejo_{nombre}_v{version}.json",
            "cotejo_flujo": f"{b}/flujos/{nombre}/cotejo_flujo_{nombre}_v{version}.json",
            "log": f"{b}/flujos/{nombre}/log_agentes_{nombre}_v{version}.jsonl",
            "expediente": f"{b}/flujos/{nombre}/expediente_{nombre}_v{version}.md"}[tipo]


# ----------------------------------------------------------------- ciclos y versiones
def version(trabajo, flujo):
    """Version del ciclo vigente del flujo. La primera vez: mayor vN publicada de su cotejo de flujo + 1."""
    vs = L.leer(trabajo, "v4/ciclos.json", {}) or {}
    if flujo not in vs:
        try:
            ex = [int(m.group(1)) for p in ol.listar(ruta_ol("cotejo_flujo", flujo, 0, pruebas=_pruebas(trabajo)).rsplit("/", 1)[0], False)
                  if (m := re.search(r"cotejo_flujo_.*_v(\d+)\.json$", p["name"]))]
        except Exception:
            ex = []
        vs[flujo] = {"version": (max(ex) + 1) if ex else 1, "abierto_utc": _ahora(), "motivo": "primer ciclo en este trabajo"}
        L.guardar(trabajo, "v4/ciclos.json", vs)
    return vs[flujo]["version"]


_ESTADO_TABLA = ("rapido/{lado}/{k}.json", "rapido/{lado}/{k}.pendiente.json", "nivel2/{lado}/{k}.json",
                 "cotejo_rapido/{k}.json", "v4/mediciones/{lado}/{k}.json", "v4/cotejos/{k}.json")


def nuevo_ciclo(trabajo, flujo, motivo):
    """Correccion de desarrollo: archiva el ciclo vN del flujo y abre vN+1 (se vuelve a empezar en el nivel 0)."""
    f = L.flujo(trabajo, flujo)
    if not f:
        raise KeyError(flujo)
    v = version(trabajo, flujo)
    base = L.dir_lote(trabajo)
    hist = os.path.join(base, "historial", flujo, f"v{v}")

    def mover(rel):
        p = os.path.join(base, rel)
        if os.path.exists(p):
            os.makedirs(os.path.dirname(os.path.join(hist, rel)), exist_ok=True)
            shutil.move(p, os.path.join(hist, rel))
    for rel in (f"etl/veredictos/{flujo}.json", f"semaforo/{flujo}.json", f"v4/flujos/{flujo}.json",
                f"expedientes/expediente_{flujo}_v{v}.md"):
        mover(rel)
    idx = L.leer(trabajo, "cotejos/indice.json", {}) or {}
    dif = L.leer(trabajo, "v4/diferencias.json", {}) or {}
    from ..cache import gestor
    for o in f["objetos"]:
        k = o["clave"]
        for plantilla in _ESTADO_TABLA:
            for lado in ("FABRIC", "STRATIO"):
                mover(plantilla.format(lado=lado, k=k))
        if k in idx:
            e = idx.pop(k)
            if e.get("archivo") and os.path.exists(e["archivo"]):
                os.makedirs(os.path.join(hist, "cotejos"), exist_ok=True)
                shutil.move(e["archivo"], os.path.join(hist, "cotejos", os.path.basename(e["archivo"])))
        if k in dif:
            os.makedirs(os.path.join(hist, "v4"), exist_ok=True)
            json.dump(dif.pop(k), open(os.path.join(hist, "v4", f"diferencias_{k}.json"), "w"), indent=1, ensure_ascii=False)
        for lado in ("FABRIC", "STRATIO"):      # el dato cambio con la correccion: esa cache ya no sirve
            c = gestor.carpeta(trabajo, lado, k)
            if os.path.isdir(c):
                shutil.rmtree(c)
    L.guardar(trabajo, "cotejos/indice.json", idx)
    L.guardar(trabajo, "v4/diferencias.json", dif)
    ver = L.leer(trabajo, "v4/verificaciones.json", {}) or {}
    ver.pop(flujo, None)
    L.guardar(trabajo, "v4/verificaciones.json", ver)
    vs = L.leer(trabajo, "v4/ciclos.json", {}) or {}
    vs[flujo] = {"version": v + 1, "abierto_utc": _ahora(), "motivo": motivo, "anterior": v,
                 "historial": vs.get(flujo, {}).get("historial", []) + [v]}
    L.guardar(trabajo, "v4/ciclos.json", vs)
    L.bitacora(trabajo, "coordinador", "nuevo_ciclo", {"de": v, "a": v + 1, "motivo": motivo}, estado="DECISION", flujo=flujo)
    return v + 1


def _anterior(trabajo, flujo, rel):
    c = (L.leer(trabajo, "v4/ciclos.json", {}) or {}).get(flujo) or {}
    if not c.get("anterior") or not rel:
        return None, c
    p = os.path.join(L.dir_lote(trabajo), "historial", flujo, f"v{c['anterior']}", rel)
    return (json.load(open(p)) if os.path.exists(p) else None), c


def _encabezado(trabajo, formato, f, lado=None, objeto=None, fuente=None, nivel=None, rel=None):
    v = version(trabajo, f["nombre_fabric"])
    ant, ciclo = _anterior(trabajo, f["nombre_fabric"], rel)
    e = {"formato": formato, "id": str(uuid.uuid4()), "version": v, "trabajo": str(trabajo),
         "flujo": {"fabric": f["nombre_fabric"], "stratio": f.get("nombre_stratio"), "fl": f.get("fl"),
                   "nombres_distintos": bool(f.get("nombre_stratio")) and f.get("nombre_stratio") != f["nombre_fabric"]},
         "grupo": f["grupo"], "generado_utc": _ahora()}
    if lado:
        e["plataforma"] = lado
    if objeto is not None:
        e["objeto"] = objeto
    if fuente:
        e["fuente"] = fuente
    if nivel is not None:
        e["nivel_alcanzado"] = nivel
    if ant:
        ea = ant.get("encabezado") or {}
        e["reemplaza_a"] = {"version": ea.get("version"), "estado": ea.get("estado"), "motivo": ciclo.get("motivo"),
                            "resumen": ea.get("resumen"), "sha256": _sha(ant)}
    return e


# ----------------------------------------------------------------- 1-2 · medicion
def _contrato(rep2, rap):
    """Contrato observado en ESTA medicion (exacto). Con nivel 2 es completo; sin el, solo tipos y nulos."""
    if rep2:
        return {"completo": True, "columnas": [
            {"posicion": c["posicion"], "nombre": c["nombre"], "tipo": c["tipo"], "obligatoria": not c["nullable"],
             "pct_nulos": c.get("observado_pct_nulos"), "distintos": c.get("observado_distintos"),
             "longitud_max": c.get("observado_longitud_maxima"), "candidata_llave": c.get("candidata_a_llave")}
            for c in rep2["contrato_propuesto"]["columnas"]]}
    if rap:
        n1 = rap["nivel1"]["columnas"]

        def oblig(c):
            x = n1.get(c["nombre"]) or {}
            return None if x.get("nivel_perfil") == "SIN_ESTADISTICAS" else x.get("nulos") == 0
        return {"completo": False, "nota": "falta el nivel 2: sin longitudes, distintos ni llaves", "columnas": [
            {"posicion": c["orden"], "nombre": c["nombre"], "tipo": c["tipo"], "obligatoria": oblig(c),
             "pct_nulos": (n1.get(c["nombre"]) or {}).get("pct_nulos")} for c in rap["nivel0"]["columnas"]]}
    return None


def construir_medicion(trabajo, f, o, lado):
    k = o["clave"]
    rel = f"v4/mediciones/{lado}/{k}.json"
    rap = L.leer(trabajo, f"rapido/{lado}/{k}.json")
    pend = L.leer(trabajo, f"rapido/{lado}/{k}.pendiente.json")
    rep = L.leer(trabajo, f"nivel2/{lado}/{k}.json")
    if not (rap or pend or rep):
        return None
    src = o.get(lado.lower()) or {}
    nivel = 2 if rep else (1 if rap else -1)
    fuente = (rap or {}).get("objeto", {}).get("tipo_fuente") or (rep or {}).get("objeto", {}).get("tipo_fuente") or src.get("tipo")
    enc = _encabezado(trabajo, "pc.v4/medicion@1", f, lado, src.get("ruta"), fuente, nivel, rel)
    enc["medido_utc"] = (rep or {}).get("ejecucion", {}).get("medido_utc") or (rap or {}).get("medido_utc")
    if o.get("ventana_fechas"):
        enc["ventana_fechas"] = o["ventana_fechas"]
    doc = {"encabezado": enc}
    p = {0: {}, 1: {}, 2: {}}
    if rap:
        for cod, c in rap["controles"].items():
            if cod in NIVEL:
                p[NIVEL[cod]][cod] = {x: c.get(x) for x in ("estado", "detalle", "evidencia", "valor", "parcial", "aproximado") if c.get(x) is not None}
                p[NIVEL[cod]][cod]["medido_en"] = "nivel rápido (metadatos y pies de parquet)"
    if rep:
        v = rep["validaciones"]
        for r in v["ID_integridad_y_conteos"] + v["VG_esquema_y_metadata"]:
            if r["codigo"] in NIVEL:
                p[NIVEL[r["codigo"]]][r["codigo"]] = {"estado": r["estado"], "detalle": r["detalle"], "evidencia": r.get("evidencia"),
                                                      "medido_en": "nivel 2 (dato completo)"}
        pc_ = rep["puntos_control"]
        p[1]["CP-01"] = {"estado": pc_["CP-01_conteo"]["estado"], "valor": pc_["CP-01_conteo"]["valor"], "medido_en": "nivel 2 (dato completo)"}
        p[2]["CP-03"] = {"estado": pc_["CP-03_checksum"]["estado"], "valor": pc_["CP-03_checksum"]["valor"], "algoritmo": "SHA-256 canónico v15"}
        p[2]["CP-04"] = {"estado": "INFORMATIVO", "valor": pc_["CP-04_muestreo"]["valor"]}
    p[2]["VG-09"] = {"estado": "INFORMATIVO", "detalle": "contrato obtenido en esta medición (ver «contrato»); decide en el cotejo",
                     "completo": bool(rep)}
    doc["estado_controles"] = {c["codigo"]: {"nivel": c["nivel"], "rol": _rol(c["codigo"], f["grupo"]),
                                             "estado": (p[c["nivel"]].get(c["codigo"]) or {}).get("estado") or
                                             ("PENDIENTE" if nivel < c["nivel"] else "NO_EVALUADO")} for c in CAT}
    if rap:
        n0, n1 = rap["nivel0"], rap["nivel1"]
        doc["nivel_0"] = {"fuente": "_delta_log" if n0.get("version_delta") is not None else rap["objeto"].get("tipo_fuente"),
                          "num_columnas": n0["num_columnas"], "columnas": n0["columnas"],
                          "huellas_esquema": {"estricto": n0.get("hash_esquema_estricto"), "tipos": n0.get("hash_esquema_tipos"),
                                              "nombres": n0.get("hash_nombres_columnas")},
                          "version_delta": n0.get("version_delta"), "ultimo_commit": n0.get("ultimo_commit"),
                          **({"esquema_postgres": n0["esquema_postgres"]} if n0.get("esquema_postgres") else {}),
                          "pruebas": p[0]}
        doc["nivel_1"] = {"fuente": n1.get("fuente"), "filas": n1["filas"], "archivos": n1.get("archivos"),
                          "bytes": (rap.get("costo") or {}).get("bytes_objeto"), "filas_borradas_dv": n1.get("filas_borradas_dv"),
                          "por_columna": n1["columnas"], "sin_estadisticas": n1.get("sin_estadisticas") or [],
                          "advertencias": rap.get("advertencias") or [], "segundos": rap.get("segundos"), "pruebas": p[1]}
    elif pend:
        doc["nivel_0"] = {"estado": "REQUIERE_DESCARGA", "motivo": pend.get("motivo"), "pruebas": p[0]}
        doc["nivel_1"] = {"estado": "REQUIERE_DESCARGA", "motivo": pend.get("motivo"), "pruebas": p[1]}
    if rep:
        h = dict(rep["hash"])
        h.pop("especificacion", None)
        if not rap:
            doc["nivel_0"] = {"fuente": "nivel 2", "num_columnas": rep["esquema"]["num_columnas"], "columnas": rep["esquema"]["columnas"],
                              "huellas_esquema": {"estricto": rep["esquema"].get("hash_esquema_estricto"),
                                                  "tipos": rep["esquema"].get("hash_esquema_tipos"),
                                                  "nombres": rep["esquema"].get("hash_nombres_columnas")}, "pruebas": p[0]}
            doc["nivel_1"] = {"fuente": "nivel 2", "filas": rep["conteos"]["row_count"], "pruebas": p[1]}
        doc["nivel_2"] = {"motor": rep["ejecucion"].get("version_reporte"), "filas": rep["conteos"]["row_count"],
                          "hash": h, "perfil": rep["metricas_columnas"], "frecuentes": rep.get("valores_frecuentes"),
                          "muestra": {"limite": 10, "filas": (rep.get("muestra") or {}).get("filas")},
                          "segundos": rep["ejecucion"].get("duracion_segundos"),
                          "segundos_por_etapa": rep["ejecucion"].get("duracion_por_etapa"), "pruebas": p[2]}
        try:
            from ..cache import gestor
            e = gestor.manifiesto(trabajo)["entradas"].get(f"{lado}/{k}")
            if e:
                doc["nivel_2"]["descarga"] = {"archivos": e["archivos"], "bytes": e["bytes"], "segundos": (e.get("meta") or {}).get("segundos"),
                                              "version_delta": (e.get("meta") or {}).get("version_delta")}
        except Exception:
            pass
    doc["contrato"] = _contrato(rep, rap)
    L.guardar(trabajo, rel, doc)
    return doc


# ----------------------------------------------------------------- 3 · cotejo
_TEXTO = {"string", "varchar", "text", "char", "character varying"}


def _vg09(ms, mf):
    cs, cf = (ms or {}).get("contrato"), (mf or {}).get("contrato")
    if not cs or not cf:
        return {"estado": "PENDIENTE", "detalle": "falta el contrato de un lado"}
    S = {c["nombre"]: c for c in cs["columnas"]}
    F = {c["nombre"]: c for c in cf["columnas"]}
    Fl = {n.lower(): n for n in F}
    rupt = []
    for n, a in S.items():
        nf = n if n in F else Fl.get(n.lower())
        if not nf:
            rupt.append({"columna": n, "regla": "columna_ausente_en_fabric", "stratio": a["tipo"], "fabric": None})
            continue
        b = F[nf]
        if nf != n:
            rupt.append({"columna": n, "regla": "nombre_distinto", "stratio": n, "fabric": nf, "equivalente": True})
        if a["tipo"] != b["tipo"]:
            rupt.append({"columna": n, "regla": "tipo", "stratio": a["tipo"], "fabric": b["tipo"],
                         "equivalente": a["tipo"] in _TEXTO and b["tipo"] in _TEXTO})
        if a.get("obligatoria") and b.get("obligatoria") is False:
            rupt.append({"columna": n, "regla": "deja_de_ser_obligatoria", "stratio": a.get("pct_nulos"), "fabric": b.get("pct_nulos")})
        if cs["completo"] and cf["completo"]:
            if a.get("longitud_max") and (b.get("longitud_max") or 0) > a["longitud_max"]:
                rupt.append({"columna": n, "regla": "longitud_crece", "stratio": a["longitud_max"], "fabric": b["longitud_max"]})
            if a.get("candidata_llave") and not b.get("candidata_llave"):
                rupt.append({"columna": n, "regla": "deja_de_ser_llave", "stratio": True, "fabric": False})
    for n in F:
        if n not in S and n.lower() not in {x.lower() for x in S}:
            rupt.append({"columna": n, "regla": "columna_nueva_en_fabric", "stratio": None, "fabric": F[n]["tipo"]})
    return {"estado": "CUMPLE" if not rupt else "NO_CUMPLE", "completo": cs["completo"] and cf["completo"],
            "contrato_stratio": cs["columnas"], "contrato_fabric": cf["columnas"], "rupturas": rupt}


def _valor(m, cod):
    if not m:
        return None
    for n in ("nivel_0", "nivel_1", "nivel_2"):
        x = ((m.get(n) or {}).get("pruebas") or {}).get(cod)
        if x:
            return x.get("valor", x.get("estado"))
    return (m.get("estado_controles") or {}).get(cod, {}).get("estado")


def construir_cotejo(trabajo, f, o):
    k = o["clave"]
    rel = f"v4/cotejos/{k}.json"
    ms, mf = L.leer(trabajo, f"v4/mediciones/STRATIO/{k}.json"), L.leer(trabajo, f"v4/mediciones/FABRIC/{k}.json")
    if not (ms or mf):
        return None
    cr = L.leer(trabajo, f"cotejo_rapido/{k}.json")
    idx = (L.leer(trabajo, "cotejos/indice.json", {}) or {}).get(k)
    cc = json.load(open(idx["archivo"])) if idx and os.path.exists(idx["archivo"]) else None
    nivel = 2 if cc else (1 if cr else -1)
    enc = _encabezado(trabajo, "pc.v4/cotejo@1", f, None, {"stratio": (o.get("stratio") or {}).get("ruta"),
                                                            "fabric": (o.get("fabric") or {}).get("ruta")}, None, nivel, rel)
    enc["verdad"] = "STRATIO"
    enc["mediciones"] = {l.lower(): {"version": m["encabezado"]["version"], "nivel_alcanzado": m["encabezado"]["nivel_alcanzado"],
                                     "sha256": _sha(m)} for l, m in (("STRATIO", ms), ("FABRIC", mf)) if m}
    if not ms or not mf:
        enc["esperando"] = "STRATIO" if not ms else "FABRIC"
    vg09 = _vg09(ms, mf)
    difs = ((L.leer(trabajo, "v4/diferencias.json", {}) or {}).get(k)) or []
    comp = {0: {}, 1: {}, 2: {}}
    for c in CAT:
        cod = c["codigo"]
        rol = _rol(cod, f["grupo"])
        fila = {"rol": rol, "stratio": _valor(ms, cod), "fabric": _valor(mf, cod)}
        rr = ((cr or {}).get("controles") or {}).get(cod) or {}
        res = rr.get("resultado")
        if res == "PENDIENTE_NIVEL_2":
            res = None
        if cod == "VG-09":
            res = vg09["estado"] if vg09["estado"] != "PENDIENTE" else None
        elif cc and cod in ("CP-01", "CP-03", "ID-02", "ID-05", "CP-04"):
            v = cc["veredictos"]
            reg = v["controles"].get("regresiones") or []
            res = {"CP-01": "CUMPLE" if v["filas"]["delta"] == 0 else "NO_CUMPLE",
                   "CP-03": "CUMPLE" if v["hash"]["igual"] else "NO_CUMPLE",
                   "ID-02": "NO_CUMPLE" if "ID-02" in reg else "CUMPLE",
                   "ID-05": "NO_CUMPLE" if "ID-05" in reg else "CUMPLE", "CP-04": "INFORMATIVO"}[cod]
            if cod == "CP-03":
                iguales, distintas = v["hash"].get("columnas_hash_igual") or 0, v["hash"].get("columnas_hash_distinto") or []
                fila.update(columnas_hash_igual=iguales, columnas_hash_distinto=distintas,
                            identidad_columnas_pct=round(100.0 * iguales / max(1, iguales + len(distintas)), 2))
            if cod == "CP-01":
                fila.update(delta=v["filas"]["delta"], pct=v["filas"]["pct"])
        if cod == "CP-01" and cr and not cc:
            fila.update(delta=cr["filas"]["delta"], pct=cr["filas"]["pct"])
        if res in ("CUMPLE", "NO_CUMPLE") and rol == "informa":
            fila["comparacion"] = res
            res = "INFORMATIVO"
        if rol == "no_aplica":
            res = "NO_APLICA"
        dd = [d for d in difs if d.get("control") == cod]
        if res == "NO_CUMPLE" and dd:
            ds = {d["decision"] for d in dd}
            res = ("NO_CUMPLE" if "DEVUELTO" in ds else "A_VERIFICAR" if "A_VERIFICAR" in ds else
                   "PENDIENTE_DECISION" if "PENDIENTE" in ds else "JUSTIFICADO")
        if dd:
            fila["diferencias"] = [d["id"] for d in dd]
        fila["resultado"] = res or ("PENDIENTE" if nivel < c["nivel"] else "NO_EVALUADO")
        comp[c["nivel"]][cod] = fila
    doc = {"encabezado": enc,
           "estado_controles": {cod: {"nivel": NIVEL[cod], "rol": comp[NIVEL[cod]][cod]["rol"],
                                      "resultado": comp[NIVEL[cod]][cod]["resultado"]} for cod in NIVEL}}
    doc["nivel_0"] = {"esquema": (cr or {}).get("esquema"), "comparacion": comp[0]}
    doc["nivel_1"] = {"filas": (cr or {}).get("filas"), "nulos_distintos": (cr or {}).get("nulos_distintos"),
                      "vacias_solo_en_fabric": (cr or {}).get("vacias_solo_en_fabric"),
                      "constantes_solo_en_fabric": (cr or {}).get("constantes_solo_en_fabric"), "comparacion": comp[1]}
    if cc:
        v = cc["veredictos"]
        doc["nivel_2"] = {"criterio": cc["criterio"], "exigencias": cc["exigencias"], "dato": v["dato"], "filas": v["filas"],
                          "hash": v["hash"], "esquema": v["esquema"], "nulos": v["nulos"], "cardinalidad": v["cardinalidad"],
                          "perfil": v["perfil"], "regresiones": v["controles"].get("regresiones"),
                          "mejoras": v["controles"].get("mejoras"), "comparacion": comp[2]}
    else:
        doc["nivel_2"] = {"estado": "PENDIENTE", "comparacion": comp[2]}
    doc["VG-09_contrato"] = vg09
    doc["diferencias"] = difs
    enc["estado"] = _estado_tabla(doc, nivel, difs)
    falta = _sin_analizar(doc, difs) if nivel >= 2 else []
    if falta:
        enc["sin_analizar"] = falta
    enc["resumen"] = _resumen_tabla(doc)
    L.guardar(trabajo, rel, doc)
    return doc


def _sin_analizar(doc, difs):
    """Diferencias medibles (filas o huella distintas, rupturas de contrato) que nadie analizo todavia."""
    n2 = doc.get("nivel_2") or {}
    medibles = []
    if (n2.get("filas") or {}).get("delta"):
        medibles.append("CP-01")
    if n2.get("hash") and not n2["hash"].get("igual"):
        medibles.append("CP-03")
    if (doc.get("VG-09_contrato") or {}).get("rupturas"):
        medibles.append("VG-09")
    cubiertos = {d["control"] for d in difs}
    return [m for m in medibles if m not in cubiertos]


def _estado_tabla(doc, nivel, difs):
    if nivel < 2:
        return "EN_CURSO"
    if _sin_analizar(doc, difs):          # nada se aprueba en silencio: el cotejador debe registrar lo que vio
        return "EN_REVISION"
    res = [x["resultado"] for x in doc["estado_controles"].values() if x["rol"] == "decide"]
    ds = {d["decision"] for d in difs}
    if "DEVUELTO" in ds:
        return "DEVUELTO"
    if "NO_CUMPLE" in res or "PENDIENTE" in ds or "PENDIENTE_DECISION" in res:
        return "EN_REVISION"
    if "A_VERIFICAR" in ds or "A_VERIFICAR" in res:
        return "APROBADO_CON_VERIFICACION"
    if "JUSTIFICADA" in ds or "JUSTIFICADO" in res:
        return "APROBADO_CON_JUSTIFICACION"
    return "APROBADO"


def _resumen_tabla(doc):
    fam = {}
    for cod, x in doc["estado_controles"].items():
        if x["rol"] != "decide":
            continue
        a = fam.setdefault(cod[:2], [0, 0])
        if x["resultado"] in ("CUMPLE", "JUSTIFICADO"):
            a[0] += 1
        if x["resultado"] not in ("PENDIENTE", "NO_EVALUADO", "NO_APLICA"):
            a[1] += 1
    fl = (doc.get("nivel_2") or {}).get("filas") or (doc.get("nivel_1") or {}).get("filas") or {}
    return ((f"filas {fl.get('stratio')} → {fl.get('fabric')} · " if fl else "") +
            " · ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(fam.items())) + f" · {len(doc['diferencias'])} diferencia(s)")


def registrar_diferencia(trabajo, clave, control, tipo, descripcion, filas_afectadas, ejemplos, decision="PENDIENTE",
                         causa=None, causa_medida=False, columna=None, id_dif=None):
    """La escribe el agente cotejador tras mirar las dos tablas (o una persona). Exacta, con hasta 5 ejemplos."""
    if decision not in DECISIONES:
        raise ValueError(f"decision: {DECISIONES}")
    if control not in NIVEL:
        raise ValueError(f"control fuera del catalogo: {control}")
    if decision == "JUSTIFICADA" and not (causa and causa_medida):
        raise ValueError("JUSTIFICADA exige la causa y causa_medida=True")
    if len(ejemplos or []) > 5:
        raise ValueError("maximo 5 ejemplos por diferencia")
    d = L.leer(trabajo, "v4/diferencias.json", {}) or {}
    lst = d.setdefault(clave, [])
    id_dif = id_dif or f"D{len(lst) + 1}"
    previa = next((x for x in lst if x["id"] == id_dif), None) or {}
    nueva = {"id": id_dif, "control": control, "nivel": NIVEL[control], "tipo": tipo or previa.get("tipo"),
             "columna": columna or previa.get("columna"), "descripcion": descripcion or previa.get("descripcion"),
             "filas_afectadas": filas_afectadas if filas_afectadas is not None else previa.get("filas_afectadas"),
             "ejemplos": ejemplos or previa.get("ejemplos") or [],
             "causa": causa or previa.get("causa"), "causa_medida": causa_medida or previa.get("causa_medida", False),
             "decision": decision, "registrado_por": previa.get("registrado_por") or {"usuario": L.usuario(), "utc": _ahora()}}
    if previa:
        nueva["historial_decisiones"] = previa.get("historial_decisiones", []) + [
            {"decision": previa.get("decision"), "por": (previa.get("decidido_por") or previa.get("registrado_por") or {}).get("usuario"),
             "utc": (previa.get("decidido_por") or previa.get("registrado_por") or {}).get("utc")}]
    if decision != "PENDIENTE":
        nueva["decidido_por"] = {"usuario": L.usuario(), "utc": _ahora()}
    lst[:] = sorted([x for x in lst if x["id"] != id_dif] + [nueva], key=lambda x: x["id"])
    L.guardar(trabajo, "v4/diferencias.json", d)
    fl = next((f["nombre_fabric"] for f, o in L.objetos(trabajo) if o["clave"] == clave), None)
    L.bitacora(trabajo, "cotejador", "registrar_diferencia", {"id": id_dif, "control": control, "decision": decision,
               "causa": causa}, estado="DECISION" if decision != "PENDIENTE" else "OK", nivel=NIVEL[control], flujo=fl, clave=clave)
    return nueva


# ----------------------------------------------------------------- 4 · cotejo de flujo
def _filas_delta(tablas):
    from ..rapido import delta_remoto as dr
    out = []
    for t in tablas:
        fila = {"tabla": t}
        if t and "." in t and "/" not in t:
            try:
                lg = dr.leer_log(dr.resolver_tabla(t), todos_los_commits=False)
                st = [a.get("stats") or {} for a in lg["vigentes"].values()]
                fila["filas"] = sum(int(s.get("numRecords") or 0) for s in st) if st and all("numRecords" in s for s in st) else None
                fila["columnas"] = [c["nombre"] for c in dr.columnas(lg)]
                fila["version_delta"] = lg["version"]
            except Exception as e:
                fila["nota"] = f"no Delta o sin acceso ({type(e).__name__})"
        out.append(fila)
    return out


def _reclasificar(pruebas, cambios):
    entradas = {c["ruta"] for c in cambios if c.get("rol_codigo") == "entrada"}
    out = []
    for p in pruebas or []:
        q = {k: p.get(k) for k in ("prueba", "nivel", "objeto", "esperado", "obtenido", "detalle")}
        if p.get("prueba") in ("contenido_actualizado", "esquema_estable") and any(t and t in str(p.get("objeto")) for t in entradas):
            q.update(nivel_validador=q["nivel"], nivel="NO_APLICA",
                     reclasificada="la tabla es ENTRADA según el código del flujo: la prueba de salida no aplica")
        out.append(q)
    return out


def construir_cotejo_flujo(trabajo, f):
    n = f["nombre_fabric"]
    rel = f"v4/flujos/{n}.json"
    etl = L.leer(trabajo, f"etl/veredictos/{n}.json")
    sem = L.leer(trabajo, f"semaforo/{n}.json")
    tablas = [L.leer(trabajo, f"v4/cotejos/{o['clave']}.json") for o in f["objetos"]]
    enc = _encabezado(trabajo, "pc.v4/cotejo_flujo@1", f, rel=rel)
    enc["orquestador"] = f.get("orquestador")
    doc = {"encabezado": enc}
    if etl:
        r, inv, raw = etl["resumen"], etl.get("inventario") or {}, etl.get("veredicto") or {}
        corr, conf = inv.get("correccion") or {}, inv.get("confirmacion_delta") or {}
        doc["ejecucion"] = {"item": n, "tipo_item": r.get("tipo"), "run_id": (raw.get("corrida_fabric") or {}).get("id"),
                            "inicio_utc": r.get("inicio_utc"), "fin_utc": r.get("fin_utc"), "estado": r.get("estado_corrida"),
                            "duracion_s": r.get("duracion_s"), "actividades": raw.get("metricas_corrida"),
                            "validador": {"resultado": r.get("resultado_validador"), "lanzamiento": etl.get("lanzamiento"),
                                          "tiempos_s": raw.get("tiempos_segundos")},
                            "pruebas": _reclasificar(raw.get("pruebas"), corr.get("cambios") or [])}
        doc["dependencias"] = {"declaradas": f.get("dependencias") or [], "orquestador": f.get("orquestador"),
                               "validador": raw.get("dependencias"), "existencia": raw.get("existencia"),
                               "ejecutadas_por_qa": [e.get("detalle") for e in L.leer_bitacora(trabajo)
                                                     if e["accion"] == "ejecutar_productor" and e.get("flujo") == n]}
        if r.get("roles_desde") == "actividad_copy":
            doc["roles"] = {"desde": "actividad Copy (origen/destino del pipeline)", "invertidos_por_validador": False}
            doc["entradas"] = [{"ruta": x} for x in r.get("entradas") or []]
            doc["salidas"] = [{"ruta": x, "datos": (r.get("datos_salida") or {}).get(x)} for x in r.get("salidas") or []]
        else:
            com = {x["ruta"]: x for x in (conf.get("entradas") or []) + (conf.get("salidas") or [])}
            band = {x["ruta"]: x for x in (corr.get("entradas") or []) + (corr.get("salidas") or [])}
            doc["roles"] = {"desde": "código del flujo + _delta_log", "zip": inv.get("zip"), "capa": inv.get("capa"),
                            "invertidos_por_validador": corr.get("invertido"), "coherentes_con_delta": conf.get("roles_coherentes")}

            def mk(fila):
                b, c_ = band.get(fila["tabla"]) or {}, com.get(fila["tabla"]) or {}
                return dict(fila, parametro=b.get("bandera"), rol_segun_validador=b.get("rol_validador"),
                            commits_en_corrida=c_.get("commits_en_ventana"))
            io = etl.get("io_medido") or {}      # medido una vez al recoger el ETL y guardado en disco
            ent = io.get("entradas") if io else _filas_delta([x["ruta"] for x in corr.get("entradas") or []])
            sal = io.get("salidas") if io else _filas_delta([x["ruta"] for x in corr.get("salidas") or []])
            doc["entradas"] = [mk(x) for x in ent]
            doc["salidas"] = [mk(x) for x in sal]
            if io:
                doc["roles"]["io_medido_utc"] = io.get("utc")
        if f["grupo"] == "analitica":
            an = etl.get("revision_analitica") or {}
            ce = {c for x in doc.get("entradas", []) for c in x.get("columnas") or []}
            cs = {c for x in doc.get("salidas", []) for c in x.get("columnas") or []}
            doc["analitica"] = {
                "transformacion": {"filas_entrada": sum(x.get("filas") or 0 for x in doc.get("entradas", [])),
                                   "filas_salida": sum(x.get("filas") or 0 for x in doc.get("salidas", [])),
                                   "conservadas": sorted(ce & cs), "descartadas": sorted(ce - cs), "derivadas": sorted(cs - ce),
                                   "roles": "corregidos"},
                "consultado_al_validador": {k2: an.get(k2) for k2 in ("veredicto", "ruta_onelake", "ambiente", "transformacion")} if an else None}
    doc["tablas"] = [{"clave": o["clave"], "fabric": (o.get("fabric") or {}).get("ruta"), "stratio": (o.get("stratio") or {}).get("ruta"),
                      "estado": (t or {}).get("encabezado", {}).get("estado"), "resumen": (t or {}).get("encabezado", {}).get("resumen"),
                      "nivel_alcanzado": (t or {}).get("encabezado", {}).get("nivel_alcanzado")}
                     for o, t in zip(f["objetos"], tablas)]
    if sem:
        doc["semaforo"] = {k2: sem.get(k2) for k2 in ("estado", "motivos_rojo", "avisos", "evaluado_utc")}
    ver = (L.leer(trabajo, "v4/verificaciones.json", {}) or {}).get(n)
    if ver:
        doc["verificacion"] = ver
    niveles = [t["nivel_alcanzado"] for t in doc["tablas"] if t["nivel_alcanzado"] is not None]
    enc["nivel_alcanzado"] = min(niveles) if niveles else -1
    enc["estado"] = _estado_flujo(f, doc, ver)
    L.guardar(trabajo, rel, doc)
    return doc


def _estado_flujo(f, doc, ver):
    ej = (doc.get("ejecucion") or {}).get("estado")
    if f["grupo"] == "orquestador":
        return "APROBADO" if ej == "Completed" else ("DEVUELTO" if ej in ("Failed", "Cancelled") else "EN_CURSO")
    if (doc.get("semaforo") or {}).get("estado") == "ROJO" or ej in ("Failed", "Cancelled"):
        return "DEVUELTO"
    est = [t["estado"] for t in doc["tablas"]]
    if (ver or {}).get("decision") == "CORREGIR" or "DEVUELTO" in est:
        return "DEVUELTO"
    if not est or any(e in (None, "EN_CURSO", "EN_REVISION") for e in est):
        return "EN_CURSO"
    if "APROBADO_CON_VERIFICACION" in est:
        return "APROBADO_CON_VERIFICACION"
    if "APROBADO_CON_JUSTIFICACION" in est:
        return "APROBADO_CON_JUSTIFICACION"
    return "APROBADO"


def verificar(trabajo, flujo, por, decision, nota):
    """Cierra una APROBACION CON VERIFICACION. por: QA | COMFANDI. decision: APRUEBA | CORREGIR."""
    if por not in ("QA", "COMFANDI") or decision not in ("APRUEBA", "CORREGIR"):
        raise ValueError("por QA|COMFANDI, decision APRUEBA|CORREGIR")
    v = L.leer(trabajo, "v4/verificaciones.json", {}) or {}
    v[flujo] = {"por": por, "decision": decision, "nota": nota, "persona": L.usuario(), "utc": _ahora()}
    L.guardar(trabajo, "v4/verificaciones.json", v)
    L.bitacora(trabajo, "coordinador", "verificacion", v[flujo], estado="DECISION", flujo=flujo)
    return v[flujo]


def listo_para_acta(doc):
    e = doc["encabezado"]["estado"]
    if e == "APROBADO_CON_VERIFICACION":
        return (doc.get("verificacion") or {}).get("decision") == "APRUEBA"
    return e in ("APROBADO", "APROBADO_CON_JUSTIFICACION")


# ----------------------------------------------------------------- 5 · expediente (.md)
def expediente(trabajo, f):
    """El .md de un flujo listo para el acta: lo que recibe la persona que arma el lote."""
    n = f["nombre_fabric"]
    cf = L.leer(trabajo, f"v4/flujos/{n}.json")
    if not cf or not listo_para_acta(cf):
        return None
    pr = _pruebas(trabajo)
    v = cf["encabezado"]["version"]
    out = [f"# Expediente · {n} · v{v}", "",
           f"- Flujo en Fabric: `{n}` · en Stratio: `{f.get('nombre_stratio') or 'por definir'}` · FL: {f.get('fl') or 'sin código FL'}",
           f"- Grupo: **{f['grupo']}** · orquestador: {f.get('orquestador') or 'ninguno'}",
           f"- Estado: **{cf['encabezado']['estado']}**", f"- Trabajo: `{trabajo}` · generado {_ahora()}", ""]
    if cf.get("verificacion"):
        x = cf["verificacion"]
        out += [f"> Verificado por {x['por']} ({x['persona']}, {x['utc']}): {x['nota']}", ""]
    if cf["encabezado"].get("reemplaza_a"):
        r = cf["encabezado"]["reemplaza_a"]
        out += [f"> Reemplaza a v{r['version']} ({r['estado']}). Corrección: {r.get('motivo')}", ""]
    ej = cf.get("ejecucion") or {}
    out += ["## Ejecución", "", f"Estado **{ej.get('estado')}** · inicio {ej.get('inicio_utc')} · {ej.get('duracion_s')} s · run `{ej.get('run_id')}`", ""]
    ro = cf.get("roles") or {}
    out += ["## Entradas y salidas", "", f"Roles: {ro.get('desde')}" +
            (" · el validador los tenía invertidos; se usaron los del código" if ro.get("invertidos_por_validador") else ""), ""]
    out += [f"- entrada `{x.get('tabla') or x.get('ruta')}` · {x.get('filas')} filas" for x in cf.get("entradas") or []]
    out += [f"- salida `{x.get('tabla') or x.get('ruta')}` · {x.get('filas')} filas · commits en la corrida: {x.get('commits_en_corrida')}"
            for x in cf.get("salidas") or []]
    out += ["", "## Tablas", "", "| Tabla | Estado | Resumen |", "|---|---|---|"]
    out += [f"| `{t['clave']}` | {t['estado']} | {t['resumen']} |" for t in cf["tablas"]]
    out.append("")
    for o in f["objetos"]:
        co = L.leer(trabajo, f"v4/cotejos/{o['clave']}.json") or {}
        if co.get("diferencias"):
            out += [f"### Diferencias · {o['clave']}", ""]
            for d in co["diferencias"]:
                out += [f"- **{d['id']} · {d['control']} · {d['tipo']}**" + (f" · `{d['columna']}`" if d.get("columna") else "") +
                        f" · {d['filas_afectadas']} fila(s) · **{d['decision']}**", f"  - {d['descripcion']}"]
                if d.get("causa"):
                    out.append(f"  - Causa{' (medida)' if d.get('causa_medida') else ''}: {d['causa']}")
                out += [f"  - ejemplo: `{json.dumps(e, ensure_ascii=False, default=str)[:300]}`" for e in d.get("ejemplos") or []]
            out.append("")
    out += ["## Archivos", "", "| Documento | Ruta en el lakehouse |", "|---|---|"]
    for o in f["objetos"]:
        out += [f"| medición Stratio · `{o['clave']}` | `{ruta_ol('medicion', o['clave'], v, 'STRATIO', pr)}` |",
                f"| medición Fabric · `{o['clave']}` | `{ruta_ol('medicion', o['clave'], v, 'FABRIC', pr)}` |",
                f"| cotejo · `{o['clave']}` | `{ruta_ol('cotejo', o['clave'], v, pruebas=pr)}` |"]
    out += [f"| cotejo de flujo | `{ruta_ol('cotejo_flujo', n, v, pruebas=pr)}` |",
            f"| log de agentes (local) | `trabajos/{trabajo}/bitacora.jsonl` |"]
    ev = [e for e in L.leer_bitacora(trabajo) if e.get("flujo") in (n, None)]
    out += ["", "## Decisiones registradas", ""]
    out += [f"- {e['ts']} · {e['usuario']} · {e['accion']} · {json.dumps(e.get('detalle'), ensure_ascii=False, default=str)[:200]}"
            for e in ev if e["estado"] == "DECISION"]
    out += ["", f"Eventos en el log: {len(ev)} · errores: {sum(1 for e in ev if e['estado'] == 'ERROR')}"]
    p = os.path.join(L.dir_lote(trabajo), "expedientes", f"expediente_{n}_v{v}.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf8").write("\n".join(out) + "\n")
    return p


# ----------------------------------------------------------------- todo y publicacion
def construir(trabajo):
    d = L.leer(trabajo, "lote.json")
    h = {"mediciones": 0, "cotejos": 0, "cotejos_flujo": 0, "expedientes": 0}
    for f in d["flujos"]:
        for o in f["objetos"]:
            for lado in ("FABRIC", "STRATIO"):
                h["mediciones"] += bool(construir_medicion(trabajo, f, o, lado))
            h["cotejos"] += bool(construir_cotejo(trabajo, f, o))
        construir_cotejo_flujo(trabajo, f)
        h["cotejos_flujo"] += 1
        h["expedientes"] += bool(expediente(trabajo, f))
    return h


def publicar(trabajo, bucket=True):
    """Publica SOLO mediciones, cotejos y cotejo de flujo en OneLake reportes_v4 (reescribe en sitio la vN del ciclo)
    y las dos mediciones al bucket v4. HEAD a todo. Log, expediente y acta quedan locales."""
    from ..acceso import bucket as B
    d = L.leer(trabajo, "lote.json")
    pr = _pruebas(trabajo)
    base, hechos = L.dir_lote(trabajo), []

    def subir(dest, datos, extra):
        ol.escribir(dest, datos)
        h = ol.head(dest)
        r = dict({"ruta": dest, "head_ok": bool(h) and h["bytes"] == len(datos)}, **extra)
        hechos.append(r)
        return r
    for f in d["flujos"]:
        n = f["nombre_fabric"]
        v = version(trabajo, n)
        for o in f["objetos"]:
            k = o["clave"]
            for lado in ("STRATIO", "FABRIC"):
                p = os.path.join(base, "v4", "mediciones", lado, f"{k}.json")
                if os.path.exists(p):
                    datos = open(p, "rb").read()
                    r = subir(ruta_ol("medicion", k, v, lado, pr), datos, {"tipo": f"medicion_{lado.lower()}", "version": v})
                    if bucket:
                        blob = f"v4/{'_pruebas/' if pr else ''}qa/{k}/medicion_{lado.lower()}_{k}_v{v}.json"
                        try:
                            B.subir(lado, blob, datos, sobrescribir=True)
                            r["bucket"] = f"{B.CONT[lado]}/{blob}"
                        except Exception as e:
                            r["bucket_error"] = f"{type(e).__name__}: {str(e)[:120]}"
            p = os.path.join(base, "v4", "cotejos", f"{k}.json")
            if os.path.exists(p):
                subir(ruta_ol("cotejo", k, v, pruebas=pr), open(p, "rb").read(), {"tipo": "cotejo", "version": v})
        p = os.path.join(base, "v4", "flujos", f"{n}.json")
        if os.path.exists(p):
            subir(ruta_ol("cotejo_flujo", n, v, pruebas=pr), open(p, "rb").read(), {"tipo": "cotejo_flujo", "version": v})
    L.guardar(trabajo, "v4/publicado.json", {"utc": _ahora(), "pruebas": pr, "archivos": hechos})
    return hechos
