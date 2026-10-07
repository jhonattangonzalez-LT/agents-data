"""Nivel 2 · medicion COMPLETA en local (SHA-256, duplicados, llaves, perfil) con el motor v15.

Regla: todas las metricas se calculan en local; solo Postgres puede medirse dentro de la base
(nivel 0/1). Para el nivel 2 SIEMPRE se descarga a la cache: Fabric (parquet vigentes del _delta_log
o Files/), Stratio (HDFS por Rocket, SFTP, Postgres extraida). Los dos lados se miden con el MISMO
motor, asi la medicion es simetrica.

Flujo por objeto y lado:  bajar_*() -> registrar en cache -> vista() -> medir() -> reporte JSON.
"""
import datetime
import glob
import json
import os
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor

from ..acceso import onelake as ol
from ..cache import gestor
from ..config import CFG, PAR, RAIZ
from ..rapido import delta_remoto as dr
from . import motor_v15 as motor


# ----------------------------------------------------------------- descargas
def bajar_delta_fabric(lote, clave, tabla, ws=None, lh=None, log=print):
    """_delta_log + SOLO los parquet vigentes (y sus deletion vectors)."""
    base = dr.resolver_tabla(tabla, ws, lh)
    if not base:
        raise FileNotFoundError(f"no existe {tabla}")
    dl = dr.leer_log(base, ws, lh)
    dest = gestor.carpeta(lote, "FABRIC", clave)
    vig = list(dl["vigentes"].values())
    total = sum(int(a.get("size") or 0) for a in vig)
    if not gestor.cabe(total):
        raise RuntimeError(f"sin espacio en la cache para {total/1e9:.1f} GB ({gestor.espacio()})")
    t0 = time.time()
    # el _delta_log completo (delta_scan lo necesita) + vigentes + DV
    logs = [p for p in ol.listar(f"{base}/_delta_log", False, ws, lh) if not p["isDirectory"]]
    tareas = [(p["name"], os.path.join(dest, "_delta_log", p["name"].rsplit("/", 1)[-1]), p["contentLength"]) for p in logs]
    for a in vig:
        rel = urllib.parse.unquote(a["path"])
        tareas.append((f"{base}/{rel}", os.path.join(dest, rel), int(a.get("size") or 0)))
    dvs = _dv_archivos([a["deletionVector"] for a in vig if (a.get("deletionVector") or {}).get("storageType") == "u"])
    tareas += [(f"{base}/{d}", os.path.join(dest, d), None) for d in dvs]
    with ThreadPoolExecutor(PAR["onelake_hilos"]) as ex:
        list(ex.map(lambda t: ol.bajar(t[0], t[1], t[2], ws, lh), tareas))
    archivos = [os.path.join(dest, urllib.parse.unquote(a["path"])) for a in vig]
    # una re-descarga deja en la cache los parquet de versiones anteriores y la medicion los leeria: fuera
    from ..acceso.rocket import _limpiar_obsoletos
    _limpiar_obsoletos(dest, [t[1] for t in tareas], log)
    meta = {"tabla": tabla, "base": base, "version_delta": dl["version"], "ultimo_commit": dl["ultimo_commit"],
            "deletion_vectors": len(dvs), "column_mapping": dl["column_mapping"], "lector": "delta" if dvs or dl["column_mapping"] else "parquet",
            "segundos": round(time.time() - t0, 1)}
    gestor.registrar(lote, "FABRIC", clave, f"onelake:{base}", archivos, meta)
    log(f"fabric {tabla}: v{dl['version']} {len(archivos)} parquet {total/1e6:.1f} MB en {meta['segundos']}s")
    return dest, archivos, meta


def bajar_files_fabric(lote, clave, directorio, ws=None, lh=None, log=print):
    ps = [p for p in ol.listar(directorio, True, ws, lh) if not p["isDirectory"]
          and not p["name"].rsplit("/", 1)[-1].startswith(("_", "."))]
    dest = gestor.carpeta(lote, "FABRIC", clave)
    pref = directorio.rstrip("/") + "/"
    with ThreadPoolExecutor(PAR["onelake_hilos"]) as ex:
        locs = list(ex.map(lambda p: ol.bajar(p["name"], os.path.join(dest, p["name"][len(pref):]), p["contentLength"], ws, lh), ps))
    meta = {"directorio": directorio, "lector": _lector(locs), "ultima_modificacion": max((p.get("lastModified") or "") for p in ps) if ps else None}
    gestor.registrar(lote, "FABRIC", clave, f"onelake:{directorio}", locs, meta)
    return dest, locs, meta


