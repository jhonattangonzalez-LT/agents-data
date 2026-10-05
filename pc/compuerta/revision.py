"""Compuertas finales antes del acta: revision QA (humana) -> revision Comfandi -> aprobacion.

Como varios usuarios activan agentes, el acta final la genera UNA persona (responsable_acta del
lote) y solo cuando las tres compuertas estan APROBADAS sobre la MISMA version del resumen. Si el
resumen cambia despues de una aprobacion (otra medicion, otro cotejo), las aprobaciones se
invalidan: la huella del resumen va dentro de cada aprobacion.
"""
import datetime
import hashlib
import json
import os

from .. import lote_final as L
from .. import lote as T

COMPUERTAS = ("revision_qa", "revision_comfandi", "aprobacion")
DECISIONES = ("APROBADO", "CON_OBSERVACIONES", "RECHAZADO")


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def consolidar(lote):
    """Resumen del LOTE armado (lotes/<N>/): un renglon por expediente incluido, con su huella."""
    d = L.leer(lote, "lote.json")
    if not d:
        raise FileNotFoundError(f"el lote {lote} no esta armado: python -m pc lote armar")
    flujos = []
    for e in d["expedientes"]:
        cf = T.leer(e["trabajo"], f"v4/flujos/{e['flujo']}.json") or {}
        flujos.append({"flujo": e["flujo"], "trabajo": e["trabajo"], "version": e["version"], "grupo": e["grupo"],
                       "nombre_stratio": cf.get("encabezado", {}).get("flujo", {}).get("stratio"),
                       "fl": cf.get("encabezado", {}).get("flujo", {}).get("fl"),
                       "estado": cf.get("encabezado", {}).get("estado"), "expediente_sha256": e["sha256"],
                       "tablas": cf.get("tablas"), "verificacion": cf.get("verificacion")})
    res = {"lote": str(lote), "generado_utc": _ahora(), "generado_por": T.usuario(),
           "responsable_acta": d.get("responsable_acta"), "flujos": flujos}
    res["huella"] = hashlib.sha256(json.dumps(flujos, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]
    L.guardar(lote, "revision/resumen.json", res)
    with open(os.path.join(L.dir_lote(lote), "revision", "RESUMEN_LOTE.md"), "w", encoding="utf8") as fh:
        fh.write(_md(res))
    return res


def _md(res):
    out = [f"# Lote {res['lote']} · resumen para las compuertas", "",
           f"Huella `{res['huella']}` · {res['generado_utc']} · armado por {res['generado_por']} · "
           f"responsable del acta: **{res['responsable_acta']}**", "",
           "Cada aprobación queda atada a esta huella: si el lote cambia, hay que aprobar de nuevo.", ""]
    for g in ("ingesta", "analitica", "orquestador"):
        fs = [f for f in res["flujos"] if f["grupo"] == g]
        if not fs:
            continue
        out += [f"## {g.capitalize()} · {len(fs)} flujo(s)", "", "| Flujo | Stratio | FL | v | Estado | Tablas |", "|---|---|---|---|---|---|"]
        out += [f"| `{f['flujo']}` | {f.get('nombre_stratio') or 'por definir'} | {f.get('fl') or 'sin código FL'} | v{f['version']} | "
                f"{f['estado']} | {len(f.get('tablas') or [])} |" for f in fs]
        out.append("")
    out += ["Los expedientes completos están en `expedientes/`.", "",
            "Compuertas: revisión QA → revisión Comfandi → aprobación (`python -m pc revision aprobar …`)."]
    return "\n".join(out)


def registrar(lote, compuerta, decision, persona=None, notas=""):
    assert compuerta in COMPUERTAS and decision in DECISIONES
    res = L.leer(lote, "revision/resumen.json")
    if not res:
        raise RuntimeError("primero consolidar el lote")
    est = L.leer(lote, "revision/compuertas.json", {}) or {}
    previa = COMPUERTAS[COMPUERTAS.index(compuerta) - 1] if COMPUERTAS.index(compuerta) else None
    if previa and (est.get(previa) or {}).get("decision") != "APROBADO":
        raise RuntimeError(f"la compuerta {compuerta} exige {previa} APROBADO antes")
    est[compuerta] = {"decision": decision, "persona": persona or T.usuario(), "utc": _ahora(),
                      "huella_resumen": res["huella"], "notas": notas}
    L.guardar(lote, "revision/compuertas.json", est)
    L.guardar(lote, "revision/bitacora_compuertas.json", (L.leer(lote, "revision/bitacora_compuertas.json", []) or []) +
              [{"utc": _ahora(), "compuerta": compuerta, "decision": decision, "persona": persona or T.usuario(), "notas": notas}])
    return estado(lote)


def estado(lote):
    res = L.leer(lote, "revision/resumen.json") or {}
    est = L.leer(lote, "revision/compuertas.json", {}) or {}
    d = L.leer(lote, "lote.json") or {}
    filas = []
    for c in COMPUERTAS:
        e = est.get(c) or {}
        vigente = e.get("huella_resumen") == res.get("huella")
        filas.append({"compuerta": c, "decision": e.get("decision"), "persona": e.get("persona"), "utc": e.get("utc"),
                      "vigente": vigente if e else None})
    listo = all(f["decision"] == "APROBADO" and f["vigente"] for f in filas)
    return {"lote": str(lote), "huella_resumen": res.get("huella"), "compuertas": filas,
            "responsable_acta": d.get("responsable_acta"), "puede_generar_acta": listo}


def autorizar_acta(lote, persona=None):
    """Lo llama el agente de acta antes de generar: falla si no corresponde."""
    e = estado(lote)
    quien = persona or T.usuario()
    if not e["puede_generar_acta"]:
        raise PermissionError(f"faltan compuertas: {[c for c in e['compuertas'] if c['decision'] != 'APROBADO' or not c['vigente']]}")
    if e["responsable_acta"] and quien != e["responsable_acta"]:
        raise PermissionError(f"el acta del lote {lote} la genera {e['responsable_acta']}, no {quien}")
    L.guardar(lote, "revision/autorizacion_acta.json", {"persona": quien, "huella": e["huella_resumen"], "utc": _ahora()})
    return e
