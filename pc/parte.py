"""Parte de agente: lo unico que un agente le devuelve al coordinador.

Esquema fijo (trabajos/<T>/partes/p-NNNN.json):
  {"id", "ts", "agente", "flujo", "clave", "estado": OK|AVISO|ERROR|PREGUNTA,
   "hecho": "una o dos lineas",
   "cifras": {"nombre": {"valor": X, "de": "v4/cotejos/k.json#metricas.filas.stratio"}},
   "archivos": ["rel/al/trabajo"], "pendientes": ["..."],
   "pregunta": {"para": "persona|<agente>", "texto": "...", "nodo": "<id del grafo>"} | null,
   "siguiente": "comando o paso"}

Cada cifra lleva su puntero `de` (archivo relativo al trabajo # ruta con puntos; [i] para listas) y se
COMPRUEBA contra el disco al registrar: una cifra que no coincide no entra. Asi las cifras que llegan al
chat y a los reportes son las del JSON, nunca reescritas a mano.
"""
import datetime
import glob
import json
import os
import re

from . import lote as L

ESTADOS = ("OK", "AVISO", "ERROR", "PREGUNTA")


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def resolver(trabajo, puntero):
    """'v4/cotejos/k.json#metricas.filas.stratio' -> valor en disco (KeyError si no existe)."""
    rel, _, ruta = puntero.partition("#")
    doc = L.leer(trabajo, rel)
    if doc is None:
        raise KeyError(f"no existe {rel}")
    x = doc
    for parte in [p for p in re.split(r"\.(?![^\[]*\])", ruta) if p] if ruta else []:
        m = re.fullmatch(r"([^\[]*)((?:\[\d+\])*)", parte)
        if m.group(1):
            x = x[m.group(1)]
        for i in re.findall(r"\[(\d+)\]", m.group(2)):
            x = x[int(i)]
    return x


def registrar(trabajo, agente, doc):
    estado = doc.get("estado", "OK")
    if estado not in ESTADOS:
        raise ValueError(f"estado {estado} no es {ESTADOS}")
    if not doc.get("hecho"):
        raise ValueError("falta 'hecho'")
    malas = []
    cifras = {}
    for nombre, c in (doc.get("cifras") or {}).items():
        if not isinstance(c, dict) or "de" not in c:
            malas.append(f"{nombre}: sin puntero 'de' al JSON del que sale")
            continue
        try:
            real = resolver(trabajo, c["de"])
        except (KeyError, IndexError, TypeError) as e:
            malas.append(f"{nombre}: {c['de']} no se encuentra ({e})")
            continue
        if "valor" in c and c["valor"] != real:
            malas.append(f"{nombre}: dice {c['valor']!r} y en disco es {real!r}")
            continue
        cifras[nombre] = {"valor": real, "de": c["de"]}
    if malas:
        raise ValueError("cifras que no coinciden con el disco:\n  " + "\n  ".join(malas))
    for a in doc.get("archivos") or []:
        if not os.path.exists(os.path.join(L.dir_lote(trabajo), a)) and not os.path.exists(a):
            raise ValueError(f"archivo citado que no existe: {a}")
    d = os.path.join(L.dir_lote(trabajo), "partes")
    os.makedirs(d, exist_ok=True)
    n = len(glob.glob(os.path.join(d, "p-*.json"))) + 1
    pid = f"p-{n:04d}"
    while os.path.exists(os.path.join(d, f"{pid}.json")):
        n += 1
        pid = f"p-{n:04d}"
    out = {"id": pid, "ts": _ahora(), "agente": agente, "flujo": doc.get("flujo"), "clave": doc.get("clave"),
           "estado": estado, "hecho": doc["hecho"], "cifras": cifras, "archivos": doc.get("archivos") or [],
           "pendientes": doc.get("pendientes") or [], "pregunta": doc.get("pregunta"), "siguiente": doc.get("siguiente")}
    L.guardar(trabajo, f"partes/{pid}.json", out)
    L.bitacora(trabajo, agente, "parte", {"parte": pid, "hecho": doc["hecho"][:200]},
               estado={"PREGUNTA": "AVISO"}.get(estado, estado), flujo=out["flujo"], clave=out["clave"],
               salidas=[f"partes/{pid}.json"])
    return out


def listar(trabajo, flujo=None, agente=None, ultimos=None):
    ps = [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(L.dir_lote(trabajo), "partes", "p-*.json")))]
    ps = [p for p in ps if (not flujo or p.get("flujo") == flujo) and (not agente or p.get("agente") == agente)]
    return ps[-ultimos:] if ultimos else ps


def linea(p):
    """La unica linea que el agente devuelve al coordinador."""
    return f"PARTE {p['id']} · {p['estado']} · {p['agente']} · {p.get('flujo') or ''} {p.get('clave') or ''} · {p['hecho'][:140]}"


def texto(p):
    """Parte para leer (compacto)."""
    out = [linea(p)]
    for k, c in p["cifras"].items():
        out.append(f"  {k}: {c['valor']}   ← {c['de']}")
    for a in p["archivos"]:
        out.append(f"  archivo: {a}")
    for x in p["pendientes"]:
        out.append(f"  pendiente: {x}")
    if p.get("pregunta"):
        q = p["pregunta"]
        out.append(f"  PREGUNTA para {q.get('para')}: {q.get('texto')}" + (f"  [nodo {q['nodo']}]" if q.get("nodo") else ""))
    if p.get("siguiente"):
        out.append(f"  siguiente: {p['siguiente']}")
    return "\n".join(out)
