"""Diferencias exactas por llave entre S (Stratio, la referencia) y F (Fabric), sobre la cache del nivel 2.

  python -m pc diferenciar --trabajo T --clave K [--llave a,b] [--columna-fecha C]

Lo que entrega (todo contado, nada estimado):
  llave        la declarada en lote.json; si no hay, una columna sin nulos y unica en los dos lados; si no, una
               compuesta de 2 o 3 columnas (se buscan candidatas y se COMPRUEBAN exactas); si no hay, sin llave.
  filas        solo en S, solo en F, comunes por llave, comunes con alguna columna distinta.
  por columna  filas exactas con valor distinto y su PATRON (cada fila cae en el primero que cumple):
               nulo_vs_vacio · espacios · mayusculas · acentos_unicode · mojibake · ceros_izquierda ·
               mismo_numero_otra_escala · diferencia_numerica (con max |S-F|) · desplazamiento_horario (offsets) ·
               truncamiento_fecha_hora · mismo_instante_otro_formato · otro
               El patron DESCRIBE la diferencia; no cambia umbrales ni decide. La causa la mide el cotejador y la
               decide una persona.
  localizacion por mes de una columna de fecha: donde estan las filas solo S, solo F y cambiadas.
  ejemplos     deterministas (ordenados por llave), hasta 5 por hallazgo, con el valor de cada lado.
  detalle      trabajos/<T>/diferencias/<K>/{solo_stratio,solo_fabric,cambiadas}.parquet (local, completo)
Sin llave: solo las filas completas que estan en un lado y no en el otro (EXCEPT ALL, multiconjunto exacto).
"""
import datetime
import json
import os
import re

from ..medir import motor_v15 as M

PATRONES = ("nulo_vs_vacio", "nulo_en_fabric", "nulo_en_stratio", "espacios", "mayusculas", "acentos_unicode", "mojibake", "ceros_izquierda",
            "mismo_numero_otra_escala", "diferencia_numerica", "desplazamiento_horario", "truncamiento_fecha_hora",
            "misma_fecha_otra_hora", "mismo_instante_otro_formato", "otro")
NULO = "chr(0) || 'NULL' || chr(0)"
_MARCADORES = ("''", "'null'", "'NULL'", "'None'", "'nan'", "'NaN'", "'N/A'", "'n/a'", "'-'")
_MOJI = (("Ã¡", "á"), ("Ã©", "é"), ("Ã­", "í"), ("Ã³", "ó"), ("Ãº", "ú"), ("Ã±", "ñ"), ("Ã‘", "Ñ"), ("Ã\u0081", "Á"),
         ("Ã‰", "É"), ("Ã\u008d", "Í"), ("Ã“", "Ó"), ("Ãš", "Ú"), ("Ã¼", "ü"), ("Â°", "°"), ("Â", ""))
_NOMBRE_LLAVE = re.compile(r"(^|_)(id|codigo|cod|key|llave|numero|num|nro|documento|identificacion|partner|bp)(_|$)", re.I)


def _m(n):
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else str(n)


def _lit(s):
    return "'" + str(s).replace("'", "''") + "'"


def describir(con, vista):
    return [(r[0], r[1]) for r in con.execute(f"describe select * from {vista}").fetchall()]


def comunes(con):
    s, f = describir(con, "S"), dict(describir(con, "F"))
    return [(c, t, f[c]) for c, t in s if c in f]


def _n(con, v):
    return con.execute(f"select count(*) from {v}").fetchone()[0]


def _unica(con, cols, n_s, n_f):
    """Exacta: la combinacion no tiene nulos y no se repite en ninguno de los dos lados."""
    tup = ", ".join(M.q(c) for c in cols)
    nn = " and ".join(f"{M.q(c)} is not null" for c in cols)
    for v, n in (("S", n_s), ("F", n_f)):
        r = con.execute(f"select count(*) filter (where {nn}), count(distinct ({tup})) filter (where {nn}) from {v}").fetchone()
        if r[0] != n or r[1] != n:
            return False
    return True


