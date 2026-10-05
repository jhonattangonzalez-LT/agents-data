"""Mesa de analisis del cotejador (nivel 2): las dos tablas descargadas, abiertas lado a lado en DuckDB.

Las DIFERENCIAS no las calcula un algoritmo: las encuentra y explica el agente cotejador mirando las dos
tablas, en paralelo a la medicion de metricas. Esta mesa le da:
  S  = la tabla de Stratio (la verdad)      F = la tabla de Fabric
  con la misma vista que uso el medidor (ventana de fechas, columnas excluidas, tipos de Postgres).

  python -m pc comparar --trabajo T --clave K --sql "select count(*) from S"
  python -m pc comparar --trabajo T --clave K --solo STRATIO --limite 5     # filas que solo estan en Stratio
  python -m pc comparar --trabajo T --clave K --columna Sueldo               # valores de esa columna a cada lado

Todo exacto: EXCEPT ALL compara multiconjuntos de filas completas (cuenta repetidas).
Lo que el agente concluye se escribe con `python -m pc diferencia …` dentro del cotejo.
"""
import json

from .. import lote as L
from ..cache import gestor
from ..medir import completo as C
from ..medir import motor_v15 as M


def abrir(trabajo, clave):
    man = gestor.manifiesto(trabajo)["entradas"]
    f, o = next(((f, o) for f, o in L.objetos(trabajo) if o["clave"] == clave), (None, None))
    if not o:
        raise KeyError(f"{clave} no esta en el trabajo {trabajo}")
    con = C.conectar()
    vistas = {}
    for lado, nombre in (("STRATIO", "S"), ("FABRIC", "F")):
        e = man.get(f"{lado}/{clave}")
        if not e:
            raise FileNotFoundError(f"{lado}/{clave} no esta descargado: correr `python -m pc descargar`")
        src = o.get(lado.lower()) or {}
        filtro = None
        if o.get("ventana_fechas") and src.get("tipo") != "pg":
            v = o["ventana_fechas"]
            c = M.q(v["columna"])
            filtro = " and ".join(([f"{c} >= '{v['desde']}'"] if v.get("desde") else []) + ([f"{c} <= '{v['hasta']}'"] if v.get("hasta") else []))
        vistas[nombre] = C.vista(con, e["carpeta"], e["meta"].get("lector", "parquet"), filtro=filtro or None,
                                 excluir=o.get("excluir_columnas", ()), tipos_pg=e["meta"].get("esquema_postgres"),
                                 nombre=nombre, cast_varchar=src.get("cast_varchar"), csv=src.get("csv"))
    return con, {"flujo": f["nombre_fabric"], "grupo": f["grupo"], "vistas": vistas}


def _comunes(con):
    s = [r[0] for r in con.execute("describe select * from S").fetchall()]
    fset = {r[0] for r in con.execute("describe select * from F").fetchall()}
    return [c for c in s if c in fset]


def consultar(con, sql, limite=200):
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return cols, [list(r) for r in cur.fetchmany(limite)]


def solo_en(con, lado, limite=5):
    """Filas completas que estan en un lado y no en el otro (multiconjunto exacto) y cuantas son."""
    cols = ", ".join(M.q(c) for c in _comunes(con))
    a, b = ("S", "F") if lado.upper().startswith("S") else ("F", "S")
    total = con.execute(f"select count(*) from (select {cols} from {a} except all select {cols} from {b})").fetchone()[0]
    c, filas = consultar(con, f"select {cols} from {a} except all select {cols} from {b}", limite)
    return {"lado": "STRATIO" if a == "S" else "FABRIC", "filas_solo_en_este_lado": total, "columnas": c, "ejemplos": filas}


def columna(con, col, limite=10):
    """Distribucion exacta de una columna a cada lado (valores con su conteo), para ver que cambia."""
    q = M.q(col)
    sql = (f"with s as (select cast({q} as varchar) v, count(*) n from S group by 1), "
           f"f as (select cast({q} as varchar) v, count(*) n from F group by 1) "
           f"select coalesce(s.v, f.v) valor, coalesce(s.n, 0) stratio, coalesce(f.n, 0) fabric "
           f"from s full join f on s.v is not distinct from f.v where coalesce(s.n,0) <> coalesce(f.n,0) "
           f"order by abs(coalesce(s.n,0) - coalesce(f.n,0)) desc")
    total = con.execute(f"select count(*) from ({sql})").fetchone()[0]
    cols, filas = consultar(con, sql, limite)
    return {"columna": col, "valores_con_conteo_distinto": total, "columnas": cols, "ejemplos": filas}


def imprimir(x):
    print(json.dumps(x, ensure_ascii=False, indent=1, default=str))
