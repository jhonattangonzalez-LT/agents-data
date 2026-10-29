"""Descargas que se caen: que quedo completo y como cotejar esa parte (siempre con la persona y con salvedad).

Cada descarga escribe <carpeta>/.esperados.json (archivo relativo y tamano) antes de empezar y lo borra al terminar
bien. Si la VPN, la cookie o OneLake cortan, el archivo queda: `inventario()` dice cuantos archivos llegaron completos
(mismo tamano), cuantos faltan y que particiones (`col=valor`) estan enteras. Con eso el coordinador PREGUNTA si se
coteja solo esa parte; si la persona acepta, `pc descargar --parcial` registra en el manifiesto solo lo completo y el
cotejo de la tabla lleva la descarga parcial como faltante hasta que se registra `salvedad_parcial` en lote.json
(cotejo por corte sobre las particiones completas, `pc comparar --sql`). Nunca se presenta como el dato completo.
"""
import collections
import json
import os

NOMBRE = ".esperados.json"


def esperados(carpeta, archivos, origen):
    """archivos = [(ruta relativa, bytes)] que la descarga debe dejar en `carpeta`."""
    os.makedirs(carpeta, exist_ok=True)
    json.dump({"origen": origen, "archivos": [[r, s] for r, s in archivos]}, open(os.path.join(carpeta, NOMBRE), "w"))


def completa(carpeta):
    p = os.path.join(carpeta, NOMBRE)
    if os.path.exists(p):
        os.remove(p)


def _particion(rel):
    return "/".join(x for x in rel.split("/")[:-1] if "=" in x) or None


def inventario(carpeta):
    """None si la ultima descarga termino bien (o no hay registro). Si quedo a medias: cifras de lo completo y lo que falta."""
    p = os.path.join(carpeta, NOMBRE)
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    comp, falt = [], []
    for rel, s in d["archivos"]:
        loc = os.path.join(carpeta, rel)
        ok = os.path.exists(loc) and (s is None or os.path.getsize(loc) == s)
        (comp if ok else falt).append((rel, s))
    datos = lambda xs: [x for x in xs if not x[0].startswith("_delta_log/") and not x[0].endswith((".crc", ".json"))]
    por_part = collections.defaultdict(lambda: [0, 0])
    for rel, _ in datos(comp):
        por_part[_particion(rel)][0] += 1
    for rel, _ in datos(falt):
        por_part[_particion(rel)][1] += 1
    enteras = sorted(k for k, (c, f) in por_part.items() if k and c and not f)
    return {"origen": d["origen"], "archivos_total": len(datos(comp)) + len(datos(falt)), "archivos_completos": len(datos(comp)),
            "bytes_total": sum(s or 0 for _, s in datos(comp) + datos(falt)), "bytes_completos": sum(s or 0 for _, s in datos(comp)),
            "particiones_enteras": enteras, "particiones_incompletas": sorted(k for k, (c, f) in por_part.items() if k and f),
            "sin_particiones": not any(por_part), "completos": [os.path.join(carpeta, r) for r, _ in datos(comp)],
            "faltan_delta_log": any(r.startswith("_delta_log/") for r, _ in falt)}


def texto(inv, clave, lado):
    pct = 100 * inv["bytes_completos"] / inv["bytes_total"] if inv["bytes_total"] else 0
    mb = lambda b: f"{b / 1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    t = (f"CAÍDA {lado} · {clave}: {inv['archivos_completos']} de {inv['archivos_total']} archivo(s) completos "
         f"({mb(inv['bytes_completos'])} de {mb(inv['bytes_total'])} MB, {pct:.0f} %)")
    if inv["particiones_enteras"]:
        t += (f" · {len(inv['particiones_enteras'])} partición(es) enteras (p. ej. {inv['particiones_enteras'][0]}): "
              "se pueden cotejar por corte contra las mismas particiones del otro lado")
    elif inv["sin_particiones"]:
        t += " · la tabla no está particionada: una parte de los archivos es un subconjunto arbitrario de filas (solo sirve para perfil y llaves, no para conteos)"
    if inv["faltan_delta_log"]:
        t += " · falta parte del _delta_log: se leería como parquet sin deletion vectors"
    return t + ("\n  → PREGUNTAR a la persona: reintentar la descarga completa · cotejar esta parte (`pc descargar --parcial`, "
                "cotejo por corte con salvedad) · esperar a que vuelva la VPN/cookie"
                + (" · pedir a analítica una copia particionada (`pc mensaje --para particion`)" if lado.upper() == "STRATIO" else ""))


def registrar(lote, plataforma, clave, inv):
    """Manifiesto con SOLO los archivos completos y la marca de descarga parcial (la lee el cotejo de la tabla)."""
    from . import gestor
    from ..medir.completo import _lector
    meta = {"lector": "parquet" if plataforma.upper() == "FABRIC" else _lector(inv["completos"]),
            "parcial": {k: inv[k] for k in ("archivos_total", "archivos_completos", "bytes_total", "bytes_completos",
                                            "particiones_enteras", "particiones_incompletas", "sin_particiones")}}
    return gestor.registrar(lote, plataforma, clave, inv["origen"], inv["completos"], meta)