def resolver_llave(con, declarada=None, max_columnas=3):
    """(llave, origen, notas). Primero la declarada; despues una sola columna; despues compuesta (2-3)."""
    n_s, n_f = _n(con, "S"), _n(con, "F")
    todas = comunes(con)
    cols = [c for c, _ts, _tf in todas]
    # una llave no es un numero con decimales ni una marca de tiempo (coinciden por azar o cambian de precision)
    llaveables = {c for c, ts, tf in todas if not any(x in (ts + tf).upper() for x in ("DOUBLE", "FLOAT", "DECIMAL", "REAL", "TIMESTAMP"))}
    notas = []
    if declarada:
        faltan = [c for c in declarada if c not in cols]
        if faltan:
            notas.append(f"llave declarada {declarada}: faltan {faltan} en algún lado")
        elif _unica(con, declarada, n_s, n_f):
            return list(declarada), "declarada", notas
        else:
            notas.append(f"llave declarada {declarada}: tiene nulos o repetidos en algún lado; se busca otra")
    if not cols or not n_s or not n_f:
        return None, "sin_llave", notas + ["una de las tablas está vacía"]
    # perfil barato y exacto por columna: nulos y distintos de cada lado
    sel = ", ".join(f"count({M.q(c)}), count(distinct {M.q(c)})" for c in cols)
    ps, pf = con.execute(f"select {sel} from S").fetchone(), con.execute(f"select {sel} from F").fetchone()
    perfil = {c: (ps[2 * i], ps[2 * i + 1], pf[2 * i], pf[2 * i + 1]) for i, c in enumerate(cols)}
    sin_nulos = [c for c in cols if perfil[c][0] == n_s and perfil[c][2] == n_f and c in llaveables]
    unicas = [c for c in sin_nulos if perfil[c][1] == n_s and perfil[c][3] == n_f]
    def cobertura(comb):
        on = " and ".join(f"S.{M.q(c)} = F.{M.q(c)}" for c in comb)
        return con.execute(f"select count(*) from S join F on {on}").fetchone()[0]

    # una columna unica en cada lado no es por eso la llave ENTRE los lados: se elige la que mas filas cruza
    # (conteo exacto del join); a igual cobertura, menos columnas y nombre de llave
    cands = [[c] for c in sorted(unicas, key=lambda c: (not _NOMBRE_LLAVE.search(c), cols.index(c)))[:6]]
    tope = min(n_s, n_f)
    mejor = max(((cobertura(c), c) for c in cands), key=lambda x: (x[0], bool(_NOMBRE_LLAVE.search(x[1][0]))), default=(0, None))
    if mejor[1] and mejor[0] == tope:
        return mejor[1], "una_columna", notas
    from itertools import combinations
    cand = sorted(sin_nulos, key=lambda c: (-(min(perfil[c][1] / n_s, perfil[c][3] / n_f)), not _NOMBRE_LLAVE.search(c)))[:10]
    probadas = 0
    for k in range(2, max_columnas + 1):
        for comb in combinations(cand, k):
            # cota exacta y barata: el producto de distintos tiene que alcanzar las filas
            ps_ = 1
            for c in comb:
                ps_ *= min(perfil[c][1], perfil[c][3])
            if ps_ < max(n_s, n_f) or probadas >= 20:
                continue
            if _unica(con, list(comb), n_s, n_f):
                probadas += 1
                cv = cobertura(comb)
                nombre = sum(bool(_NOMBRE_LLAVE.search(c)) for c in comb) / len(comb)
                nombre_mejor = sum(bool(_NOMBRE_LLAVE.search(c)) for c in mejor[1]) / len(mejor[1]) if mejor[1] else -1
                if cv > mejor[0] or (cv == mejor[0] and (nombre, -len(comb)) > (nombre_mejor, -len(mejor[1] or []))):
                    mejor = (cv, list(comb))
                if cv == tope:
                    break
        if mejor[0] == tope:
            break
    # casi unica: la columna sin nulos que mas llaves cruza; las filas con llave repetida se cuentan aparte.
    # Gana sobre una llave estricta que cruza menos.
    casi = [c for c in sin_nulos if perfil[c][1] >= 0.95 * n_s and perfil[c][3] >= 0.95 * n_f and [c] != mejor[1]]
    cv_casi, c_casi = 0, None
    if casi:
        def cob_distinta(c):
            return con.execute(f"select count(*) from (select distinct {M.q(c)} k from S) s join (select distinct {M.q(c)} k from F) f "
                               f"on s.k = f.k").fetchone()[0]
        cv_casi, c_casi = max(((cob_distinta(c), c) for c in sorted(casi, key=lambda c: not _NOMBRE_LLAVE.search(c))[:6]),
                              key=lambda x: x[0])
    if mejor[1] and mejor[0] >= cv_casi:
        notas.append(f"la llave cruza {mejor[0]:,} de {tope:,} filas posibles".replace(",", "."))
        return mejor[1], ("una_columna" if len(mejor[1]) == 1 else f"compuesta_{len(mejor[1])}"), notas
    if c_casi and cv_casi:
        c = c_casi
        notas.append(f"{c}: casi única (Stratio {_m(perfil[c][1])} distintos en {_m(n_s)} filas; Fabric {_m(perfil[c][3])} en {_m(n_f)}); "
                     f"cruza {_m(cv_casi)} llaves; las filas con llave repetida se cuentan aparte")
        return [c], "casi_unica", notas
    if False:
        def cob_distinta(c):
            return con.execute(f"select count(*) from (select distinct {M.q(c)} k from S) s join (select distinct {M.q(c)} k from F) f "
                               f"on s.k = f.k").fetchone()[0]
        cv, c = max(((cob_distinta(c), c) for c in sorted(casi, key=lambda c: not _NOMBRE_LLAVE.search(c))[:6]),
                    key=lambda x: x[0])
        if cv:
            notas.append(f"{c}: casi única (Stratio {perfil[c][1]:,} distintos en {n_s:,} filas, Fabric {perfil[c][3]:,} en {n_f:,}); "
                         f"las filas con llave repetida se cuentan aparte".replace(",", "."))
            return [c], "casi_unica", notas
    return None, "sin_llave", notas + [f"ninguna combinación de hasta {max_columnas} columnas es única en los dos lados"]


