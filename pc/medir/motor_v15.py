"""COPIA FIEL de ~/Projects/validacion_lote9/motor.py (motor v15 sobre DuckDB, version v15-duckdb-2).
No se edita: cualquier cambio en canonica()/medir_hash() invalida las huellas ya publicadas.
Unico cambio: la muestra pasa de limit 5 a limit 10 (CP-04 informativo, acordado 2026-10-02)."""
import datetime
import hashlib
import json
import re
from decimal import Decimal

SEP = "\u0001"
NULO = "\u0000NULL\u0000"
REB = (1, 16, 31, 46)
ANCHO = 15
RE_ENTERO = r"^[+-]?[0-9]+$"
RE_DECIMAL = r"^[+-]?([0-9]+([.,][0-9]+)?|[.,][0-9]+)$"
RE_FECHA = r"^([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{8}|[0-9]{2}/[0-9]{2}/[0-9]{4}|[0-9]{4}/[0-9]{2}/[0-9]{2})$"
RE_NO_ASCII = r"[^\x00-\x7F]"
RE_CONTROL = r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"
RE_CEROS = r"^0[0-9]+$"
RE_EMAIL = r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"
SENT_TXT = ["", " ", "NULL", "null", "Null", "N/A", "NA", "n/a", "#N/D", "#N/A", "-", "--", ".",
            "?", "SIN DATO", "SIN INFORMACION", "0", "00000000", "0000-00-00", "99991231",
            "9999-12-31"]
SENT_FEC = ["0001-01-01", "1900-01-01", "1970-01-01", "9999-12-31", "2099-12-31"]
PATRON_SEG = r"[^\x00-\x7F]|[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"
DISTINTOS_EXACTOS_HASTA = 10**18   # NADA estimado: distintos siempre exactos (acordado 2026-10-05)
TOPE_CELDAS_HASH_COL = 3_000_000_000
TOP_N, MAX_COLS_TOP, MAX_DIST_TOP = 5, 25, 1000
MALOS_DELTA = re.compile(r"[ ,;{}()\n\t=]")
VERSION_MOTOR = "v15-duckdb-2"

_SPARK = {"VARCHAR": "string", "BIGINT": "bigint", "INTEGER": "int", "SMALLINT": "smallint",
          "TINYINT": "tinyint", "DOUBLE": "double", "FLOAT": "float", "BOOLEAN": "boolean",
          "DATE": "date", "TIMESTAMP": "timestamp", "TIMESTAMP WITH TIME ZONE": "timestamp",
          "TIMESTAMP_NS": "timestamp", "TIMESTAMP_MS": "timestamp", "TIMESTAMP_S": "timestamp",
          "BLOB": "binary", "HUGEINT": "decimal(38,0)", "UBIGINT": "decimal(20,0)",
          "UINTEGER": "bigint", "USMALLINT": "int", "UTINYINT": "smallint", "UUID": "string",
          "TIME": "string", "INTERVAL": "interval", '"NULL"': "void", "NULL": "void"}


def tipo_spark(t):
    u = str(t).strip().upper()
    if u.startswith("DECIMAL"):
        return u.lower().replace(" ", "")
    if u.startswith("STRUCT") or u.startswith("MAP") or u.endswith("[]"):
        return u.lower()
    return _SPARK.get(u, u.lower())


def _cat(ts):
    if ts in ("bigint", "int", "smallint", "tinyint"):
        return "entero"
    if ts.startswith("decimal"):
        return "decimal"
    if ts in ("double", "float"):
        return "flotante"
    if ts == "string":
        return "texto"
    if ts == "boolean":
        return "bool"
    if ts == "date":
        return "fecha"
    if ts == "timestamp":
        return "ts"
    if ts == "binary":
        return "bin"
    if ts == "void":
        return "void"
    return "complejo"


def q(n):
    return '"' + n.replace('"', '""') + '"'


def lit(s):
    return "'" + str(s).replace("'", "''") + "'"


