"""Cache de descargas del nivel 2: donde vive cada archivo bajado, cuanto ocupa y cuando se puede borrar.

Estructura:  cache/<lote>/<STRATIO|FABRIC>/<clave>/...   +   cache/<lote>/manifiesto.json
Cada entrada del manifiesto registra origen, archivos, bytes, version Delta, cuando se bajo y en que
estado esta su uso: DESCARGADO -> MEDIDO -> COTEJADO -> PUBLICADO. Solo se borra lo PUBLICADO (o
lo que el coordinador marque explicitamente), y siempre al final del lote, nunca a mitad.
"""
import datetime
import fcntl
import json
import os
import shutil

from ..config import CFG, ruta

RAIZ = ruta(CFG["cache"]["raiz"])
ORDEN = ["DESCARGADO", "MEDIDO", "COTEJADO", "PUBLICADO"]


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def carpeta(lote, plataforma, clave):
    return os.path.join(RAIZ, str(lote), plataforma.upper(), clave)


def _man(lote):
    return os.path.join(RAIZ, str(lote), "manifiesto.json")


def _editar(lote, fn):
    os.makedirs(os.path.join(RAIZ, str(lote)), exist_ok=True)
    with open(_man(lote) + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        m = json.load(open(_man(lote))) if os.path.exists(_man(lote)) else {"lote": lote, "entradas": {}}
        r = fn(m)
        tmp = _man(lote) + f".{os.getpid()}.tmp"
        json.dump(m, open(tmp, "w"), indent=1, ensure_ascii=False)
        os.replace(tmp, _man(lote))
        return r


def registrar(lote, plataforma, clave, origen, archivos, meta=None):
    k = f"{plataforma.upper()}/{clave}"

    def fn(m):
        m["entradas"][k] = {"plataforma": plataforma.upper(), "clave": clave, "origen": origen,
                            "carpeta": carpeta(lote, plataforma, clave), "archivos": len(archivos),
                            "bytes": sum(os.path.getsize(a) for a in archivos if os.path.exists(a)),
                            "meta": meta or {}, "estado": "DESCARGADO", "descargado_utc": _ahora(),
                            "historial": [("DESCARGADO", _ahora())]}
        return m["entradas"][k]
    return _editar(lote, fn)


def marcar(lote, plataforma, clave, estado):
    assert estado in ORDEN, estado
    k = f"{plataforma.upper()}/{clave}"

    def fn(m):
        e = m["entradas"].get(k)
        if not e:
            raise KeyError(k)
        if ORDEN.index(estado) > ORDEN.index(e["estado"]):
            e["estado"] = estado
        e["historial"].append((estado, _ahora()))
        return e
    return _editar(lote, fn)


def manifiesto(lote):
    return json.load(open(_man(lote))) if os.path.exists(_man(lote)) else {"lote": lote, "entradas": {}}


def espacio():
    tot, usado, libre = shutil.disk_usage(RAIZ if os.path.exists(RAIZ) else os.path.expanduser("~"))
    ocupado = 0
    for r, _d, fs in os.walk(RAIZ):
        for f in fs:
            try:
                ocupado += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    return {"cache_gb": round(ocupado / 1e9, 2), "disco_libre_gb": round(libre / 1e9, 1),
            "tope_cache_gb": CFG["cache"]["max_gb"], "margen_libre_gb": CFG["cache"]["margen_libre_gb"]}


def cabe(bytes_nuevos):
    e = espacio()
    return (e["cache_gb"] + bytes_nuevos / 1e9 <= e["tope_cache_gb"] and
            e["disco_libre_gb"] - bytes_nuevos / 1e9 >= e["margen_libre_gb"])


def limpiar(lote, solo_estado="PUBLICADO", forzar=False, simular=True):
    """Borra las carpetas de la cache del lote. Por defecto SIMULA y solo toma lo PUBLICADO.
    forzar=True borra todo el lote (lo decide el coordinador al cerrar el lote)."""
    m = manifiesto(lote)
    borrar = [e for e in m["entradas"].values() if forzar or e["estado"] == solo_estado]
    libera = sum(e["bytes"] for e in borrar)
    if not simular:
        for e in borrar:
            if os.path.isdir(e["carpeta"]) and os.path.abspath(e["carpeta"]).startswith(os.path.abspath(RAIZ)):
                shutil.rmtree(e["carpeta"])

        def fn(mm):
            for e in borrar:
                k = f"{e['plataforma']}/{e['clave']}"
                mm["entradas"][k]["borrado_utc"] = _ahora()
                mm["entradas"][k]["estado_al_borrar"] = mm["entradas"][k]["estado"]
        _editar(lote, fn)
    return {"simulado": simular, "carpetas": len(borrar), "libera_gb": round(libera / 1e9, 2),
            "pendientes_sin_publicar": [k for k, e in m["entradas"].items() if e["estado"] != "PUBLICADO"]}