def bajar_hdfs_stratio(lote, clave, ruta_hdfs, desde=None, log=print, particion=None):
    from ..acceso import rocket
    dest = gestor.carpeta(lote, "STRATIO", clave)
    locs, m = rocket.bajar(ruta_hdfs, dest, desde=desde, log=log, particion=particion)
    m.update(ruta=ruta_hdfs, desde=desde, particion=particion, lector=_lector(locs))
    gestor.registrar(lote, "STRATIO", clave, f"hdfs:{ruta_hdfs}", locs, m)
    return dest, locs, m


def bajar_sftp_stratio(lote, clave, directorio, patron=None, log=print):
    import re
    from ..acceso import stratio_pg
    dest = gestor.carpeta(lote, "STRATIO", clave)
    os.makedirs(dest, exist_ok=True)
    t, sf = stratio_pg.sftp()
    locs = []
    try:
        for a in sf.listdir_attr(directorio):
            if a.st_mode is not None and (a.st_mode & 0o170000) == 0o040000:
                continue
            if patron and not re.search(patron, a.filename):
                continue
            loc = os.path.join(dest, a.filename)
            if not (os.path.exists(loc) and os.path.getsize(loc) == a.st_size):
                sf.get(f"{directorio.rstrip('/')}/{a.filename}", loc)
            locs.append(loc)
    finally:
        sf.close()
        t.close()
    m = {"directorio": directorio, "patron": patron, "lector": _lector(locs)}
    gestor.registrar(lote, "STRATIO", clave, f"sftp:{directorio}", locs, m)
    return dest, locs, m


def _pg_select(cols):
    """Tipos que viajan distinto por psycopg/duckdb y por la Copy de Fabric -> ::text en los dos lados."""
    nativos = {"smallint", "integer", "bigint", "text", "character varying", "character", "boolean",
               "double precision", "real", "date"}
    q = motor.q
    return ", ".join(q(c["column_name"]) if c["data_type"] in nativos else f"{q(c['column_name'])}::text as {q(c['column_name'])}"
                     for c in cols)


def bajar_pg_stratio(lote, clave, tabla, where=None, log=print):
    """Extrae con DuckDB (extension postgres) a parquet. VPN < 1 MB/s: tablas chicas o cortes."""
    import duckdb
    from ..acceso import stratio_pg
    from ..pgfabric import sql as S
    cf = json.load(open(os.path.expanduser(CFG["secretos"]["stratio_conn"])))["postgres"]
    cols, filas = stratio_pg.consultar(S.esquema(tabla))
    esq = [dict(zip(cols, f)) for f in filas]
    s, t = tabla.split(".", 1)
    sql_txt = f'select {_pg_select(esq)} from "{s}"."{t}"' + (f" where {where}" if where else "")
    dest = gestor.carpeta(lote, "STRATIO", clave)
    os.makedirs(dest, exist_ok=True)
    loc = os.path.join(dest, "datos.parquet")
    con = duckdb.connect(config={"memory_limit": "2GB", "threads": "2"})
    con.execute("load postgres")
    dsn = (f"host={cf['host']} port={cf['port']} dbname={cf['dbname']} user={cf['user']} "
           f"password={cf['password']} connect_timeout=60")
    con.execute(f"attach {motor.lit(dsn)} as pg (type postgres, read_only)")
    t0 = time.time()
    con.execute(f"copy (select * from postgres_query('pg', {motor.lit(sql_txt)})) to {motor.lit(loc + '.part')} "
                f"(format parquet, compression zstd, row_group_size 500000)")
    con.close()
    os.replace(loc + ".part", loc)
    m = {"tabla": tabla, "where": where, "esquema_postgres": esq, "lector": "parquet", "segundos": round(time.time() - t0, 1)}
    gestor.registrar(lote, "STRATIO", clave, f"pg:{tabla}", [loc], m)
    return dest, [loc], m


