"""Pies (footers) de parquet leidos por rango: filas, nulos, minimo y maximo por columna sin bajar el dato.

Sirve para cualquier origen que acepte lecturas por rango: OneLake (siempre), Rocket (si
probar_rango() lo confirma) o archivos locales. Filas y nulos son exactos; el min/max puede
faltar en alguna columna segun el tipo o quien escribio el archivo: esa columna queda marcada
y su ID-06 se decide en nivel 2, nunca se da por cumplido.
"""
import datetime
import decimal
from concurrent.futures import ThreadPoolExecutor

from ..config import PAR


def _arrow_a_spark(t):
    import pyarrow as pa
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return "string"
    if pa.types.is_int64(t):
        return "bigint"
    if pa.types.is_int32(t):
        return "int"
    if pa.types.is_int16(t):
        return "smallint"
    if pa.types.is_int8(t):
        return "tinyint"
    if pa.types.is_decimal(t):
        return f"decimal({t.precision},{t.scale})"
    if pa.types.is_float64(t):
        return "double"
    if pa.types.is_float32(t):
        return "float"
    if pa.types.is_boolean(t):
        return "boolean"
    if pa.types.is_date(t):
        return "date"
    if pa.types.is_timestamp(t):
        return "timestamp"
    if pa.types.is_binary(t) or pa.types.is_large_binary(t):
        return "binary"
    if pa.types.is_null(t):
        return "void"
    if pa.types.is_struct(t) or pa.types.is_list(t) or pa.types.is_map(t):
        return "complejo"
    return str(t)


def _norm(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf8")
        except UnicodeDecodeError:
            return v.hex()
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return str(v)
    return v


def leer_pie(abrir):
    """abrir() devuelve un objeto archivo con seek/read (ArchivoRemoto, ArchivoRocket u open())."""
    import pyarrow.parquet as pq
    f = abrir()
    pf = pq.ParquetFile(f)
    md = pf.metadata
    esq = pf.schema_arrow
    cols = {}
    for i, campo in enumerate(esq):
        cols[campo.name] = {"tipo": _arrow_a_spark(campo.type), "nulos": 0, "min": None, "max": None,
                            "con_estadisticas": True, "orden": i}
    hojas = [md.schema.column(j).path for j in range(md.num_columns)]
    for rg in range(md.num_row_groups):
        g = md.row_group(rg)
        for j in range(g.num_columns):
            raiz = hojas[j].split(".")[0]
            if raiz not in cols:
                continue
            c = cols[raiz]
            if "." in hojas[j]:      # tipo anidado: sin min/max comparables
                c["con_estadisticas"] = False
                continue
            st = g.column(j).statistics
            if st is None or not st.has_null_count:
                c["con_estadisticas"] = False
                c["nulos"] = None
                continue
            if c["nulos"] is not None:
                c["nulos"] += st.null_count
            if st.has_min_max:
                mn, mx = _norm(st.min), _norm(st.max)
                try:
                    c["min"] = mn if c["min"] is None else min(c["min"], mn)
                    c["max"] = mx if c["max"] is None else max(c["max"], mx)
                except TypeError:
                    c["con_estadisticas"] = False
            elif g.column(j).num_values > st.null_count:
                c["con_estadisticas"] = False
    return {"filas": md.num_rows, "grupos": md.num_row_groups, "columnas": cols,
            "creado_por": md.created_by, "pedidos": getattr(f, "pedidos", 0),
            "bytes_leidos": getattr(f, "bytes_leidos", 0)}


def agregar(pies, restar_filas=0):
    """Suma los pies de varios archivos de la misma tabla."""
    total = sum(p["filas"] for p in pies) - restar_filas
    cols = {}
    for p in pies:
        for n, c in p["columnas"].items():
            a = cols.setdefault(n, {"tipo": c["tipo"], "nulos": 0, "min": None, "max": None,
                                    "con_estadisticas": True, "orden": c["orden"], "tipos_vistos": set()})
            a["tipos_vistos"].add(c["tipo"])
            if c["nulos"] is None or a["nulos"] is None:
                a["nulos"] = None
            else:
                a["nulos"] += c["nulos"]
            if not c["con_estadisticas"]:
                a["con_estadisticas"] = False
            for k, fn in (("min", min), ("max", max)):
                if c[k] is not None:
                    try:
                        a[k] = c[k] if a[k] is None else fn(a[k], c[k])
                    except TypeError:
                        a["con_estadisticas"] = False
    for n, a in cols.items():
        a["tipos_vistos"] = sorted(a["tipos_vistos"])
        # columna ausente en algunos archivos (esquema que evoluciona): sus nulos no son exactos
        presentes = sum(p["filas"] for p in pies if n in p["columnas"])
        if presentes != sum(p["filas"] for p in pies):
            a["con_estadisticas"] = False
            a["ausente_en_filas"] = sum(p["filas"] for p in pies) - presentes
    return {"filas": total, "archivos": len(pies), "columnas": cols,
            "pedidos": sum(p["pedidos"] for p in pies), "bytes_leidos": sum(p["bytes_leidos"] for p in pies)}


def leer_muchos(abridores, hilos=None):
    with ThreadPoolExecutor(hilos or PAR["onelake_hilos"]) as ex:
        return list(ex.map(leer_pie, abridores))