def _texto(c, t):
    """Forma canonica de motor_v15 (la misma del SHA-256) con el nulo marcado. `t` es el tipo de DuckDB."""
    return M.canonica(c, M.tipo_spark(t))


def _patron_sql(s, f):
    """CASE con el primer patron que cumple; s y f son las formas canonicas (texto, nulo = marcador)."""
    ss, ff = f"nullif({s}, {NULO})", f"nullif({f}, {NULO})"
    marc = ", ".join(_MARCADORES)
    moji_f, moji_s = ff, ss
    for a, b in _MOJI:
        moji_f = f"replace({moji_f}, {_lit(a)}, {_lit(b)})"
        moji_s = f"replace({moji_s}, {_lit(a)}, {_lit(b)})"
    ts_s, ts_f = f"try_cast({ss} as timestamp)", f"try_cast({ff} as timestamp)"
    num_s, num_f = f"try_cast({ss} as decimal(38,10))", f"try_cast({ff} as decimal(38,10))"
    fmt = lambda x: (f"coalesce(try_cast({x} as timestamp), try_strptime({x}, '%d/%m/%Y'), try_strptime({x}, '%d/%m/%Y %H:%M:%S'), "
                     f"try_strptime({x}, '%Y%m%d'), try_strptime({x}, '%m/%d/%Y'))")
    return f"""case
      when ({ss} is null and coalesce({ff}, '') in ({marc})) or ({ff} is null and coalesce({ss}, '') in ({marc})) then 'nulo_vs_vacio'
      when {ff} is null then 'nulo_en_fabric'
      when {ss} is null then 'nulo_en_stratio'
      when trim({ss}) = trim({ff}) then 'espacios'
      when lower(trim({ss})) = lower(trim({ff})) then 'mayusculas'
      when strip_accents(lower(nfc_normalize({ss}))) = strip_accents(lower(nfc_normalize({ff}))) then 'acentos_unicode'
      when {moji_s} = {moji_f} and ({ss} like '%Ã%' or {ff} like '%Ã%' or {ss} like '%Â%' or {ff} like '%Â%') then 'mojibake'
      when ltrim({ss}, '0') = ltrim({ff}, '0') then 'ceros_izquierda'
      when {num_s} is not null and {num_f} is not null and {num_s} = {num_f} then 'mismo_numero_otra_escala'
      when {num_s} is not null and {num_f} is not null then 'diferencia_numerica'
      when {ts_s} is not null and {ts_f} is not null and date_diff('second', {ts_s}, {ts_f}) % 1800 = 0
           then 'desplazamiento_horario'
      when {ts_s} is not null and {ts_f} is not null and (date_trunc('second', {ts_s}) = date_trunc('second', {ts_f})
           or (cast({ts_s} as date) = cast({ts_f} as date) and (cast({ts_s} as time) = time '00:00:00' or cast({ts_f} as time) = time '00:00:00')))
           then 'truncamiento_fecha_hora'
      when {ts_s} is not null and {ts_f} is not null and cast({ts_s} as date) = cast({ts_f} as date) then 'misma_fecha_otra_hora'
      when {fmt(ss)} is not null and {fmt(ss)} = {fmt(ff)} then 'mismo_instante_otro_formato'
      else 'otro' end"""


