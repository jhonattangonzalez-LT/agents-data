"""Reporte RAPIDO (niveles 0 y 1) de un objeto, sin descargar el dato.

  nivel 0 · esquema, version Delta, commits dentro de la ventana de la corrida   -> VG-01..06, CP-02, CP-05
  nivel 1 · pies de parquet (filas, nulos, min/max por columna)                  -> CP-01, ID-01, ID-03, ID-04, ID-06

Las reglas VG/ID se evaluan con el MISMO codigo del motor v15 (medir/motor_v15.reglas), sobre un
perfil armado con lo que dan los pies. Lo que solo sale del dato completo (CP-03, ID-02, ID-05,
CP-04) queda PENDIENTE_NIVEL_2: nunca se da por cumplido.
"""
import datetime
import time

from ..acceso import onelake as ol
from ..medir import motor_v15 as motor
from . import delta_remoto as dr
from . import pies as P

VERSION = "pc-rapido-1"
PENDIENTES = {"CP-03": "checksum SHA-256: requiere el dato completo",
              "ID-02": "duplicados de fila completa: requiere el hash por fila",
              "ID-05": "candidatas a llave: requiere distintos exactos",
              "CP-04": "muestreo: se toma al medir en nivel 2"}
FUERA = {"VG-07", "VG-08", "ID-07", "ID-08"}


