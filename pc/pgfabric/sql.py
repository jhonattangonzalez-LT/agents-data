"""SQL de medicion para Postgres (el mismo texto sirve en la de Stratio y en la de Fabric).

Nivel 0: information_schema (esquema declarado).  Nivel 1: conteo, nulos, min/max y longitudes,
por bloques de columnas para no cargar la base. Nivel 2 en base: distintos exactos y duplicados
de fila con md5(fila::text) (NO es el SHA-256 canonico: el hash del dataset exige extraer).
"""
TEXTO = ("text", "character varying", "character", "citext")
NO_ORDENABLE = ("json", "jsonb", "xml", "bytea", "ARRAY", "USER-DEFINED", "tsvector")


def q(n):
    return '"' + str(n).replace('"', '""') + '"'


def lit(s):
    return "'" + str(s).replace("'", "''") + "'"


def esquema(tabla):
    s, t = tabla.split(".", 1)
    return ("select column_name, data_type, is_nullable, ordinal_position::int as ordinal_position, "
            "numeric_precision::int as numeric_precision, numeric_scale::int as numeric_scale, "
            "character_maximum_length::int as character_maximum_length "
            f"from information_schema.columns where table_schema = {lit(s)} and table_name = {lit(t)} "
            "order by ordinal_position")


def existe(tabla):
    s, t = tabla.split(".", 1)
    return ("select count(*)::int as n from information_schema.tables "
            f"where table_schema = {lit(s)} and table_name = {lit(t)}")


def _desde(tabla, where=None):
    s, t = tabla.split(".", 1)
    return f"from {q(s)}.{q(t)}" + (f" where {where}" if where else "")


def agregados(tabla, cols, where=None, con_distintos=False):
    """Una fila: n + por columna (i): nn_i, mn_i, mx_i [, lmin_i, lmax_i, vac_i] [, d_i]. Todo ::text
    o ::bigint para que viaje igual por la Copy de Fabric y por psycopg2."""
    sel = ["count(*)::bigint as n"]
    for i, c in enumerate(cols):
        n, dt = q(c["column_name"]), c["data_type"]
        sel.append(f"count({n})::bigint as nn_{i}")
        if dt in NO_ORDENABLE:
            continue
        if dt == "boolean":
            sel += [f"min({n}::int)::text as mn_{i}", f"max({n}::int)::text as mx_{i}"]
        else:
            sel += [f"min({n})::text as mn_{i}", f"max({n})::text as mx_{i}"]
        if dt in TEXTO:
            sel += [f"min(length({n}))::bigint as lmin_{i}", f"max(length({n}))::bigint as lmax_{i}",
                    f"sum(case when {n} = '' then 1 else 0 end)::bigint as vac_{i}"]
        if con_distintos:
            sel.append(f"count(distinct {n})::bigint as d_{i}")
    return f"select {', '.join(sel)} {_desde(tabla, where)}"


def duplicados(tabla, cols, where=None):
    lista = ", ".join(q(c["column_name"]) for c in cols)
    return (f"select count(*)::bigint as n, count(distinct md5(row({lista})::text))::bigint as distintas "
            f"{_desde(tabla, where)}")


def bloques(cols, tam):
    return [cols[i:i + tam] for i in range(0, len(cols), tam)]


# ------------------------------------------------------- trozos por ctid (tablas grandes en Fabric)
# La Copy de Fabric corta el socket si la consulta pasa ~40 s sin devolver filas (agregados sobre una
# tabla grande). Se parte el barrido por rangos de paginas (TID Range Scan, Postgres >= 14: no requiere
# indice) y se combinan los agregados de forma EXACTA: sumas y min/max; los min/max de valores se
# combinan otra vez dentro de la base, con el tipo declarado y su collation (no en Python).
_CAST = {"character": "bpchar", "character varying": "varchar"}


def paginas(tabla):
    s, t = tabla.split(".", 1)
    return ("select c.relpages::bigint as paginas from pg_class c join pg_namespace n on n.oid = c.relnamespace "
            f"where n.nspname = {lit(s)} and c.relname = {lit(t)}")


def trozos_ctid(n_paginas, tam):
    """Condiciones que cubren TODA la tabla: el ultimo trozo queda abierto (relpages es una estimacion)."""
    cortes = list(range(0, int(n_paginas), int(tam)))[1:]
    lim = [None] + cortes + [None]
    out = []
    for a, b in zip(lim, lim[1:]):
        c = []
        if a is not None:
            c.append(f"ctid >= '({a},0)'::tid")
        if b is not None:
            c.append(f"ctid < '({b},0)'::tid")
        out.append(" and ".join(c) or "true")
    return out


def y(where, extra):
    return f"({where}) and {extra}" if where else extra


def combinar(cols, partes, ejecutor):
    """Une los resultados de `agregados` por trozo en una sola fila, exacta. `ejecutor(sql)` -> filas."""
    def suma(k):
        v = [p.get(k) for p in partes if p.get(k) is not None]
        return sum(int(x) for x in v) if v else None

    def ext(k, f):
        v = [int(p[k]) for p in partes if p.get(k) is not None]
        return f(v) if v else None

    fila = {"n": suma("n")}
    sel = []
    for i, c in enumerate(cols):
        fila[f"nn_{i}"] = suma(f"nn_{i}")
        dt = c["data_type"]
        if dt in NO_ORDENABLE:
            continue
        tipo = "int" if dt == "boolean" else _CAST.get(dt, dt)
        for k, fn in ((f"mn_{i}", "min"), (f"mx_{i}", "max")):
            vals = [p[k] for p in partes if p.get(k) is not None]
            if not vals:
                fila[k] = None
                continue
            filas_v = ", ".join(f"({lit(v)})" for v in vals)
            sel.append(f"(select {fn}(v::{tipo})::text from (values {filas_v}) t(v)) as {k}")
        if dt in TEXTO:
            fila[f"lmin_{i}"] = ext(f"lmin_{i}", min)
            fila[f"lmax_{i}"] = ext(f"lmax_{i}", max)
            fila[f"vac_{i}"] = suma(f"vac_{i}")
    if sel:
        fila.update(ejecutor("select " + ", ".join(sel))[0])
    return fila
