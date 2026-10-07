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


def _version_anterior(trabajo, flujo, rel):
    ant, ciclo = _anterior(trabajo, flujo, rel)
    if not ant:
        return None
    ea = ant.get("encabezado") or {}
    return {"version": ea.get("version"), "estado_que_tenia": ea.get("estado"), "motivo_del_nuevo_ciclo": ciclo.get("motivo")}


def construir_cotejo(trabajo, f, o):
    """Cotejo de tabla, formato 2 (pc/reportes/formato2.py): encabezado · controles · justificaciones · metricas."""
    from . import formato2 as F2
    k = o["clave"]
    rel = f"v4/cotejos/{k}.json"
    ms, mf = L.leer(trabajo, f"v4/mediciones/STRATIO/{k}.json"), L.leer(trabajo, f"v4/mediciones/FABRIC/{k}.json")
    if not (ms or mf):
        return None
    cr = L.leer(trabajo, f"cotejo_rapido/{k}.json")
    idx = (L.leer(trabajo, "cotejos/indice.json", {}) or {}).get(k)
    cc = json.load(open(idx["archivo"])) if idx and os.path.exists(idx["archivo"]) else None
    enc = {"id": str(uuid.uuid4()), "version": version(trabajo, f["nombre_fabric"]), "trabajo": str(trabajo), "generado_utc": _ahora(),
           "mediciones": {l.lower(): {"version": m["encabezado"]["version"], "nivel_alcanzado": m["encabezado"]["nivel_alcanzado"],
                                      "sha256": _sha(m)} for l, m in (("STRATIO", ms), ("FABRIC", mf)) if m}}
    if not ms or not mf:
        enc["esperando"] = "STRATIO" if not ms else "FABRIC"
    difs = ((L.leer(trabajo, "v4/diferencias.json", {}) or {}).get(k)) or []
    doc = F2.cotejo(enc, f, o, ms, mf, cr, cc, difs, _vg09(ms, mf), _version_anterior(trabajo, f["nombre_fabric"], rel))
    doc["encabezado"]["faltantes"] = F2.faltantes_cotejo(doc)
    L.guardar(trabajo, rel, doc)
    return doc


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
    """Cotejo de flujo, formato 2: encabezado · ejecucion · analitica|ingesta · orquestacion · comprobaciones · tablas · semaforo.
    La evidencia de la corrida y de las dependencias la mide `pc etl evidencia` (etl/evidencia/<flujo>.json)."""
    from . import formato2 as F2
    n = f["nombre_fabric"]
    rel = f"v4/flujos/{n}.json"
    etl = L.leer(trabajo, f"etl/veredictos/{n}.json")
    ev = L.leer(trabajo, f"etl/evidencia/{n}.json")
    sem = L.leer(trabajo, f"semaforo/{n}.json")
    tablas = [L.leer(trabajo, f"v4/cotejos/{o['clave']}.json") for o in f["objetos"]]
    enc = {"id": str(uuid.uuid4()), "version": version(trabajo, n), "trabajo": str(trabajo), "generado_utc": _ahora(),
           "version_anterior": _version_anterior(trabajo, n, rel)}
    otros = []
    for g in (L.leer(trabajo, "lote.json") or {}).get("flujos", []):
        e2 = L.leer(trabajo, f"etl/veredictos/{g['nombre_fabric']}.json") or {}
        otros.append({"flujo": g["nombre_fabric"],
                      "entradas": [x.get("ruta") for x in ((e2.get("inventario") or {}).get("correccion") or {}).get("entradas") or []]})
    ver = (L.leer(trabajo, "v4/verificaciones.json", {}) or {}).get(n)
    doc = F2.flujo(enc, f, etl, ev, sem, tablas, ver, otros)
    doc["encabezado"]["faltantes"] = F2.faltantes_flujo(doc)
    L.guardar(trabajo, rel, doc)
    return doc


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
    if cf["encabezado"].get("version_anterior"):
        r = cf["encabezado"]["version_anterior"]
        out += [f"> Reemplaza a v{r['version']} (que estaba {r['estado_que_tenia']}). Corrección: {r.get('motivo_del_nuevo_ciclo')}", ""]
    ej = (cf.get("ejecucion") or {}).get("corrida_validada") or {}
    out += ["## Ejecución", "", f"Estado **{ej.get('estado')}** · inicio {ej.get('inicio_utc')} · {ej.get('duracion_s')} s · run `{ej.get('run_id')}`"
            f" · lanzada por {ej.get('lanzada_por')}", ""]
    sec = cf.get("analitica") or cf.get("ingesta") or {}
    ro = sec.get("roles") or {}
    out += ["## Entradas y salidas", "", f"Roles: {ro.get('origen')}" +
            (" · el validador los tenía invertidos; se usaron los del código" if ro.get("corregidos_respecto_al_validador") else ""), ""]
    out += [f"- entrada `{x.get('entrada')}` · versión leída {x.get('version_leida')} ({x.get('commit_utc')}) · {x.get('filas')} filas"
            for x in sec.get("entradas") or []]
    out += [f"- salida `{x.get('tabla') or x.get('destino')}` · escrita por la corrida: {x.get('escrita_por_la_corrida_validada', x.get('archivos_escritos_en_la_corrida'))}"
            for x in sec.get("salidas") or []]
    out += ["", "## Comprobaciones del flujo", ""]
    out += [f"- {c['resultado']} · {c['comprobacion']} · {c['detalle']}" for c in cf.get("comprobaciones") or []]
    out += ["", "## Tablas", "", "| Tabla | Estado | Resumen |", "|---|---|---|"]
    out += [f"| `{t['clave']}` | {t['estado']} | {t['resumen']} |" for t in cf["tablas"]]
    out.append("")
    for o in f["objetos"]:
        co = L.leer(trabajo, f"v4/cotejos/{o['clave']}.json") or {}
        if co.get("justificaciones"):
            out += [f"### Diferencias · {o['clave']}", ""]
            for d in co["justificaciones"]:
                out += [f"- **{d['id']} · {d['control']} · {d['tipo']}**" + (f" · `{d['columna']}`" if d.get("columna") else "") +
                        f" · {d['filas_afectadas']} fila(s) · **{d['decision']}**", f"  - {d['que_se_encontro']}"]
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


