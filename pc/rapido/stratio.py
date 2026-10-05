"""Nivel 0/1 del lado de Stratio. SIN PROBAR (se prueba con VPN y cookie vigente).

  HDFS (Rocket)  si Rocket acepta Range -> pies de parquet por rango, sin descargar.
                 si no -> se descarga a la cache (el nivel 2 la necesita de todos modos) y se
                 leen los pies en local. El resultado de la prueba de Range se guarda una vez.
  Postgres       agregados dentro de la base (rapido/postgres.py, plataforma STRATIO).
  SFTP parquet   pies por rango (paramiko permite seek). CSV: requiere descarga (sin pie).
"""
import json
import os
import time

from ..acceso import rocket
from ..config import RAIZ
from . import nivel01, postgres

_PRUEBA = os.path.join(RAIZ, "cache", ".rocket_rango.json")


def rocket_acepta_rango(archivo_muestra=None, rehacer=False):
    """Una sola vez: ¿Rocket responde 206 a una peticion con Range? Guarda la respuesta."""
    if os.path.exists(_PRUEBA) and not rehacer:
        return json.load(open(_PRUEBA))
    if not archivo_muestra:
        raise ValueError("pasar la ruta HDFS de un .parquet pequeno para la prueba")
    r = rocket.probar_rango(archivo_muestra)
    r["probado_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    os.makedirs(os.path.dirname(_PRUEBA), exist_ok=True)
    json.dump(r, open(_PRUEBA, "w"), indent=1)
    return r


def medir_hdfs(ruta, desde=None, ventana=None):
    arch = [(p, s) for p, s, _m in rocket.arbol(ruta, desde=desde) if p.endswith(".parquet")]
    if not arch:
        raise FileNotFoundError(f"sin parquet en {ruta} (¿CSV? ¿Stratio reescribiendo?)")
    pr = rocket_acepta_rango(arch[0][0])
    if not pr.get("acepta"):
        return {"estado": "REQUIERE_DESCARGA", "motivo": f"Rocket no acepta Range (HTTP {pr.get('status')})",
                "archivos": len(arch), "bytes": sum(s for _, s in arch)}
    rep = nivel01.medir_parquets(arch, lambda r, s: rocket.ArchivoRocket(r, s), "STRATIO", ruta, "HDFS_PARQUET",
                                 ventana, {"desde": desde}, hilos=8)
    return rep


def medir_local(carpeta, ubicacion, plataforma="STRATIO", tipo_fuente="HDFS_PARQUET"):
    """Pies de parquet ya descargados a la cache (cuando Rocket no acepta Range)."""
    arch = []
    for r, _d, fs in os.walk(carpeta):
        for f in fs:
            if f.endswith(".parquet") and not f.startswith((".", "_")):
                p = os.path.join(r, f)
                arch.append((p, os.path.getsize(p)))
    return nivel01.medir_parquets(sorted(arch), lambda r, s: open(r, "rb"), plataforma, ubicacion, tipo_fuente,
                                  extra={"leido_de": "cache_local"})


def medir_pg(tabla, where=None):
    return postgres.medir(tabla, "STRATIO", where=where)


def medir_sftp_parquet(directorio, patron=None):
    import re
    from ..acceso import stratio_pg
    t, sf = stratio_pg.sftp()
    try:
        todos = [a for a in sf.listdir_attr(directorio) if not patron or re.search(patron, a.filename)]
        arch = [(f"{directorio.rstrip('/')}/{a.filename}", a.st_size) for a in todos if a.filename.endswith(".parquet")]
        if not arch:
            return {"estado": "REQUIERE_DESCARGA", "motivo": "SFTP sin parquet (CSV u otro texto: no tiene pie)",
                    "archivos": len(todos), "bytes": sum(a.st_size for a in todos)}
        rep = nivel01.medir_parquets(arch, lambda r, s: sf.open(r, "rb"), "STRATIO", directorio, "SFTP_PARQUET", hilos=1)
    finally:
        sf.close()
        t.close()
    return rep


def medir_local_csv(archivos, ubicacion, csv=None, plataforma="STRATIO"):
    """Nivel 0/1 de un CSV ya descargado (no tiene pie): conteo, nulos y min/max por columna con DuckDB.
    Lector RFC 4180 (comillas dobles escapadas duplicandolas, saltos de linea dentro de comillas). Todo texto."""
    import time as _t
    import duckdb
    t0 = _t.time()
    from ..medir.completo import base_csv
    con = duckdb.connect()
    base, codificacion = base_csv(con, archivos, csv)
    cols = [r[0] for r in con.execute(f"describe select * from {base}").fetchall()]
    q = lambda c: '"' + c.replace('"', '""') + '"'
    sel = ["count(*)"] + [x for c in cols for x in (f"count({q(c)})", f"min({q(c)})", f"max({q(c)})")]
    r = con.execute(f"select {', '.join(sel)} from {base}").fetchone()
    con.close()
    filas = r[0]
    agg_cols = {}
    for i, c in enumerate(cols):
        nn, mn, mx = r[1 + 3 * i], r[2 + 3 * i], r[3 + 3 * i]
        agg_cols[c] = {"tipo": "string", "orden": i, "nulos": filas - nn, "min": mn, "max": mx, "con_estadisticas": True}
    agg = {"filas": filas, "archivos": len(archivos), "columnas": agg_cols, "pedidos": 0, "bytes_leidos": 0,
           "bytes_objeto": sum(os.path.getsize(a) for a in archivos)}
    cl = [{"orden": i, "nombre": c, "tipo": "string", "nullable": True, "fisico": c} for i, c in enumerate(cols)]
    rep = nivel01._armar(plataforma, ubicacion, "CSV", cl, agg, None, None, t0, {"leido_de": "cache_local", "lector": "csv RFC 4180", "codificacion": codificacion})
    rep["nivel1"]["fuente"] = "csv_local"
    return rep
