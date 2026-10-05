"""El LOTE se arma AL FINAL: una persona reune los expedientes de los flujos aprobados (de uno o varios
trabajos), pasa las compuertas y activa el acta.

lotes/<N>/
  lote.json            expedientes incluidos (trabajo, flujo, version, huella), responsable del acta
  expedientes/         copia de cada expediente .md incluido
  revision/            resumen del lote (huella) + compuertas.json
"""
import datetime
import glob
import hashlib
import json
import os
import shutil

from . import lote as T
from .config import RAIZ


def dir_lote(n):
    return os.path.join(RAIZ, "lotes", str(n))


def leer(n, rel, defecto=None):
    p = os.path.join(dir_lote(n), rel)
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else defecto


def guardar(n, rel, doc):
    p = os.path.join(dir_lote(n), rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(doc, open(p, "w"), indent=1, ensure_ascii=False, default=str)
    return p


def disponibles():
    """Todos los expedientes listos para acta en todos los trabajos (el ultimo ciclo de cada flujo)."""
    out = {}
    for p in sorted(glob.glob(os.path.join(RAIZ, "trabajos", "*", "expedientes", "expediente_*_v*.md"))):
        trabajo = p.split(os.sep)[-3]
        base = os.path.basename(p)[len("expediente_"):-3]
        flujo, v = base.rsplit("_v", 1)
        cf = T.leer(trabajo, f"v4/flujos/{flujo}.json") or {}
        if cf.get("encabezado", {}).get("version") != int(v):
            continue                       # expediente de un ciclo ya reemplazado
        clave = flujo
        if clave not in out or int(v) > out[clave]["version"]:
            out[clave] = {"trabajo": trabajo, "flujo": flujo, "version": int(v), "ruta": p,
                          "estado": cf["encabezado"]["estado"], "grupo": cf["encabezado"]["grupo"],
                          "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest()}
    return list(out.values())


def armar(n, responsable, flujos=None):
    """Arma el lote con los expedientes disponibles (todos, o los flujos indicados)."""
    if leer(n, "lote.json"):
        raise FileExistsError(f"el lote {n} ya existe")
    exps = [e for e in disponibles() if not flujos or e["flujo"] in flujos]
    faltan = sorted(set(flujos or []) - {e["flujo"] for e in exps})
    if faltan:
        raise ValueError(f"sin expediente aprobado: {faltan}")
    for e in exps:
        os.makedirs(os.path.join(dir_lote(n), "expedientes"), exist_ok=True)
        shutil.copy(e["ruta"], os.path.join(dir_lote(n), "expedientes", os.path.basename(e["ruta"])))
    doc = {"lote": str(n), "responsable_acta": responsable, "armado_por": T.usuario(),
           "armado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "expedientes": exps}
    guardar(n, "lote.json", doc)
    return doc
