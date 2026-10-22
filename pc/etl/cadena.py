"""Ejecuta cadenas de flujos de Fabric EN ORDEN estricto: cada flujo empieza solo si el anterior termino Completed.

  python -m pc.etl.cadena <cadenas.json> [--cadena N]   (reanudable: salta lo que ya termino Completed)
  Con --cadena N corre solo esa cadena, con su propio estado (estado_cN.json): varias cadenas en paralelo, cada una
  en su orden. Las ingestas ya completadas en cualquier otra cadena (leidas de sus estados en disco) no se repiten.
  Un paso EN_CURSO cuya corrida sigue viva en Fabric se adopta (se espera esa misma corrida, no se relanza).

cadenas.json: {"cadenas": [{"nombre", "flujos": [...], "manuales": [...], "nota_manuales"}]}
- Un fallo detiene todo: nada sigue sobre datos incompletos. Al relanzar, se reintenta desde el flujo que fallo.
- Una ingesta (landing / trusted / crm-masivo / csv_to_parquet) que ya termino en una cadena anterior de esta misma
  orquestacion no se repite; una analitica repetida si se vuelve a correr en su posicion.
- Estado en <carpeta>/estado.json y un renglon por evento en <carpeta>/cadena.log. No mide datos: solo la ejecucion.
"""
import datetime
import json
import os
import re
import sys
import time

from . import validador as V

_INGESTA = re.compile(r"(landing|trusted|crm-masivo|csv_to_parquet)", re.I)


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _adoptar(flujo):
    """Si la ultima corrida del pipeline sigue viva en Fabric, la espera en vez de lanzar otra."""
    from ..acceso import fabric
    from ..config import FAB
    cands = fabric.buscar_item(flujo, ("DataPipeline",), FAB["ws_ingesta"]) or \
        fabric.buscar_item(flujo, ("DataPipeline",), FAB["ws_orquestacion"])
    if not cands:
        return None
    it = cands[0]
    vivas = [r for r in fabric.corridas(it["workspaceId"], it["id"]) if r.get("status") in ("InProgress", "NotStarted")]
    if not vivas:
        return None
    t0 = time.time()
    f = fabric.esperar(it["workspaceId"], it["id"], vivas[0]["id"], max_s=4 * 3600, cada=30)
    return {"estado": f.get("status"), "run": vivas[0]["id"], "inicio_utc": f.get("startTimeUtc"), "fin_utc": f.get("endTimeUtc"),
            "error": f.get("failureReason"), "segundos": round(time.time() - t0), "adoptada": True}


def correr(ruta, solo=None):
    d = json.load(open(ruta, encoding="utf8"))
    base = os.path.dirname(os.path.abspath(ruta))
    pe = os.path.join(base, f"estado_c{solo}.json" if solo else "estado.json")
    est = json.load(open(pe, encoding="utf8")) if os.path.exists(pe) else {"inicio_utc": _ahora(), "pasos": {}}
    log = open(os.path.join(base, "cadena.log"), "a", encoding="utf8")

    def anota(msg):
        log.write(f"{_ahora()} {msg}\n")
        log.flush()
        print(msg, flush=True)

    def guarda():
        tmp = pe + ".tmp"
        json.dump(est, open(tmp, "w", encoding="utf8"), indent=1, ensure_ascii=False)
        os.replace(tmp, pe)

    hechos = {k.split("::", 1)[1] for k, v in est["pasos"].items() if v.get("estado") == "Completed"}
    import glob
    for otro in glob.glob(os.path.join(base, "estado*.json")):      # lo completado por las otras cadenas
        if os.path.abspath(otro) == os.path.abspath(pe):
            continue
        try:
            hechos |= {k.split("::", 1)[1] for k, v in json.load(open(otro, encoding="utf8"))["pasos"].items()
                       if v.get("estado") == "Completed"}
        except Exception:
            pass
    for ci, c in enumerate(d["cadenas"], 1):
        if solo and ci != solo:
            continue
        anota(f"== cadena {ci}: {c['nombre']} · {len(c['flujos'])} flujos")
        for fi, f in enumerate(c["flujos"], 1):
            k = f"{ci}::{f}"
            p = est["pasos"].get(k) or {}
            if p.get("estado") in ("Completed", "OMITIDO_YA_EJECUTADO", "SALTADO_POR_DECISION"):
                if p.get("estado") == "SALTADO_POR_DECISION":
                    anota(f"  {fi:>2}. {f}: SALTADO por decisión ({p.get('motivo', '')}); queda pendiente de re-ejecutar")
                continue
            if ci > 1 and f in hechos and _INGESTA.search(f):
                est["pasos"][k] = {"orden": fi, "estado": "OMITIDO_YA_EJECUTADO", "nota": "ingesta ya completada en una cadena anterior"}
                guarda()
                anota(f"  {fi:>2}. {f}: ya completada en la cadena anterior, no se repite")
                continue
            r = None
            if p.get("estado") == "EN_CURSO":
                try:
                    r = _adoptar(f)
                except Exception:
                    r = None
                if r:
                    anota(f"  {fi:>2}. {f}: se adoptó la corrida que seguía viva en Fabric (no se relanza)")
            if r is None:
                anota(f"  {fi:>2}. {f}: lanzando")
                est["pasos"][k] = {"orden": fi, "estado": "EN_CURSO", "lanzado_utc": _ahora()}
                guarda()
                try:
                    r = V.lanzar_flujo(f)
                except Exception as e:
                    r = {"estado": "ERROR_AL_LANZAR", "error": f"{type(e).__name__}: {str(e)[:300]}"}
            est["pasos"][k].update(estado=r.get("estado"), run=r.get("run"), inicio_utc=r.get("inicio_utc"),
                                   fin_utc=r.get("fin_utc"), segundos=r.get("segundos"), error=r.get("error"))
            guarda()
            anota(f"  {fi:>2}. {f}: {r.get('estado')} · {r.get('segundos')} s" + (f" · {str(r.get('error'))[:200]}" if r.get("error") else ""))
            if r.get("estado") != "Completed":
                est["detenida_en"] = k
                est["fin_utc"] = _ahora()
                guarda()
                anota(f"DETENIDA: {f} terminó {r.get('estado')}. Nada siguió después. Relanzar reintenta desde aquí.")
                return 1
            hechos.add(f)
        if c.get("manuales"):
            anota(f"  AVISO cadena {ci}: cargas a mano sin flujo ({c.get('nota_manuales', '')}): " + ", ".join(c["manuales"]))
    est.pop("detenida_en", None)
    est["fin_utc"] = _ahora()
    guarda()
    salt = [k.split("::", 1)[1] for k, v in est["pasos"].items() if v.get("estado") == "SALTADO_POR_DECISION"]
    anota("COMPLETAS: todas las cadenas terminaron en orden." + (f" Saltados por decisión, pendientes de re-ejecutar: {', '.join(salt)}" if salt else ""))
    return 0


if __name__ == "__main__":
    solo = int(sys.argv[sys.argv.index("--cadena") + 1]) if "--cadena" in sys.argv else None
    sys.exit(correr(sys.argv[1], solo))