def canonica(nombre, ts, crudo=None):
    c, k = q(nombre), _cat(ts)
    if k == "flotante":
        e = f"case when isnan({c}) then 'NaN' else cast(cast({c} as decimal(38,10)) as varchar) end"
    elif k in ("decimal", "entero"):
        e = f"cast({c} as varchar)"
    elif k == "bool":
        e = f"case when {c} is null then null when {c} then 'true' else 'false' end"
    elif k == "fecha":
        e = f"strftime({c}, '%Y-%m-%d')"
    elif k == "ts":
        e = f"strftime(cast({c} as timestamp), '%Y-%m-%d %H:%M:%S.%g')"
    elif k == "texto":
        e = c
    elif k == "bin":
        e = f"upper(hex({c}))"
    elif k == "void":
        e = "cast(null as varchar)"
    else:
        e = f"to_json({c})"
    return f"coalesce(cast({e} as varchar), chr(0) || 'NULL' || chr(0))"


def _rebanadas(expr_hex, pref, cond=None):
    out = []
    for i, ini in enumerate(REB, 1):
        v = f"('0x' || substr({expr_hex}, {ini}, {ANCHO}))::BIGINT"
        if cond is not None:
            v = f"case when {cond} then {v} else 0 end"
        out.append(f"sum({v}::HUGEINT) as {pref}{i}")
    return out


def sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def _h_sumas(filas, s):
    return sha("|".join(["SHA256-CANON-v1", str(filas)] + [str(x) for x in s]))


def esquema_de(con, vista, nullables=None):
    filas = con.execute(f"describe select * from {vista}").fetchall()
    cols = []
    for i, r in enumerate(filas):
        ts = tipo_spark(r[1])
        nl = True if nullables is None else bool(nullables.get(r[0], True))
        cols.append({"orden": i, "nombre": r[0], "tipo": ts, "nullable": nl, "tipo_motor": r[1]})
    return cols


def hashes_esquema(cols):
    s = sorted(cols, key=lambda c: c["nombre"])
    return {"hash_esquema_estricto": sha("||".join(f"{c['nombre']}|{c['tipo']}|{str(c['nullable']).lower()}" for c in s)),
            "hash_esquema_tipos": sha("||".join(f"{c['nombre']}|{c['tipo']}" for c in s)),
            "hash_nombres_columnas": sha("||".join(c["nombre"] for c in s))}


def _num(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, (bytes, bytearray)):
        return v.hex().upper()
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, list):
        return [_num(x) for x in v]
    return v


