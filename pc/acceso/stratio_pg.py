"""Postgres y SFTP de Stratio (solo por VPN). Credenciales en ~/Projects/.stratio_conn.json.

Regla: medir sin indisponibilizar la base. Una consulta lleva statement_timeout, las columnas van
por bloques y el numero de consultas simultaneas lo limita el llamador (paralelismo.pg_stratio_consultas).
"""
import json
import socket

from ..config import CFG, secreto_ruta


def _cf(clave):
    return json.load(open(secreto_ruta("stratio_conn"), encoding="utf8"))[clave]


def vpn_ok(timeout=10):
    """¿Llega la maquina a la Postgres de Stratio? (prueba TCP, sin credenciales)."""
    cf = _cf("postgres")
    try:
        with socket.create_connection((cf["host"], int(cf["port"])), timeout=timeout):
            return True
    except OSError:
        return False


def conectar(timeout_consulta=None):
    import psycopg2
    cf = _cf("postgres")
    cn = psycopg2.connect(host=cf["host"], port=cf["port"], dbname=cf["dbname"], user=cf["user"],
                          password=cf["password"], connect_timeout=30, keepalives=1,
                          keepalives_idle=60, keepalives_interval=30, keepalives_count=10,
                          application_name="qa_pipeline_v2")
    cn.set_session(readonly=True, autocommit=True)
    t = timeout_consulta or CFG["postgres"]["timeout_consulta"]
    h, m, s = (int(x) for x in t.split(":"))
    with cn.cursor() as cur:
        cur.execute(f"set statement_timeout = {(h * 3600 + m * 60 + s) * 1000}")
    return cn


def consultar(sql, params=None, timeout_consulta=None):
    cn = conectar(timeout_consulta)
    try:
        with cn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return cols, cur.fetchall()
    finally:
        cn.close()


def sftp():
    """(transport, cliente). El llamador cierra los dos."""
    import paramiko
    cf = _cf("sftp")
    t = paramiko.Transport((cf["host"], int(cf["port"])))
    t.banner_timeout = 60
    t.connect(username=cf["user"], password=cf["password"])
    return t, paramiko.SFTPClient.from_transport(t)