def _iso(t=None):
    return (t or datetime.datetime.now(datetime.timezone.utc)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _perfil(cols, agg):
    """Perfil minimo que entienden motor.reglas / contrato a partir de los pies."""
    filas = agg["filas"]
    perfil, sin_est = {}, []
    for c in cols:
        a = agg["columnas"].get(c.get("fisico", c["nombre"])) or agg["columnas"].get(c["nombre"]) or {}
        nul = a.get("nulos")
        nn = None if nul is None else filas - nul
        mn, mx = a.get("min"), a.get("max")
        est = bool(a.get("con_estadisticas")) and nul is not None
        if not est:
            sin_est.append(c["nombre"])
        perfil[c["nombre"]] = {
            "tipo_spark": c["tipo"], "orden_fisico": c["orden"], "registros": filas,
            "no_nulos": nn if nn is not None else -1, "nulos": nul if nul is not None else 0,
            "pct_nulos": round(100.0 * nul / filas, 4) if (filas and nul is not None) else None,
            "minimo": mn, "maximo": mx,
            "es_constante": (mn == mx and mn is not None) if est else False,
            "candidata_a_llave": False, "valores_distintos": None,
            "nivel_perfil": "PIES_PARQUET" if est else "SIN_ESTADISTICAS"}
    return perfil, sin_est


def _controles(cols, perfil, filas, sin_est, cp05, aproximado):
    hashes = {"filas_duplicadas_exactas": None, "filas_duplicadas_estimadas": 0, "filas_distintas_metodo": None}
    val = motor.reglas(cols, perfil, hashes, filas)
    out = {}
    for r in val["ID_integridad_y_conteos"] + val["VG_esquema_y_metadata"]:
        cod = r["codigo"]
        if cod in FUERA:
            continue
        r = dict(r, nivel=0 if cod.startswith("VG") else 1)
        if cod in PENDIENTES:
            r.update(estado="PENDIENTE_NIVEL_2", detalle=PENDIENTES[cod], evidencia=None, nivel=2)
        if cod == "ID-03" and sin_est:
            vacias = [n for n in (r.get("evidencia") or {}).get("columnas", []) if n not in sin_est]
            r["evidencia"] = {"columnas": vacias, "sin_estadisticas": sin_est}
            r["estado"] = "OK" if not vacias else "ALERTA"
            r["detalle"] = f"{len(vacias)} columna(s) sin ningun valor · {len(sin_est)} sin estadisticas en el pie (se deciden en nivel 2)"
        if cod == "ID-06" and sin_est:
            r["detalle"] += f" · {len(sin_est)} columna(s) sin min/max en el pie: se deciden en nivel 2"
            r["parcial"] = True
        if aproximado and cod in ("ID-03", "ID-04"):
            r["aproximado"] = "hay deletion vectors: los nulos del pie incluyen filas borradas"
        out[cod] = r
    out["CP-01"] = {"codigo": "CP-01", "nombre": "Conteo de filas", "estado": "OK" if filas else "ALERTA",
                    "valor": filas, "nivel": 1, "detalle": f"{filas:,} filas (pies de parquet)"}
    firma = ", ".join(f"{c['nombre']} ({c['tipo']})" for c in cols)
    out["CP-02"] = dict({"codigo": "CP-02", "nombre": "Esquema y tipos", "estado": "OK", "valor": firma, "nivel": 0},
                        **motor.hashes_esquema(cols))
    out["CP-05"] = dict({"codigo": "CP-05", "nombre": "Commit de la corrida citada", "nivel": 0}, **cp05)
    for cod in ("CP-03", "CP-04"):
        out[cod] = {"codigo": cod, "estado": "PENDIENTE_NIVEL_2", "detalle": PENDIENTES[cod], "nivel": 2}
    return out


def _cp05(log, ventana):
    if not ventana:
        return {"estado": "NO_EVALUADO", "detalle": "sin ventana de corrida declarada",
                "ultimo_commit": log["ultimo_commit"] if log else None}
    if not log:
        return {"estado": "NO_APLICA", "detalle": "el origen no es Delta"}
    en = dr.commits_en_ventana(log, ventana["inicio_utc"], ventana["fin_utc"])
    return {"estado": "OK" if en else "ERROR",
            "detalle": (f"{len(en)} commit(s) de escritura dentro de la corrida" if en else
                        "ningun commit de escritura dentro de la ventana: la corrida citada NO escribio esta tabla "
                        "(si el flujo terminó bien, revisar roles entrada/salida)"),
            "commits": en, "ventana": ventana, "ultimo_commit": log["ultimo_commit"]}


def _armar(plataforma, ubicacion, tipo_fuente, cols, agg, log, ventana, t0, extra=None):
    perfil, sin_est = _perfil(cols, agg)
    aproximado = bool(agg.get("filas_borradas_dv"))
    ctl = _controles(cols, perfil, agg["filas"], sin_est, _cp05(log, ventana), aproximado)
    return {
        "tipo_reporte": "rapido", "version": VERSION, "plataforma": plataforma,
        "objeto": dict({"ubicacion": ubicacion, "tipo_fuente": tipo_fuente}, **(extra or {})),
        "medido_utc": _iso(), "segundos": round(time.time() - t0, 2),
        "nivel0": {"columnas": [{k: c[k] for k in ("orden", "nombre", "tipo", "nullable")} for c in cols],
                   "num_columnas": len(cols), **motor.hashes_esquema(cols),
                   "version_delta": log["version"] if log else None,
                   "ultimo_commit": log["ultimo_commit"] if log else None,
                   "particiones": log["particiones"] if log else None,
                   "column_mapping": log["column_mapping"] if log else None},
        "nivel1": {"filas": agg["filas"], "archivos": agg["archivos"], "fuente": "pies_parquet",
                   "filas_borradas_dv": agg.get("filas_borradas_dv", 0),
                   "columnas": {c["nombre"]: {k: perfil[c["nombre"]][k] for k in
                                              ("nulos", "pct_nulos", "minimo", "maximo", "es_constante", "nivel_perfil")}
                                for c in cols},
                   "sin_estadisticas": sin_est},
        "controles": ctl,
        "pendiente_nivel2": sorted(PENDIENTES),
        "costo": {"pedidos_rango": agg.get("pedidos"), "bytes_leidos": agg.get("bytes_leidos"),
                  "bytes_objeto": agg.get("bytes_objeto")},
    }


def medir_delta(tabla, ventana=None, ws=None, lh=None):
    """Tabla Delta de OneLake. `ventana` = {inicio_utc, fin_utc} de la corrida citada (ISO)."""
    t0 = time.time()
    base = dr.resolver_tabla(tabla, ws, lh)
    if not base:
        raise FileNotFoundError(f"no existe la tabla {tabla} en el lakehouse")
    log = dr.leer_log(base, ws, lh)
    cols = dr.columnas(log)
    viv = list(log["vigentes"].values())
    abridores = [(lambda a=a: ol.ArchivoRemoto(f"{base}/{_unq(a['path'])}", int(a.get("size") or 0), ws, lh))
                 for a in viv]
    ps = P.leer_muchos(abridores) if viv else []
    dv = sum(int((a.get("deletionVector") or {}).get("cardinality") or 0) for a in viv)
    agg = P.agregar(ps, restar_filas=dv) if ps else {"filas": 0, "archivos": 0, "columnas": {}, "pedidos": 0, "bytes_leidos": 0}
    agg["filas_borradas_dv"] = dv
    agg["bytes_objeto"] = sum(int(a.get("size") or 0) for a in viv)
    st = [a.get("stats") or {} for a in viv]
    n_stats = sum(int(s.get("numRecords") or 0) for s in st) - dv if all("numRecords" in s for s in st) else None
    rep = _armar("FABRIC", base, "DELTA", cols, agg, log, ventana, t0,
                 {"tabla": tabla, "conteo_por_stats_delta": n_stats})
    if n_stats is not None and n_stats != agg["filas"]:
        rep["advertencias"] = [f"numRecords del _delta_log ({n_stats}) != filas de los pies ({agg['filas']})"]
    return rep


def medir_parquets(archivos, abrir, plataforma, ubicacion, tipo_fuente="PARQUET", ventana=None, extra=None, hilos=None):
    """Carpeta de parquet (Files/ de OneLake, HDFS por Rocket con Range, o local).
    archivos = [(ruta, bytes)]; abrir(ruta, bytes) -> objeto archivo."""
    t0 = time.time()
    ps = P.leer_muchos([(lambda r=r, s=s: abrir(r, s)) for r, s in archivos], hilos)
    agg = P.agregar(ps)
    agg["bytes_objeto"] = sum(s for _, s in archivos)
    ref = max(ps, key=lambda p: len(p["columnas"]))["columnas"] if ps else {}
    cols = [{"orden": c["orden"], "nombre": n, "tipo": c["tipo"], "nullable": True, "fisico": n}
            for n, c in sorted(ref.items(), key=lambda kv: kv[1]["orden"])]
    rep = _armar(plataforma, ubicacion, tipo_fuente, cols, agg, None, ventana, t0, extra)
    mixtos = {n: a["tipos_vistos"] for n, a in agg["columnas"].items() if len(a["tipos_vistos"]) > 1}
    if mixtos:
        rep.setdefault("advertencias", []).append(f"tipos distintos entre archivos: {mixtos}")
    return rep


def medir_files(directorio, ventana=None, ws=None, lh=None):
    """Carpeta parquet en Files/ de OneLake."""
    arch = [(p["name"], p["contentLength"]) for p in ol.listar(directorio, True, ws, lh)
            if not p["isDirectory"] and p["name"].endswith(".parquet")
            and not p["name"].rsplit("/", 1)[-1].startswith(("_", "."))]
    if not arch:
        raise FileNotFoundError(f"sin parquet en {directorio} (CSV u otro formato: requiere descarga)")
    return medir_parquets(arch, lambda r, s: ol.ArchivoRemoto(r, s, ws, lh), "FABRIC", directorio, "PARQUET_FILES", ventana)


def _unq(p):
    import urllib.parse
    return urllib.parse.unquote(p)
