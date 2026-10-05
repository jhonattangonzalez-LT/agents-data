"""Prueba real: ETL Validator v9 parametrizado sobre un flujo de ingesta liviano, y correccion de roles."""
import json, sys, time
sys.path.insert(0, "/home/quind/Projects/pipeline-comfandi")
from pc.etl import validador as V
F = "23-landing-globales-ssf-tipo-identificacion"
l = V.lanzar([F], ejecutar=True, corrida_qa="prueba-2026-10-04")
print("lanzado", json.dumps(l), flush=True)
r = V.seguir(l, avisar=lambda e, s: print(f"{time.strftime('%H:%M:%S')} {e} {s}s", flush=True))
print("fin notebook", r.get("status"), r.get("startTimeUtc"), r.get("endTimeUtc"), json.dumps(r.get("failureReason"))[:500], flush=True)
vs = V.veredictos([F], desde_utc=l["lanzado_utc"])
out = {"lanzamiento": l, "notebook": r, "veredictos": {}}
for f, x in vs.items():
    if not x:
        print("sin veredicto nuevo para", f); continue
    inv = V.corregir(f, x["veredicto"])
    out["veredictos"][f] = {"ruta": x["ruta"], "resumen": V.resumen(f, x["veredicto"], inv), "inventario": inv}
    print(json.dumps(out["veredictos"][f]["resumen"], ensure_ascii=False, default=str), flush=True)
json.dump(out, open("/home/quind/Projects/pipeline-comfandi/pruebas/resultado_etl_v9.json", "w"), indent=1, default=str, ensure_ascii=False)
print("OK")
