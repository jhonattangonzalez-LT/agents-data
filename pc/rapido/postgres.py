"""Reporte RAPIDO (niveles 0 y 1) de una tabla Postgres, medido DENTRO de la base.

El mismo SQL corre en la Postgres de Stratio (psycopg2 por VPN) y en la de Fabric (pipeline
qa_v2_postgres). Solo viajan los agregados: nada de dato. Mismo formato que nivel01, asi el
cotejo rapido no distingue el origen.
"""
import time
from concurrent.futures import ThreadPoolExecutor

from ..config import CFG, PAR
from ..pgfabric import sql as S
from . import nivel01

_TIPOS = {"integer": "int", "bigint": "bigint", "smallint": "smallint", "double precision": "double",
          "real": "float", "boolean": "boolean", "date": "date", "text": "string",
          "character varying": "string", "character": "string", "uuid": "string", "json": "string",
          "jsonb": "string", "time without time zone": "string", "interval": "interval"}


def tipo_spark(c):
    dt = c["data_type"]
    if dt == "numeric":
        p, s = c.get("numeric_precision"), c.get("numeric_scale")
        return f"decimal({int(p)},{int(s or 0)})" if p not in (None, "") and p == p else "decimal(38,18)"
    if dt.startswith("timestamp"):
        return "timestamp"
    return _TIPOS.get(dt, "string")


def ejecutor_stratio(sql_txt):
    from ..acceso import stratio_pg
    cols, filas = stratio_pg.consultar(sql_txt)
    return [dict(zip(cols, f)) for f in filas]


def ejecutor_fabric(sql_txt):
    from ..pgfabric import pipeline
    filas, _r = pipeline.consultar(sql_txt)
    return filas


def medir(tabla, plataforma, ejecutor=None, where=None, ventana=None, columnas_por_consulta=None, paralelo=None):
    """plataforma STRATIO | FABRIC. `where` acota el corte (delimitador de fechas)."""
    t0 = time.time()
    ejecutor = ejecutor or (ejecutor_stratio if plataforma == "STRATIO" else ejecutor_fabric)
    esq = ejecutor(S.esquema(tabla))
    if not esq:
        raise FileNotFoundError(f"{plataforma}: no existe {tabla} (o sin permisos)")
    esq = sorted(esq, key=lambda c: int(c["ordinal_position"]))
    tam = columnas_por_consulta or CFG["postgres"]["columnas_por_consulta"]
    bloques = S.bloques(esq, tam)
    par = paralelo or (PAR["pg_stratio_consultas"] if plataforma == "STRATIO" else PAR["pg_fabric_corridas"])
    with ThreadPoolExecutor(par) as ex:
        res = list(ex.map(lambda b: ejecutor(S.agregados(tabla, b, where))[0], bloques))
    filas = int(res[0]["n"])
    cols, agg_cols = [], {}
    for bi, b in enumerate(bloques):
        r = res[bi]
        for i, c in enumerate(b):
            o = int(c["ordinal_position"]) - 1
            nombre = c["column_name"]
            cols.append({"orden": o, "nombre": nombre, "tipo": tipo_spark(c),
                         "nullable": c.get("is_nullable") != "NO", "fisico": nombre})
            nn = r.get(f"nn_{i}")
            orden = c["data_type"] not in S.NO_ORDENABLE
            agg_cols[nombre] = {"tipo": tipo_spark(c), "orden": o,
                                "nulos": None if nn is None else filas - int(nn),
                                "min": r.get(f"mn_{i}") if orden else None,
                                "max": r.get(f"mx_{i}") if orden else None,
                                "con_estadisticas": orden and nn is not None,
                                "tipo_postgres": c["data_type"]}
            if c["data_type"] in S.TEXTO:
                agg_cols[nombre].update(longitud_minima=r.get(f"lmin_{i}"), longitud_maxima=r.get(f"lmax_{i}"),
                                        cadenas_vacias=r.get(f"vac_{i}"))
    cols.sort(key=lambda c: c["orden"])
    agg = {"filas": filas, "archivos": 0, "columnas": agg_cols, "pedidos": len(bloques) + 1, "bytes_leidos": 0}
    rep = nivel01._armar(plataforma, tabla, "POSTGRES", cols, agg, None, ventana, t0,
                         {"tabla": tabla, "where": where, "consultas": len(bloques) + 1})
    rep["nivel1"]["fuente"] = "sql_en_base"
    rep["nivel0"]["esquema_postgres"] = esq
    return rep