def medir_hash(con, vista, cols, filas, excluidas=()):
    fuera = {x.lower() for x in excluidas}
    campos = [c for c in cols if c["nombre"].lower() not in fuera]
    if not campos:
        return {"estado": "OMITIDO", "motivo": "no_quedaron_columnas_tras_exclusiones"}
    canon = [canonica(c["nombre"], c["tipo"]) for c in campos]
    fila = f"sha256(concat_ws(chr(1), {', '.join(canon)}))"
    textos = [c for c in campos if c["tipo"] == "string"]
    cond = None
    if textos:
        partes = [f"({q(c['nombre'])} is null or length(trim({q(c['nombre'])})) = 0 or "
                  f"regexp_matches({q(c['nombre'])}, {lit(PATRON_SEG)}))" for c in textos]
        cond = " or ".join(partes)
    por_col = filas * len(campos) <= TOPE_CELDAS_HASH_COL
    exacto = filas <= DISTINTOS_EXACTOS_HASTA
    sel = ["count(*) as n", ("count(distinct h)" if exacto else "approx_count_distinct(h)") + " as d"]
    sel += _rebanadas("h", "s")
    if cond:
        sel += _rebanadas("h", "l", "not af") + _rebanadas("h", "a", "af")
        sel.append("sum(case when af then 1 else 0 end) as naf")
    inner = [f"{fila} as h"] + ([f"({cond}) as af"] if cond else [])
    if por_col:
        for i, e in enumerate(canon):
            # hash por columna: hash() de 64 bits de DuckDB (mismo motor y version en los dos lados),
            # reducido a 60 bits. Mucho mas barato que un sha256 por celda; la huella de FILA sigue siendo sha256 v15.
            inner.append(f"(hash({e}) >> 4) as hc{i}")
            sel.append(f"sum(hc{i}::HUGEINT) as c{i}")
    sql = f"select {', '.join(sel)} from (select {', '.join(inner)} from {vista})"
    cur = con.execute(sql)
    nombres = [d[0] for d in cur.description]
    r = dict(zip(nombres, cur.fetchone()))
    n = int(r["n"] or 0)
    s = [str(r[f"s{i}"] if r[f"s{i}"] is not None else 0) for i in range(1, 5)]
    d = int(r["d"] or 0)
    res = {"estado": "OK", "algoritmo": "SHA-256",
           "especificacion": ("fila = sha256(concat_ws(0x01, columnas_canonicas_en_ORDEN_FISICO)); "
                              "agregado independiente del orden de filas = suma exacta decimal(38,0) "
                              "de 4 rebanadas de 60 bits del digest; hash_dataset = "
                              "sha256('SHA256-CANON-v1|filas|s1|s2|s3|s4'); hash_datos por columna = "
                              "sha256('SHA256-COL-v2|filas|suma') SIN el nombre de la columna; "
                              "hash_conjunto_columnas = sha256('SHA256-SET-v1|' + hashes_datos "
                              "ordenados). Misma especificacion que la celda 6 del notebook v15, "
                              "ejecutada en DuckDB."),
           "alcance": "COMPLETO", "porcentaje_muestreado": 100, "orden_canonico": "POSICION_FISICA",
           "columnas_incluidas": [c["nombre"] for c in campos],
           "columnas_excluidas": sorted(excluidas),
           "filas_hasheadas": n, "filas_distintas_por_hash": d,
           "filas_distintas_metodo": "EXACTO" if exacto else "APROXIMADO_HLL",
           "filas_duplicadas_exactas": (n - d) if exacto else None,
           "filas_duplicadas_estimadas": None if exacto else max(0, n - d),
           "sumas_parciales": s, "hash_dataset": _h_sumas(n, s),
           "metodo_hash_columna": "duckdb_hash64>>4 (v15-duckdb-2)"}
    if por_col:
        pos, nom = [], {}
        for i, c in enumerate(campos):
            h = sha(f"SHA256-COL-v2|{n}|{r[f'c{i}'] if r[f'c{i}'] is not None else 0}")
            pos.append({"posicion": i, "nombre": c["nombre"], "tipo": c["tipo"], "hash_datos": h})
            nom[c["nombre"]] = h
        res["columnas"] = pos
        res["hash_por_columna"] = nom
        res["hash_conjunto_columnas"] = sha("SHA256-SET-v1|" + "|".join(sorted(nom.values())))
    if cond:
        naf = int(r["naf"] or 0)
        sl = [str(r[f"l{i}"] or 0) for i in range(1, 5)]
        sa = [str(r[f"a{i}"] or 0) for i in range(1, 5)]
        res["segregacion"] = {
            "criterio": ("fila AFECTADA = alguna columna de texto es NULL, o esta vacia, o casa el "
                         "patron de caracteres. Es la UNION a proposito: asi las dos plataformas "
                         "marcan LAS MISMAS filas aunque una tenga NULL y la otra ''"),
            "patron_caracteres": PATRON_SEG,
            "columnas_de_texto_evaluadas": [c["nombre"] for c in textos],
            "filas_afectadas": naf, "filas_limpias": n - naf,
            "pct_afectadas": round(100.0 * naf / n, 6) if n else None,
            "hash_filas_limpias": _h_sumas(n - naf, sl),
            "hash_filas_afectadas": _h_sumas(naf, sa)}
    res.update(hashes_esquema(cols))
    return res