def bajar_pg_fabric(lote, clave, tabla, where=None, log=print):
    """Por la pipeline qa_v2_postgres: Copy a parquet en Files/ y descarga."""
    from ..pgfabric import pipeline, sql as S
    esq, _ = pipeline.consultar(S.esquema(tabla))
    esq = sorted(esq, key=lambda c: int(c["ordinal_position"]))
    s, t = tabla.split(".", 1)
    sql_txt = f'select {_pg_select(esq)} from "{s}"."{t}"' + (f" where {where}" if where else "")
    r = pipeline.ejecutar(sql_txt, archivo="datos.parquet", timeout="02:00:00")
    if r["estado"] != "Completed":
        raise RuntimeError(f"pipeline qa_v2_postgres {r['estado']}: {json.dumps(r.get('error'))[:300]}")
    dest = gestor.carpeta(lote, "FABRIC", clave)
    loc = pipeline.resultado(r["ruta_onelake"], os.path.join(dest, "datos.parquet"))
    m = {"tabla": tabla, "where": where, "esquema_postgres": esq, "lector": "parquet", "pipeline": r}
    gestor.registrar(lote, "FABRIC", clave, f"pgfab:{tabla}", [loc], m)
    return dest, [loc], m


def _lector(locs):
    ext = {os.path.splitext(p[:-3] if p.endswith(".gz") else p)[1].lower() for p in locs}
    if ext <= {".parquet", ""}:
        return "parquet"
    if ext & {".csv", ".txt"}:
        return "csv"
    return "parquet"


_Z85 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-:+=^!/*?&<>()[]{}@%$#"


def _dv_archivos(dvs):
    out = set()
    for dv in dvs:
        pid = dv["pathOrInlineDv"]
        pref, cod = pid[:-20], pid[-20:]
        b = bytearray()
        for i in range(0, len(cod), 5):
            v = 0
            for ch in cod[i:i + 5]:
                v = v * 85 + _Z85.index(ch)
            b += v.to_bytes(4, "big")
        nombre = f"deletion_vector_{uuid.UUID(bytes=bytes(b))}.bin"
        out.add(f"{pref}/{nombre}" if pref else nombre)
    return out


# ----------------------------------------------------------------- vista y medicion
def base_csv(con, archivos, csv=None):
    """SQL de lectura de un CSV (RFC 4180). Si no se declara la codificacion se prueba UTF-8 y luego Latin-1;
    devuelve (sql, codificacion) para dejar escrito con que se leyo (explica diferencias de acentos)."""
    opciones = dict(csv or {})
    cods = [opciones.pop("encoding").strip("'")] if "encoding" in opciones else ["utf-8", "latin-1"]
    extra = "".join(f", {k}={v}" for k, v in opciones.items())
    ultimo = None
    for cod in cods:
        sql = (f"read_csv({sorted(archivos)!r}, all_varchar=true, union_by_name=true, quote='\"', escape='\"', "
               f"encoding='{cod}'{extra})")
        try:
            con.execute(f"select count(*) from {sql}").fetchone()
            return sql, cod
        except Exception as e:
            ultimo = e
    raise ultimo


def conectar():
    m = CFG["medicion"]
    # una carpeta de desborde por CONEXION (proceso + hilo): dos DuckDB en la misma carpeta se pisan los .tmp (IO Error)
    import threading
    spill = os.path.join(RAIZ, "cache", ".spill", f"{os.getpid()}_{threading.get_ident()}")
    return motor.conectar(spill, memoria=m["duckdb_memoria"], hilos=m["duckdb_hilos"])


def vista(con, carpeta, lector, archivos=None, csv=None, filtro=None, excluir=(), tipos_pg=None, nombre="T",
          cast_varchar=None):
    """Crea la vista `nombre` sobre lo descargado. lector: delta | parquet | csv."""
    if lector == "delta":
        con.execute("install delta; load delta")
        base = f"delta_scan('{carpeta}')"
    elif lector == "parquet":
        arch = archivos or [p for p in glob.glob(f"{carpeta}/**/*", recursive=True)
                            if os.path.isfile(p) and not p.endswith((".part", ".crc", ".json", ".bin"))
                            and "/_" not in p[len(carpeta):] and "/." not in p[len(carpeta):]]
        hive = any("=" in p[len(carpeta):] for p in arch)
        opt = f"union_by_name=true, hive_partitioning={'true' if hive else 'false'}" + (", hive_types_autocast=false" if hive else "")
        if cast_varchar:
            obj = {c.lower() for c in cast_varchar}
            partes = []
            for p in arch:
                ns = [r[0] for r in con.execute(f"select name from parquet_schema('{p}')").fetchall()]
                rep = [n for n in ns if n.lower() in obj]
                sel = "*" + (f" replace ({', '.join(f'cast({motor.q(n)} as varchar) as {motor.q(n)}' for n in rep)})" if rep else "")
                partes.append(f"select {sel} from read_parquet('{p}', hive_partitioning={'true' if hive else 'false'})")
            base = "(" + " union all by name ".join(partes) + ")"
        else:
            base = f"read_parquet({arch!r}, {opt})"
    elif lector == "csv":
        arch = archivos or sorted(p for p in glob.glob(f"{carpeta}/**/*", recursive=True) if os.path.isfile(p)
                                  and not p.endswith((".part", ".json")))
        # RFC 4180: comillas dobles escapadas duplicandolas, saltos de linea dentro de comillas; codificacion probada
        base, codificacion = base_csv(con, arch, csv)
    else:
        raise ValueError(lector)
    cols = [r[0] for r in con.execute(f"describe select * from {base}").fetchall()]
    fuera = [c for c in excluir if c in cols]
    sel = "*" + (f" exclude ({', '.join(motor.q(c) for c in fuera)})" if fuera else "")
    if tipos_pg:
        M = {"date": "DATE", "integer": "INTEGER", "bigint": "BIGINT", "smallint": "SMALLINT", "real": "FLOAT",
             "double precision": "DOUBLE", "boolean": "BOOLEAN"}
        dec = {c["column_name"]: c["data_type"] for c in tipos_pg}
        sel = ", ".join(f"cast({motor.q(c)} as {M.get(dec.get(c), 'VARCHAR')}) as {motor.q(c)}" for c in cols if c not in fuera)
    con.execute(f"create or replace view {nombre} as select {sel} from {base}" + (f" where {filtro}" if filtro else ""))
    out = {"columnas_excluidas": fuera, "filtro": filtro, "columnas_origen": cols}
    if lector == "csv":
        out["codificacion_csv"] = codificacion
    return out