def incompletos(trabajo):
    """{archivo: [lo que falta]} de los cotejos de tabla y de flujo del trabajo. Vacio = todo completo."""
    out = {}
    for f in (L.leer(trabajo, "lote.json") or {}).get("flujos", []):
        cf = L.leer(trabajo, f"v4/flujos/{f['nombre_fabric']}.json")
        x = (cf or {}).get("encabezado", {}).get("faltantes") if cf else ["no existe el cotejo de flujo"]
        if x:
            out[f"flujo {f['nombre_fabric']}"] = x
        for o in f["objetos"]:
            co = L.leer(trabajo, f"v4/cotejos/{o['clave']}.json")
            x = (co or {}).get("encabezado", {}).get("faltantes") if co else ["no existe el cotejo"]
            if x:
                out[f"tabla {o['clave']}"] = x
    return out


def publicar(trabajo, bucket=True, forzar_incompleto=False):
    """Publica SOLO mediciones, cotejos y cotejo de flujo en OneLake reportes_v4 (reescribe en sitio la vN del ciclo)
    y las dos mediciones al bucket v4. HEAD a todo. Log, expediente y acta quedan locales."""
    from ..acceso import bucket as B
    d = L.leer(trabajo, "lote.json")
    falta = incompletos(trabajo)
    if falta and not forzar_incompleto:
        raise RuntimeError("no se publica: informacion incompleta en " + "; ".join(f"{k}: {v[:4]}" for k, v in list(falta.items())[:8]))
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