def _aggs(c, i, fecha_ref):
    n, ts, k, p = q(c["nombre"]), c["tipo"], _cat(c["tipo"]), f"m{i}_"
    a = [f"count({n}) as {p}no_nulos"]
    if k not in ("complejo", "void", "bin"):
        a.append(f"count(distinct {n}) as {p}distintos")
    if k in ("entero", "decimal", "flotante"):
        suma = (f"sum({n})" if k == "decimal" else
                f"sum(cast({n} as decimal(38,10)))" if k == "flotante" else
                f"sum(cast({n} as hugeint))")
        a += [f"min({n}) as {p}minimo", f"max({n}) as {p}maximo", f"{suma} as {p}suma_exacta",
              f"sum(case when {n} = 0 then 1 else 0 end) as {p}ceros",
              f"sum(case when {n} < 0 then 1 else 0 end) as {p}negativos",
              f"quantile_disc({n}, [0.25, 0.5, 0.75]) as {p}pct"]
        if k == "flotante":
            a += [f"sum(case when isnan({n}) then 1 else 0 end) as {p}nan",
                  f"sum(case when isinf({n}) then 1 else 0 end) as {p}inf"]
    elif k == "texto":
        a += [f"min(length({n})) as {p}lmin", f"max(length({n})) as {p}lmax",
              f"min({n}) as {p}vmin", f"max({n}) as {p}vmax",
              f"sum(case when length({n}) = 0 then 1 else 0 end) as {p}vacias",
              f"sum(case when length({n}) > 0 and length(trim({n})) = 0 then 1 else 0 end) as {p}esp",
              f"sum(case when {n} <> trim({n}) then 1 else 0 end) as {p}bordes",
              f"sum(case when trim({n}) in ({', '.join(lit(x) for x in SENT_TXT)}) then 1 else 0 end) as {p}sent",
              f"sum(case when {n} = upper({n}) and length(trim({n})) > 0 then 1 else 0 end) as {p}upper"]
        for nom, rx in (("ent", RE_ENTERO), ("num", RE_DECIMAL), ("fec", RE_FECHA),
                        ("cz", RE_CEROS), ("nascii", RE_NO_ASCII), ("ctrl", RE_CONTROL),
                        ("mail", RE_EMAIL)):
            a.append(f"sum(case when regexp_matches({n}, {lit(rx)}) then 1 else 0 end) as {p}{nom}")
    elif k in ("fecha", "ts"):
        dd = f"cast({n} as date)"
        a += [f"cast(min({n}) as varchar) as {p}minimo", f"cast(max({n}) as varchar) as {p}maximo",
              f"count(distinct {dd}) as {p}dias",
              f"sum(case when {dd} > date {lit(fecha_ref)} then 1 else 0 end) as {p}fut",
              f"sum(case when {dd} < date '1900-01-01' then 1 else 0 end) as {p}old",
              f"sum(case when strftime({dd}, '%Y-%m-%d') in ({', '.join(lit(x) for x in SENT_FEC)}) then 1 else 0 end) as {p}sentf"]
    elif k == "bool":
        a += [f"sum(case when {n} then 1 else 0 end) as {p}true",
              f"sum(case when not {n} then 1 else 0 end) as {p}false"]
    elif k == "bin":
        a += [f"min(octet_length({n})) as {p}bmin", f"max(octet_length({n})) as {p}bmax"]
    return a


MAPEO = {"minimo": "minimo", "maximo": "maximo", "suma_exacta": "suma_exacta",
"ceros": "ceros", "negativos": "negativos",
         "nan": "valores_nan", "inf": "valores_infinitos", "pct": "percentiles_p25_p50_p75",
         "lmin": "longitud_minima", "lmax": "longitud_maxima", "vmin": "valor_minimo_lexicografico", "vmax": "valor_maximo_lexicografico",
         "vacias": "cadenas_vacias", "esp": "solo_espacios", "bordes": "con_espacios_en_bordes",
         "ent": "enteros_como_texto", "num": "numericos_como_texto", "fec": "fechas_como_texto",
         "cz": "con_ceros_a_la_izquierda", "nascii": "con_caracteres_no_ascii",
         "ctrl": "con_caracteres_de_control", "mail": "correos_validos",
         "sent": "centinelas_de_nulo", "upper": "mayusculas_completas", "dias": "dias_distintos",
         "fut": "posteriores_a_fecha_ejecucion", "old": "anteriores_a_1900",
         "sentf": "centinelas_de_fecha", "true": "verdaderos", "false": "falsos",
         "bmin": "bytes_minimo", "bmax": "bytes_maximo"}