def _fecha(cols, preferida=None):
    if preferida and preferida in [c for c, _a, _b in cols]:
        return preferida
    for c, ts, tf in cols:
        if any(x in (ts + tf).upper() for x in ("DATE", "TIMESTAMP")):
            return c
    return None


def diferenciar(con, llave=None, origen=None, columna_fecha=None, ejemplos=5, destino=None):
    cols = comunes(con)
    n_s, n_f = _n(con, "S"), _n(con, "F")
    solo_cols = {"solo_en_stratio": [c for c, _ in describir(con, "S") if c not in {x[0] for x in cols}],
                 "solo_en_fabric": [c for c, _ in describir(con, "F") if c not in {x[0] for x in cols}]}
    out = {"generado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "filas": {"stratio": n_s, "fabric": n_f}, "columnas_comunes": len(cols), "columnas_no_comunes": solo_cols,
           "llave": llave, "llave_origen": origen}
    if destino:
        os.makedirs(destino, exist_ok=True)
    if not llave:
        lista = ", ".join(M.q(c) for c, _a, _b in cols)
        for a, b, nom in (("S", "F", "solo_stratio"), ("F", "S", "solo_fabric")):
            sql = f"select {lista} from {a} except all select {lista} from {b}"
            out["filas"][nom] = con.execute(f"select count(*) from ({sql})").fetchone()[0]
            cur = con.execute(f"{sql} order by all limit {ejemplos}")
            out[f"ejemplos_{nom}"] = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
            if destino:
                con.execute(f"copy ({sql}) to {_lit(os.path.join(destino, nom + '.parquet'))} (format parquet)")
        out["aviso"] = "sin llave: una fila con una sola columna distinta cuenta como solo en S y solo en F"
        return out
    kq = [M.q(c) for c in llave]
    resto = [(c, ts, tf) for c, ts, tf in cols if c not in llave]
    fcol = _fecha(cols, columna_fecha)
    sel_s = ", ".join([f"{M.q(c)} as k{i}" for i, c in enumerate(llave)] + [f"{_texto(c, ts)} as s{i}" for i, (c, ts, _t) in enumerate(resto)]
                      + ([f"cast({M.q(fcol)} as date) as fecha_s"] if fcol else []))
    sel_f = ", ".join([f"{M.q(c)} as k{i}" for i, c in enumerate(llave)] + [f"{_texto(c, tf)} as f{i}" for i, (c, _ts, tf) in enumerate(resto)]
                      + ([f"cast({M.q(fcol)} as date) as fecha_f"] if fcol else []))
    con.execute(f"create or replace temp table _s as select {sel_s} from S")
    con.execute(f"create or replace temp table _f as select {sel_f} from F")
    kl = ", ".join(f"k{i}" for i in range(len(llave)))
    rep = con.execute(f"""create or replace temp table _rep as
        select {kl} from _s group by all having count(*) > 1 union select {kl} from _f group by all having count(*) > 1""")
    n_rep = _n(con, "_rep")
    if n_rep:     # llave repetida en algun lado: esas filas no se emparejan una a una; se cuentan aparte
        usa = " and ".join(f"x.k{i} = r.k{i}" for i in range(len(llave)))
        out["filas"]["llave_repetida"] = {
            "llaves": n_rep,
            "stratio": con.execute(f"select count(*) from _s x semi join _rep r on {usa}").fetchone()[0],
            "fabric": con.execute(f"select count(*) from _f x semi join _rep r on {usa}").fetchone()[0]}
        if destino:
            for t_, nom in (("_s", "llave_repetida_stratio"), ("_f", "llave_repetida_fabric")):
                con.execute(f"copy (select x.* from {t_} x semi join _rep r on {usa}) to {_lit(os.path.join(destino, nom + '.parquet'))} (format parquet)")
        for t_ in ("_s", "_f"):
            con.execute(f"delete from {t_} x where exists (select 1 from _rep r where {usa})")
    on = " and ".join(f"_s.k{i} = _f.k{i}" for i in range(len(llave)))
    con.execute(f"create or replace temp table _j as select * from _s join _f using ({', '.join(f'k{i}' for i in range(len(llave)))})")
    out["filas"]["solo_stratio"] = con.execute(f"select count(*) from _s anti join _f on {on}").fetchone()[0]
    out["filas"]["solo_fabric"] = con.execute(f"select count(*) from _f anti join _s on {on}").fetchone()[0]
    out["filas"]["comunes"] = _n(con, "_j")
    distinto = [f"s{i} is distinct from f{i}" for i in range(len(resto))]
    out["filas"]["comunes_con_alguna_diferencia"] = con.execute(
        f"select count(*) from _j where {' or '.join(distinto) or 'false'}").fetchone()[0]
    kn = ", ".join(f"k{i}" for i in range(len(llave)))
    nombres_k = ", ".join(f"k{i} as {M.q(c)}" for i, c in enumerate(llave))
    for lado, a, b in (("stratio", "_s", "_f"), ("fabric", "_f", "_s")):
        cur = con.execute(f"select {', '.join(f'{a}.k{i} as {M.q(c)}' for i, c in enumerate(llave))} from {a} anti join {b} on {on} "
                          f"order by {', '.join(f'{a}.k{i}' for i in range(len(llave)))} limit {ejemplos}")
        out[f"ejemplos_solo_{lado}"] = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    # por columna: conteo exacto en un solo barrido
    if resto:
        r = con.execute("select " + ", ".join(f"count(*) filter (where {x})" for x in distinto) + " from _j").fetchone()
        por_col = {resto[i][0]: r[i] for i in range(len(resto)) if r[i]}
    else:
        por_col = {}
    out["por_columna"] = {}
    for c, n in sorted(por_col.items(), key=lambda kv: -kv[1]):
        i = [x[0] for x in resto].index(c)
        pat = _patron_sql(f"s{i}", f"f{i}")
        filas = con.execute(f"select p, count(*) from (select {pat} p from _j where s{i} is distinct from f{i}) group by 1 order by 2 desc").fetchall()
        det = {"filas_distintas": n, "tipo_stratio": resto[i][1], "tipo_fabric": resto[i][2],
               "patrones": {p: k for p, k in filas}}
        if "diferencia_numerica" in det["patrones"]:
            m = con.execute(f"select max(abs(try_cast(nullif(s{i}, {NULO}) as decimal(38,10)) - try_cast(nullif(f{i}, {NULO}) as decimal(38,10)))), "
                            f"min(abs(try_cast(nullif(s{i}, {NULO}) as decimal(38,10)) - try_cast(nullif(f{i}, {NULO}) as decimal(38,10)))) "
                            f"from _j where {pat} = 'diferencia_numerica'").fetchone()
            det["diferencia_numerica"] = {"max_abs": str(m[0]), "min_abs": str(m[1])}
        if "desplazamiento_horario" in det["patrones"]:
            off = con.execute(f"select date_diff('second', try_cast(nullif(s{i}, {NULO}) as timestamp), try_cast(nullif(f{i}, {NULO}) as timestamp)) / 3600.0 h, "
                              f"count(*) from _j where {pat} = 'desplazamiento_horario' group by 1 order by 2 desc limit 3").fetchall()
            det["desplazamiento_horas"] = {str(h): k for h, k in off}
        if det["patrones"].get("otro"):
            # columna corrida: el valor de Fabric es el de OTRA columna de Stratio en la misma fila (conteo exacto)
            otras = [j for j in range(len(resto)) if j != i]
            if otras:
                r_ = con.execute("select " + ", ".join(f"count(*) filter (where f{i} = s{j} and f{i} <> {NULO} and trim(f{i}) not in ({", ".join(_MARCADORES)}))" for j in otras)
                                 + f" from _j where s{i} is distinct from f{i}").fetchone()
                vc = {resto[j][0]: r_[n_] for n_, j in enumerate(otras) if r_[n_]}
                if vc:
                    det["viene_de_columna"] = dict(sorted(vc.items(), key=lambda kv: -kv[1])[:3])
        cur = con.execute(f"select {nombres_k}, nullif(s{i}, {NULO}) as stratio, nullif(f{i}, {NULO}) as fabric, {pat} as patron "
                          f"from _j where s{i} is distinct from f{i} order by {kn} limit {ejemplos}")
        det["ejemplos"] = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        out["por_columna"][c] = det
    # localizacion por mes
    if fcol:
        out["columna_fecha"] = fcol
        loc = con.execute(f"""
          with a as (select strftime(fecha_s, '%Y-%m') m, 'solo_stratio' t from _s anti join _f on {on}
                     union all select strftime(fecha_f, '%Y-%m'), 'solo_fabric' from _f anti join _s on {on}
                     union all select strftime(fecha_s, '%Y-%m'), 'cambiadas' from _j where {' or '.join(distinto) or 'false'})
          select coalesce(m, 'sin fecha') m, t, count(*) from a group by 1, 2 order by 1, 2""").fetchall()
        meses = {}
        for m, t, k in loc:
            meses.setdefault(m, {})[t] = k
        out["por_mes"] = meses
    if destino:
        for nom, sql in (("solo_stratio", f"select _s.* from _s anti join _f on {on}"),
                         ("solo_fabric", f"select _f.* from _f anti join _s on {on}"),
                         ("cambiadas", f"select * from _j where {' or '.join(distinto) or 'false'}")):
            con.execute(f"copy ({sql}) to {_lit(os.path.join(destino, nom + '.parquet'))} (format parquet)")
        out["detalle"] = destino
        out["columnas_detalle"] = {f"k{i}": c for i, c in enumerate(llave)} | {f"s{i}/f{i}": c for i, (c, _a, _b) in enumerate(resto)}
    for t in ("_s", "_f", "_j", "_rep"):
        con.execute(f"drop table if exists {t}")
    return out


