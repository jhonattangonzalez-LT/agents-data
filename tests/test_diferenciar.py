"""Diferencias por llave sobre tablas sinteticas: un caso por patron (python -m pytest tests/test_diferenciar.py)."""
import duckdb

from pc.cotejo import diferenciar as D


def _con():
    con = duckdb.connect()
    con.execute("""create table S as select * from (values
      (1, 'A', 'Juan', 10.50, timestamp '2024-01-01 10:00:00', 'x', '007', '2024-01-05'),
      (1, 'B', 'Ana ', 20.00, timestamp '2024-01-02 10:00:00', 'y', '008', '2024-02-05'),
      (2, 'A', 'PEDRO', 30.25, timestamp '2024-02-01 10:00:00', null, '009', '2024-03-05'),
      (2, 'B', 'José', 40.00, timestamp '2024-02-02 10:00:00', 'z', '010', '2024-04-05'),
      (3, 'A', 'Muñoz', 50.00, timestamp '2024-03-01 10:00:00', 'w', '011', '2024-05-05'),
      (4, 'A', 'solo S', 1.0, timestamp '2024-03-02 10:00:00', 'v', '012', '2024-06-05')
    ) t(id, tipo, nombre, valor, ts, nota, cod, fecha_txt)""")
    con.execute("""create table F as select * from (values
      (1, 'A', 'Juan', 10.5, timestamp '2024-01-01 15:00:00', 'x', '7', '05/01/2024'),
      (1, 'B', 'Ana', 20.00, timestamp '2024-01-02 15:00:00', 'y', '008', '2024-02-05'),
      (2, 'A', 'pedro', 30.26, timestamp '2024-02-01 15:00:00', '', '009', '2024-03-05'),
      (2, 'B', 'Jose', 40.00, timestamp '2024-02-02 10:00:00', 'z', '010', '2024-04-05'),
      (3, 'A', 'MuÃ±oz', 50.00, timestamp '2024-03-01 10:00:00', 'w', '011', '2024-05-05'),
      (5, 'A', 'solo F', 1.0, timestamp '2024-03-03 10:00:00', 'u', '013', '2024-07-05')
    ) t(id, tipo, nombre, valor, ts, nota, cod, fecha_txt)""")
    return con


def test_llave_compuesta_y_patrones():
    con = _con()
    llave, origen, _ = D.resolver_llave(con)
    assert llave == ["id", "tipo"] and origen == "compuesta_2"
    r = D.diferenciar(con, llave, origen, columna_fecha="ts")
    f = r["filas"]
    assert (f["solo_stratio"], f["solo_fabric"], f["comunes"]) == (1, 1, 5)
    pc = {c: d["patrones"] for c, d in r["por_columna"].items()}
    assert pc["nombre"] == {"espacios": 1, "mayusculas": 1, "acentos_unicode": 1, "mojibake": 1}
    assert pc["valor"] == {"diferencia_numerica": 1}
    assert r["por_columna"]["valor"]["diferencia_numerica"]["max_abs"].startswith("0.01")
    assert pc["ts"] == {"desplazamiento_horario": 3}
    assert r["por_columna"]["ts"]["desplazamiento_horas"] == {"5.0": 3}
    assert pc["nota"] == {"nulo_vs_vacio": 1}
    assert r["por_columna"]["ts"]["patrones"] == {"desplazamiento_horario": 3}
    assert pc["cod"] == {"ceros_izquierda": 1}
    assert pc["fecha_txt"] == {"mismo_instante_otro_formato": 1}
    assert f["comunes_con_alguna_diferencia"] == 5


def test_llave_declarada_no_unica_y_sin_llave():
    con = _con()
    llave, origen, notas = D.resolver_llave(con, declarada=["id"])
    assert origen == "compuesta_2" and "repetidos" in notas[0]
    r = D.diferenciar(con, None, "sin_llave")
    assert r["filas"]["solo_stratio"] == 6 and r["filas"]["solo_fabric"] == 6


def test_mismo_numero_otra_escala():
    con = duckdb.connect()
    con.execute("create table S as select * from (values (1, '1.50'), (2, '2')) t(k, v)")
    con.execute("create table F as select * from (values (1, '1.5'), (2, '2.00')) t(k, v)")
    r = D.diferenciar(con, ["k"], "una_columna")
    assert r["por_columna"]["v"]["patrones"] == {"mismo_numero_otra_escala": 2}


def test_llave_casi_unica_cuenta_repetidas_aparte():
    con = duckdb.connect()
    con.execute("create table S as select 'k' || i as id_x, i % 3 as v from range(40) t(i) union all select 'k5', 9")
    con.execute("create table F as select 'k' || i as id_x, case when i = 7 then 99 else i % 3 end as v from range(1, 41) t(i)")
    llave, origen, _ = D.resolver_llave(con)
    assert (llave, origen) == (["id_x"], "casi_unica")
    r = D.diferenciar(con, ["id_x"], "casi_unica")
    assert r["filas"]["llave_repetida"] == {"llaves": 1, "stratio": 2, "fabric": 1}
    assert (r["filas"]["solo_stratio"], r["filas"]["solo_fabric"], r["filas"]["comunes"]) == (1, 1, 38)
    assert r["por_columna"]["v"]["filas_distintas"] == 1


def test_columna_corrida_y_nulos():
    con = duckdb.connect()
    con.execute("create table S as select * from (values (1, 'A1', 'x', 'p'), (2, 'A2', 'y', 'q'), (3, 'A3', 'z', null)) t(k, cod, nombre, extra)")
    con.execute("create table F as select * from (values (1, 'x', 'x', null), (2, 'y', 'y', null), (3, 'z', 'z', 'r')) t(k, cod, nombre, extra)")
    r = D.diferenciar(con, ["k"], "una_columna")
    assert r["por_columna"]["cod"]["viene_de_columna"] == {"nombre": 3}
    assert r["por_columna"]["extra"]["patrones"] == {"nulo_en_fabric": 2, "nulo_en_stratio": 1}

if __name__ == "__main__":
    import traceback
    malas = 0
    for n, fn in list(globals().items()):
        if n.startswith("test_"):
            try:
                fn()
                print("OK  ", n)
            except Exception:
                malas += 1
                print("FALLA", n)
                traceback.print_exc()
    raise SystemExit(malas)