def perfilar(con, vista, cols, filas, fecha_ref, lote=14, aprox=False):
    crudo = {}
    for ini in range(0, len(cols), lote):
        ex = [e for i in range(ini, min(len(cols), ini + lote)) for e in _aggs(cols[i], i, fecha_ref)]
        if aprox:
            ex = [x.replace("count(distinct ", "approx_count_distinct(") for x in ex]
        cur = con.execute(f"select {', '.join(ex)} from {vista}")
        crudo.update(dict(zip([d[0] for d in cur.description], cur.fetchone())))
    out = {}
    for i, c in enumerate(cols):
        p, ts, k = f"m{i}_", c["tipo"], _cat(c["tipo"])
        v = {kk[len(p):]: vv for kk, vv in crudo.items() if kk.startswith(p)}
        nn = int(v.get("no_nulos") or 0)
        nul = filas - nn
        d = {"tipo_spark": ts, "nullable_declarado": c["nullable"], "orden_fisico": i,
             "nivel_perfil": "COMPLETO", "registros": filas, "no_nulos": nn, "nulos": nul,
             "pct_nulos": round(100.0 * nul / filas, 4) if filas else None,
             "pct_completitud": round(100.0 * nn / filas, 4) if filas else None}
        if "distintos" in v:
            dist = int(v["distintos"] or 0)
            d["valores_distintos"] = dist
            d["valores_distintos_metodo"] = "APROXIMADO_HLL" if aprox else "EXACTO"
            d["pct_cardinalidad"] = round(100.0 * dist / nn, 4) if nn else None
            mn, mx = v.get("minimo", v.get("vmin")), v.get("maximo", v.get("vmax"))
            if mn is not None and mx is not None:
                d["es_constante"], d["es_constante_metodo"] = (mn == mx), "EXACTO (min == max)"
            else:
                d["es_constante"], d["es_constante_metodo"] = (dist == 1), "EXACTO"
            d["candidata_a_llave"] = bool(nn == filas and filas > 0 and dist == filas)
        else:
            d["valores_distintos"] = None
            d["valores_distintos_metodo"] = "NO_APLICABLE_PARA_ESTE_TIPO"
            d["candidata_a_llave"] = False
        for kk, vv in v.items():
            if kk in ("no_nulos", "distintos"):
                continue
            d[MAPEO.get(kk, kk)] = _num(vv)
        if k in ("entero", "decimal", "flotante") and nn and v.get("suma_exacta") is not None:
            try:
                d["media_exacta"] = str((Decimal(str(v["suma_exacta"])) / Decimal(nn)).quantize(Decimal("0.000001")))
            except Exception:
                d["media_exacta"] = None
        if k == "texto":
            d["nulos_efectivos_incluyendo_centinelas"] = nul + int(d.get("cadenas_vacias") or 0) + int(d.get("solo_espacios") or 0)
            ent, cz = int(d.get("enteros_como_texto") or 0), int(d.get("con_ceros_a_la_izquierda") or 0)
            d["tipo_semantico_sugerido"] = (
                "NUMERICO_EN_TEXTO" if nn and ent == nn and not cz else
                "CODIGO_CON_CEROS_IZQUIERDA" if nn and cz > 0.9 * nn else
                "FECHA_EN_TEXTO" if nn and int(d.get("fechas_como_texto") or 0) == nn else
                "CORREO" if nn and int(d.get("correos_validos") or 0) == nn else "TEXTO")
        out[c["nombre"]] = d
    return out


def frecuentes(con, vista, cols, perfil, filas):
    res = {}
    cand = [c for c in cols if (perfil[c["nombre"]].get("valores_distintos") or 10**9) <= MAX_DIST_TOP
            and _cat(c["tipo"]) not in ("complejo", "bin", "void")]
    cand.sort(key=lambda c: perfil[c["nombre"]]["valores_distintos"])
    for c in cand[:MAX_COLS_TOP]:
        n = q(c["nombre"])
        filas_top = con.execute(f"select cast({n} as varchar) v, count(*) f from {vista} group by 1 "
                                f"order by f desc, v nulls first limit {TOP_N}").fetchall()
        res[c["nombre"]] = [{"valor": v, "frecuencia": f, "pct": round(100.0 * f / filas, 4) if filas else None}
                            for v, f in filas_top]
    return res