def texto(r, clave=None):
    """Resumen corto para la consola y el chat."""
    f = r["filas"]
    out = [f"{clave or ''} · llave {r.get('llave') or 'NINGUNA'} ({r.get('llave_origen')}) · filas S {f['stratio']:,} | F {f['fabric']:,}".replace(",", "."),
           f"  solo Stratio {f.get('solo_stratio', 0):,} · solo Fabric {f.get('solo_fabric', 0):,}".replace(",", ".")
           + (f" · comunes {f['comunes']:,} · comunes con alguna diferencia {f['comunes_con_alguna_diferencia']:,}".replace(",", ".")
              if "comunes" in f else "")]
    if f.get("llave_repetida"):
        x = f["llave_repetida"]
        out.append(f"  llave repetida: {_m(x['llaves'])} llave(s) · filas Stratio {_m(x['stratio'])} · Fabric {_m(x['fabric'])} (aparte, no se emparejan)")
    for lado in ("solo_en_stratio", "solo_en_fabric"):
        if r["columnas_no_comunes"].get(lado):
            out.append(f"  columnas {lado.replace('_', ' ')}: {', '.join(r['columnas_no_comunes'][lado][:8])}")
    for c, d in list((r.get("por_columna") or {}).items())[:15]:
        pats = " · ".join(f"{p} {_m(k)}" for p, k in d["patrones"].items())
        extra = ""
        if d.get("diferencia_numerica"):
            extra = f" · max |S-F| {d['diferencia_numerica']['max_abs']}"
        if d.get("viene_de_columna"):
            extra += " · Fabric trae el valor de Stratio en: " + ", ".join(f"{c_} ({_m(k)})" for c_, k in d["viene_de_columna"].items())
        if d.get("desplazamiento_horas"):
            extra += " · horas " + ", ".join(f"{h}h×{k}" for h, k in d["desplazamiento_horas"].items())
        out.append(f"  {c}: {_m(d['filas_distintas'])} filas · {pats}{extra}")
        if d["ejemplos"]:
            out.append(f"     ej. {json.dumps(d['ejemplos'][0], ensure_ascii=False, default=str)[:180]}")
    if len(r.get("por_columna") or {}) > 15:
        out.append(f"  … {len(r['por_columna']) - 15} columna(s) más en el resumen JSON")
    if r.get("por_mes"):
        top = sorted(r["por_mes"].items(), key=lambda kv: -sum(kv[1].values()))[:6]
        out.append(f"  por mes de {r['columna_fecha']} (los 6 con más filas): " + " · ".join(
            f"{m}: " + ", ".join(f"{k.replace('_', ' ')} {_m(v)}" for k, v in d.items()) for m, d in top))
    if r.get("aviso"):
        out.append(f"  AVISO: {r['aviso']}")
    return "\n".join(out)
