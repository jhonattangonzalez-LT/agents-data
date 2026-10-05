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