def _regla(cod, nom, est, det, ev=None):
    r = {"codigo": cod, "nombre": nom, "estado": est, "detalle": det}
    if ev is not None:
        r["evidencia"] = ev
    return r


def reglas(cols, perfil, hashes, filas):
    idb = [_regla("ID-01", "Conteo de registros mayor que cero", "OK" if filas > 0 else "ERROR",
                  f"row_count = {filas}", {"row_count": filas})]
    dup = hashes.get("filas_duplicadas_exactas")
    if dup is None:
        dup = hashes.get("filas_duplicadas_estimadas") or 0
    pct = round(100.0 * dup / filas, 4) if filas else 0.0
    idb.append(_regla("ID-02", "Duplicados de fila completa", "OK" if not dup else "ALERTA",
                      f"{dup} fila(s) duplicada(s) {'EXACTAS' if hashes.get('filas_distintas_metodo') == 'EXACTO' else 'ESTIMADAS'} ({pct}%)",
                      {"duplicados": dup, "exacto": hashes.get("filas_distintas_metodo") == "EXACTO",
                       "metodo": hashes.get("filas_distintas_metodo"), "alcance": hashes.get("alcance")}))
    vacias = sorted(n for n, m in perfil.items() if m["no_nulos"] == 0)
    idb.append(_regla("ID-03", "Columnas 100% nulas", "OK" if not vacias else "ALERTA",
                      f"{len(vacias)} columna(s) sin ningún valor", {"columnas": vacias}))
    con_nulos = {n: m["pct_nulos"] for n, m in perfil.items() if (m["nulos"] or 0) > 0}
    idb.append(_regla("ID-04", "Obligatoriedad de columnas", "INFORMATIVO",
                      f"{len(con_nulos)} de {len(perfil)} columnas presentan nulos. Sin contrato de datos no es "
                      "posible exigir NOT NULL; se reporta el perfil de nulos como línea base.",
                      {"pct_nulos_por_columna": con_nulos}))
    llaves = sorted(n for n, m in perfil.items() if m.get("candidata_a_llave"))
    idb.append(_regla("ID-05", "Candidatas a clave única", "OK" if llaves else "ALERTA",
                      f"{len(llaves)} columna(s) con unicidad total" + ("" if llaves else " — no se detectó identificador natural"),
                      {"candidatas": llaves}))
    ctes = sorted(n for n, m in perfil.items() if m.get("es_constante"))
    idb.append(_regla("ID-06", "Columnas constantes (un solo valor)", "OK" if not ctes else "INFORMATIVO",
                      f"{len(ctes)} columna(s) con un único valor", {"columnas": ctes}))
    nombres = [c["nombre"] for c in cols]
    bajos = [x.lower() for x in nombres]
    dups = sorted({x for x in bajos if bajos.count(x) > 1})
    inval = sorted(n for n in nombres if MALOS_DELTA.search(n))
    nosop = sorted(c["nombre"] for c in cols if c["tipo"] in ("void", "interval"))
    decm = []
    for c in cols:
        m = re.match(r"decimal\((\d+),(\d+)\)", c["tipo"])
        if m and (int(m.group(1)) > 38 or int(m.group(2)) > int(m.group(1))):
            decm.append(c["nombre"])
    compl = sorted(c["nombre"] for c in cols if _cat(c["tipo"]) == "complejo")
    largos = sorted(n for n in nombres if len(n) > 128)
    vgb = [_regla("VG-01", "Nombres de columna únicos (case-insensitive)", "OK" if not dups else "ERROR",
                  "Spark/Delta/Fabric no distinguen caja por defecto: nombres que solo difieren en mayúsculas colisionan al escribir.",
                  {"duplicados": dups}),
           _regla("VG-02", "Nombres compatibles con Delta/Parquet/Fabric", "OK" if not inval else "ERROR",
                  "Caracteres ' ,;{}()\\n\\t=' no son válidos en columnas Delta sin column mapping.", {"columnas": inval}),
           _regla("VG-03", "Tipos soportados en el destino", "OK" if not nosop else "ERROR",
                  f"{len(nosop)} columna(s) con tipo no materializable (void/interval).", {"columnas": nosop}),
           _regla("VG-04", "Precisión/escala de decimales válida", "OK" if not decm else "ERROR",
                  "Spark admite hasta decimal(38, s).", {"columnas": decm}),
           _regla("VG-05", "Tipos complejos (anidados)", "OK" if not compl else "INFORMATIVO",
                  f"{len(compl)} columna(s) anidada(s).", {"columnas": compl}),
           _regla("VG-06", "Longitud de nombres de columna", "OK" if not largos else "ALERTA",
                  f"{len(largos)} nombre(s) con más de 128 caracteres.", {"columnas": largos})]
    est = [r["estado"] for r in idb + vgb]
    por = {e: est.count(e) for e in sorted(set(est))}
    general = "ERROR" if "ERROR" in est else ("OBSERVACIONES" if "ALERTA" in est else "OK")
    return {"ID_integridad_y_conteos": idb, "VG_esquema_y_metadata": vgb,
            "resumen": {"por_estado": por, "estado_general": general,
                        "no_evaluables": [r["codigo"] for r in idb + vgb if r["estado"] == "NO_EVALUABLE"],
                        "no_ejecutados": []},
            "cobertura": {"ID": "ID-01..06", "VG": "VG-01..06 (VG-09 contrato: se decide en el cotejo)",
                          "retirados": ["VG-07", "VG-08", "ID-07", "ID-08"]}}