def medir(lote, clave, plataforma, carpeta, meta, *, nombre=None, flujo=None, grupo=None, filtro=None,
          excluir=(), csv=None, run_id=None, cast_varchar=None):
    """Mide el objeto descargado y deja el reporte en lotes/<lote>/nivel2/<PLAT>/<clave>.json."""
    con = conectar()
    try:
        v = vista(con, carpeta, meta.get("lector", "parquet"), csv=csv, filtro=filtro, excluir=excluir,
                  tipos_pg=meta.get("esquema_postgres"), cast_varchar=cast_varchar)
        rep = motor.medir(con, "T", plataforma=plataforma, clave=clave, nombre=nombre or clave,
                          ubicacion=meta.get("tabla") or meta.get("ruta") or meta.get("directorio") or carpeta,
                          flujo=flujo, tipo_fuente=meta.get("lector", "parquet").upper(),
                          run_id=run_id or uuid.uuid4().hex, excluidas_hash=(),
                          extra_objeto={"grupo": grupo, "lote": lote, "vista": v,
                                        "version_delta": meta.get("version_delta"),
                                        "ultimo_commit": meta.get("ultimo_commit")},
                          almacenamiento={k: meta.get(k) for k in ("version_delta", "deletion_vectors", "column_mapping")})
    finally:
        con.close()
    rep["ejecucion"]["etiqueta_corrida"] = f"pipeline_v2 lote {lote}"
    rep["ejecucion"]["herramienta"] = "pipeline-comfandi/pc/medir/completo.py"
    from .. import lote as _L
    out = os.path.join(_L.dir_lote(lote), "nivel2", plataforma.upper(), f"{clave}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(rep, open(out, "w"), indent=1, ensure_ascii=False, default=str)
    gestor.marcar(lote, plataforma, clave, "MEDIDO")
    try:
        from . import estimar
        n, cols, seg = rep["conteos"]["row_count"], rep["conteos"]["num_columnas"], rep["ejecucion"]["duracion_segundos"]
        pasadas = 2 + -(-cols // estimar.T["columnas_por_pasada"])
        if n > 1_000_000 and seg:
            estimar.registrar_tasa("medicion_filas_pasada_s", n * pasadas / 1e6, seg)   # en millones; se convierte al leer
    except Exception:
        pass
    return out, rep
