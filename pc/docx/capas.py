"""Capa del acta: SOLO la arquitectura medallón (Bronze · Silver · Gold). Se mide, no se supone; si es ambigua, se pregunta.

Pedido de QA (2026-10-22): «definir bien las capas de acuerdo a la tabla, y si alguna es ambigua, preguntar y no asumir»;
«ten cuidado con los nombres de las capas: escribiste cosas como qa_v2_rc». Un esquema de Postgres, un workspace, un
lakehouse o un pipeline NO son capas.

Valores válidos:  Bronze · Silver · Gold                 (tabla Delta o carpeta de Files de esa capa)
                  <Capa> · Postgres / <Capa> · SFTP     (copia: la capa es la de la tabla que se copia)
                  «Silver y Gold» (flujo que escribe en las dos) · Orquestación (solo orquestadores)

Cómo se fija la capa de una tabla, en orden y con su evidencia:
  1. la ruta de destino: Files/bronze|silver|gold/…  ó  bronze.|silver.|gold.<tabla> (también lh_*.silver.<tabla>)
  2. una tabla de Postgres o un archivo del SFTP: la copia que la escribe (índice de pipelines de pc dependencias,
     ~/.cache/pc/dependencias/indice.json) y la capa de SU origen
  3. si nada de eso la fija: AMBIGUA → no se escribe; va a la lista de preguntas (`preguntas(L)`) y la respuesta se
     guarda en el dato del lote como L["capas_decididas"] = {clave_tabla o flujo: capa}.
La capa del flujo es la de las tablas que escribe (y la carpeta del zip …/flows/<proyecto>/<capa>/…, si no contradice).
"""
import json
import os
import re

MEDALLON = ("Bronze", "Silver", "Gold")
VALIDA = re.compile(r"^(Bronze|Silver|Gold)( y (Silver|Gold))?( · (Postgres|SFTP))?$")
INDICE = os.path.join(os.path.expanduser("~"), ".cache", "pc", "dependencias", "indice.json")
_IDX = None


def _norm(r):
    r = str(r or "").strip().rstrip("/.").lower()
    m = re.search(r"/(files|tables)/(.+)$", r)
    if m and "://" in r:
        r = f"{m.group(1)}/{m.group(2)}"
    if r.startswith("tables/"):
        r = r[7:].replace("/", ".", 1)
    return r[6:] if r.startswith("files/") else r


def base(ruta):
    """Capa medallón por la ruta, o None."""
    r = _norm(ruta)
    m = re.match(r"(bronze|silver|gold)/", r)
    if m:
        return m.group(1).capitalize()
    partes = r.split(".")
    for p in partes[:-1]:                         # silver.tabla · lh_transversal.silver.tabla
        if p in ("bronze", "silver", "gold"):
            return p.capitalize()
    return None


def _indice():
    global _IDX
    if _IDX is None:
        try:
            _IDX = json.load(open(INDICE, encoding="utf8"))
        except (OSError, ValueError):
            _IDX = {}
    return _IDX


def _origen_copia(ruta):
    """Origen de la copia que escribe `ruta` (Postgres o SFTP), según las definiciones de Fabric."""
    r = _norm(ruta)
    for p in (_indice().get("pipelines") or {}).values():
        for c in p.get("copias") or []:
            d = _norm(c.get("destino"))
            if d and (d == r or d.endswith("." + r) or r.endswith("." + d) or r.startswith(d + "/") or d.startswith(r + "/")):
                return c.get("origen"), f"copia «{c.get('actividad')}» del pipeline «{p.get('nombre')}»"
    return None, None


def capa_tabla(ruta_fabric, tipo=None):
    """(capa, evidencia) o (None, motivo de la ambigüedad)."""
    b = base(ruta_fabric)
    if b:
        return b, f"ruta de destino {ruta_fabric}"
    r = _norm(ruta_fabric)
    sufijo = "SFTP" if (tipo == "sftp" or r.startswith("home/")) else "Postgres"
    o, via = _origen_copia(ruta_fabric)
    if o and base(o):
        return f"{base(o)} · {sufijo}", f"{sufijo} escrito por la {via} desde {o}"
    if o:
        return None, f"{sufijo}: la {via} copia desde {o}, que no es una tabla bronze/silver/gold"
    return None, f"{sufijo}: no se encontró la copia que escribe {ruta_fabric} (correr `python -m pc dependencias --refrescar`)"


def capa_flujo(capas_tablas, zip_ruta=None):
    """(capa, evidencia) o (None, motivo). Capa del flujo = capas base de las tablas que escribe."""
    bases = sorted({c.split(" · ")[0] for c in capas_tablas if c}, key=MEDALLON.index)
    z = re.search(r"/flows/[^/]+/(bronze|silver|gold)/", str(zip_ruta or ""), re.I)
    zc = z.group(1).capitalize() if z else None
    if not bases:
        return (zc, f"carpeta del código {zip_ruta}") if zc else (None, "sin tablas con capa medida ni carpeta de código bronze/silver/gold")
    if zc and zc not in bases:
        return None, f"el código está en {zc} ({zip_ruta}) pero las tablas se escriben en {' y '.join(bases)}"
    return " y ".join(bases), "capas de las tablas que escribe"


def valida(capa, grupo=None):
    if grupo in ("orquestadores", "orquestador") and capa == "Orquestación":
        return True
    return bool(capa and VALIDA.match(capa))


def aplicar_decisiones(L):
    """L["capas_decididas"] (respuestas de la persona) sobre los flujos y las tablas del dato del acta."""
    dec = L.get("capas_decididas") or {}
    for f in L.get("flujos") or []:
        if f.get("fabric") in dec:
            f["capa"], f["capa_evidencia"] = dec[f["fabric"]], "decidida por la persona"
        for o in f.get("objetos") or []:
            if o.get("clave") in dec:
                o["capa"], o["capa_evidencia"] = dec[o["clave"]], "decidida por la persona"
    return L


def preguntas(L):
    """Lo que hay que preguntar antes de emitir el acta: capas ausentes, ambiguas o fuera de la arquitectura medallón."""
    out = []
    for f in L.get("flujos") or []:
        if not valida(f.get("capa"), f.get("grupo")):
            out.append({"flujo": f.get("fabric"), "tabla": None, "capa_actual": f.get("capa"),
                        "motivo": f.get("capa_motivo") or ("no es una capa medallón (Bronze, Silver o Gold)" if f.get("capa") else "sin capa")})
        for o in f.get("objetos") or []:
            if not valida(o.get("capa")):
                out.append({"flujo": f.get("fabric"), "tabla": o.get("clave"), "capa_actual": o.get("capa"),
                            "motivo": o.get("capa_motivo") or ("no es una capa medallón (Bronze, Silver o Gold)" if o.get("capa") else "sin capa")})
    return out
