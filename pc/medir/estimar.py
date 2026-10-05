"""Antes del nivel 2: cuanto pesa cada tabla, cuanto tardaria descargar y medir, y si es GRANDE.

Una tabla grande (mas de `grande_filas` filas o `grande_gb` GB) SI se mide, pero solo con confirmacion
explicita del usuario: el coordinador muestra la estimacion y pregunta. La estimacion es de TIEMPO, no del dato:
el dato nunca se estima.
"""
import json
import os

from .. import lote as L
from ..config import CFG, RAIZ

T = CFG["estimacion"]
_MED = os.path.join(RAIZ, "config", "tasas_medidas.json")


def tasas():
    t = dict(T)
    if os.path.exists(_MED):
        for k, v in json.load(open(_MED)).items():
            if v.get("n", 0) >= 3:          # con 3 o mas mediciones reales, manda lo medido
                t[k] = v["promedio"] * (1e6 if k == "medicion_filas_pasada_s" else 1)
    return t


def registrar_tasa(nombre, mb, segundos):
    if not segundos or not mb:
        return
    d = json.load(open(_MED)) if os.path.exists(_MED) else {}
    e = d.setdefault(nombre, {"n": 0, "promedio": None})
    v = mb / segundos
    e["promedio"] = v if e["promedio"] is None else (e["promedio"] * e["n"] + v) / (e["n"] + 1)
    e["n"] += 1
    json.dump(d, open(_MED, "w"), indent=1)


def _fmt(s):
    return f"{s/3600:.1f} h" if s >= 3600 else (f"{s/60:.0f} min" if s >= 60 else f"{s:.0f} s")


def estimar(trabajo, flujo=None):
    t = tasas()
    filas_out = []
    for f, o in L.objetos(trabajo):
        if flujo and f["nombre_fabric"] != flujo:
            continue
        for lado in ("FABRIC", "STRATIO"):
            src = o.get(lado.lower())
            if not src:
                continue
            rap = L.leer(trabajo, f"rapido/{lado}/{o['clave']}.json") or {}
            pend = L.leer(trabajo, f"rapido/{lado}/{o['clave']}.pendiente.json") or {}
            mb = ((rap.get("costo") or {}).get("bytes_objeto") or pend.get("bytes") or 0) / 1e6
            filas = (rap.get("nivel1") or {}).get("filas")
            archivos = (rap.get("nivel1") or {}).get("archivos") or pend.get("archivos") or 1
            tipo = src["tipo"]
            if lado == "FABRIC" and tipo in ("delta", "files"):
                desc, via = mb / t["onelake_mb_s"], "OneLake"
            elif lado == "FABRIC" and tipo == "pg":
                desc, via = mb / t["pg_fabric_extraccion_mb_s"], "Postgres Fabric (pipeline qa_v2_postgres)"
            elif tipo == "hdfs":
                desc, via = mb / t["rocket_mb_s"] + archivos * t["rocket_s_por_archivo"], "Rocket (HDFS Stratio, en serie)"
            elif tipo == "pg":
                desc, via = mb / t["pg_stratio_extraccion_mb_s"], "Postgres Stratio por VPN"
            else:
                desc, via = mb / t["rocket_mb_s"], "SFTP Stratio"
            ncol = (rap.get("nivel0") or {}).get("num_columnas") or 20
            pasadas = 2 + -(-ncol // t["columnas_por_pasada"])      # hash + frecuentes + perfil por bloques
            med = (filas or mb * 1e6 / 50) * pasadas / t["medicion_filas_pasada_s"]
            grande = (filas or 0) > t["grande_filas"] or mb / 1000 > t["grande_gb"]
            filas_out.append({"flujo": f["nombre_fabric"], "clave": o["clave"], "lado": lado, "via": via,
                              "filas": filas, "mb": round(mb, 1), "sin_tamano": not mb,
                              "descarga_s": round(desc), "medicion_s": round(med), "total_s": round(desc + med),
                              "total": _fmt(desc + med), "grande": grande})
    return filas_out