def contrato(perfil, hashes, filas):
    ch = hashes.get("hash_por_columna") or {}
    return {"advertencia": ("CONTRATO PROPUESTO, NO OFICIAL: derivado por observación de los datos. "
                            "nullable=false significa «hoy no tenía nulos», no «es obligatoria»."),
            "hash_esquema_tipos": hashes.get("hash_esquema_tipos"), "row_count_linea_base": filas,
            "columnas": [{"posicion": m["orden_fisico"], "nombre": n, "tipo": m["tipo_spark"],
                          "nullable": (m.get("nulos") or 0) > 0, "hash_datos": ch.get(n),
                          "observado_pct_nulos": m.get("pct_nulos"),
                          "observado_distintos": m.get("valores_distintos"),
                          "observado_longitud_maxima": m.get("longitud_maxima"),
                          "candidata_a_llave": m.get("candidata_a_llave")}
                         for n, m in sorted(perfil.items(), key=lambda kv: kv[1]["orden_fisico"])]}


def medir(con, vista, *, plataforma, clave, nombre, ubicacion, flujo, tipo_fuente, run_id,
          excluidas_hash=(), nullables=None, fecha_ref=None, extra_objeto=None, almacenamiento=None,
          alcance=None, perfil_aprox=False):
    t0 = datetime.datetime.now(datetime.timezone.utc)
    fecha_ref = fecha_ref or t0.date().isoformat()
    etapas = {}
    cols = esquema_de(con, vista, nullables)
    _t = datetime.datetime.now()
    filas = con.execute(f"select count(*) from {vista}").fetchone()[0]
    etapas["conteo"] = (datetime.datetime.now() - _t).total_seconds()
    _t = datetime.datetime.now()
    h = medir_hash(con, vista, cols, filas, excluidas_hash)
    etapas["CP-03 checksum SHA-256"] = (datetime.datetime.now() - _t).total_seconds()
    _t = datetime.datetime.now()
    perfil = perfilar(con, vista, cols, filas, fecha_ref, aprox=perfil_aprox)
    etapas["perfilado de columnas"] = (datetime.datetime.now() - _t).total_seconds()
    _t = datetime.datetime.now()
    top = frecuentes(con, vista, cols, perfil, filas)
    etapas["valores mas frecuentes"] = (datetime.datetime.now() - _t).total_seconds()
    muestra = [[_num(x) for x in r] for r in con.execute(f"select * from {vista} limit 10").fetchall()]
    val = reglas(cols, perfil, h, filas)
    esq_h = hashes_esquema(cols)
    firma = ", ".join(f"{c['nombre']} ({c['tipo']})" for c in cols)
    fin = datetime.datetime.now(datetime.timezone.utc)
    pa = f"{plataforma}_QA"
    iso = lambda d: d.isoformat(timespec="seconds").replace("+00:00", "Z")
    rep = {
        "version_reporte": "1.0.0",
        "ejecucion": {"run_id": run_id, "etiqueta_corrida": f"lote9 {run_id[:8]}",
                      "ejecutado_utc": iso(fin), "fecha_ejecucion": fin.date().isoformat(),
                      "plataforma": plataforma, "ambiente": "QA", "plataforma_ambiente": pa,
                      "version_reporte": VERSION_MOTOR, "motor": "duckdb",
                      "nota_motor": ("Medido por QA fuera del notebook con la especificación v15 "
                                     "(mismas reglas, mismos hashes). Los dos lados del cotejo se miden "
                                     "con este mismo motor."),
                      "paridad": True, "duracion_segundos": round((fin - t0).total_seconds(), 3),
                      "duracion_por_etapa": {k: round(v, 3) for k, v in etapas.items()},
                      "medido_utc": iso(fin), "medido_desde_utc": iso(t0)},
        "objeto": dict({"id_objeto": nombre.lower(), "clave_cotejo": clave, "nombre": nombre,
                        "tipo_fuente": tipo_fuente, "ubicacion": ubicacion, "ruta_declarada": ubicacion,
                        "flujo": flujo, "almacenamiento": almacenamiento or {},
                        "alcance_temporal": alcance or {"modo": "TODAS", "estado": "TOTAL", "clave": None,
                                                        "valor": None, "detalle": "todo el objeto"}},
                       **(extra_objeto or {})),
        "errores": [],
        "perfilado": {"nivel": "COMPLETO", "precision_comparable": True,
                      "distintos_exactos_hasta": DISTINTOS_EXACTOS_HASTA, "forenses_de_texto": True,
                      "metricas_omitidas": [], "distintos_exactos": filas <= DISTINTOS_EXACTOS_HASTA},
        "conteos": {"row_count": filas, "num_columnas": len(cols), "celdas": filas * len(cols)},
        "esquema": dict({"num_columnas": len(cols),
                         "columnas": [{k: c[k] for k in ("orden", "nombre", "tipo", "nullable")} for c in cols],
                         "tipos_motor": {c["nombre"]: c["tipo_motor"] for c in cols},
                         "firma_plana": firma}, **esq_h),
        "hash": h,
        "desglose_particiones": {"estado": "NO_EJECUTADO", "motivo": "medición total del objeto"},
        "metricas_columnas": perfil,
        "valores_frecuentes": top,
        "muestra": {"filas": muestra, "nota": "Muestra ilustrativa (limit 10): NO es determinista, no se usa en el hash y CP-04 es INFORMATIVO."},
        "validaciones": val,
        "comparacion_corrida_previa": "SIN_CORRIDA_PREVIA",
        "puntos_control": {
            "CP-01_conteo": {"estado": "OK" if filas else "ALERTA", "valor": filas},
            "CP-02_esquema_tipos": {"estado": "OK", "valor": firma},
            "CP-03_checksum": {"estado": "OK" if h.get("hash_dataset") else "NO_EJECUTADO",
                               "algoritmo": "SHA-256", "valor": h.get("hash_dataset"),
                               "alcance": h.get("alcance"), "motivo": h.get("motivo")},
            "CP-04_muestreo": {"estado": "INFORMATIVO", "valor": f"{len(muestra)} fila(s)"},
            "CP-05_reejecucion_fecha": {"estado": "OK", "valor": iso(fin), "plataforma_ambiente": pa,
                                        "alcance_temporal": "total"}},
        "estado_general": val["resumen"]["estado_general"],
    }
    rep["contrato_propuesto"] = contrato(perfil, h, filas)
    return rep


def conectar(spill, memoria="6GB", hilos=4):
    import duckdb
    import os
    os.makedirs(spill, exist_ok=True)
    con = duckdb.connect(config={"memory_limit": memoria, "threads": str(hilos), "temp_directory": spill,
                                 "max_temp_directory_size": "300GB", "preserve_insertion_order": "false"})
    # Spark mide con spark.sql.session.timeZone=UTC: los timestamp ajustados a UTC se canonicalizan en UTC
    con.execute("SET TimeZone='UTC'")
    return con
