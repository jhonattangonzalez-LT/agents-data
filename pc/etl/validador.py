"""ETL Validator v9 en Fabric, manejado desde local.

Se despliega UNA vez como notebook `qa_v2_etl_validator` (copia fiel de etl_validator_fabric_v9.ipynb
mas una celda de parametros) y se lanza con RunNotebook pasando la lista de flujos. Ya no hace
falta crear una copia del notebook por lote.

Despues de la corrida, el veredicto de cada flujo se baja y se CORRIGE con el inventario de roles
(codigo del flujo + commits Delta): el validador asigna entrada/salida por el nombre de la bandera
y en los flujos encadenados de un orquestador los invierte.
"""
import copy
import datetime
import json
import os
import time

from ..acceso import fabric, onelake as ol
from ..config import FAB, ruta

WS = FAB["ws_datalake"]
NOMBRE = FAB["notebook_etl"]
RAIZ_VAL = "Files/resultados/reportes_v3/validador"

_META = {"language_info": {"name": "python"},
         "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
         "microsoft": {"language": "python", "language_group": "synapse_pyspark"},
         "kernel_info": {"name": "synapse_pyspark"},
         "dependencies": {"lakehouse": {"known_lakehouses": [{"id": FAB["lh_transversal"]}],
                                        "default_lakehouse": FAB["lh_transversal"],
                                        "default_lakehouse_name": "lh_transversal",
                                        "default_lakehouse_workspace_id": WS}}}

_PARAMS = '''# QA v2 · PARAMETROS (celda "parameters": RunNotebook los sobreescribe)
FLUJOS_JSON = ""      # lista JSON de flujos; vacio = la lista del Paso 1
EJECUTAR_TXT = ""     # "true" | "false"; vacio = lo del Paso 1
CORRIDA_QA = ""       # id de la corrida QA v2 que lanza esto (trazabilidad)
'''
_APLICAR = '''# QA v2 · aplica los parametros recibidos sobre el Paso 1
import json as _json_qa
if FLUJOS_JSON:
    FLUJOS = _json_qa.loads(FLUJOS_JSON)
if EJECUTAR_TXT:
    EJECUTAR = EJECUTAR_TXT.strip().lower() == "true"
print(f"QA v2 · corrida {CORRIDA_QA or '-'} · {len(FLUJOS)} flujo(s) · EJECUTAR={EJECUTAR}")
'''


def construir_notebook(fuente=None):
    nb = json.load(open(ruta(fuente or FAB["notebook_etl_fuente"]), encoding="utf8"))
    nb = copy.deepcopy(nb)
    for c in nb["cells"]:
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
        c.setdefault("metadata", {})
    nb["metadata"] = _META
    # despues del Paso 1 (celda 2): parametros + aplicacion
    i = next(n for n, c in enumerate(nb["cells"]) if c["cell_type"] == "code" and "PASO 1" in "".join(c["source"]))
    par = {"cell_type": "code", "metadata": {"tags": ["parameters"], "microsoft": {"language": "python"}},
           "source": _PARAMS.splitlines(True), "outputs": [], "execution_count": None}
    apl = {"cell_type": "code", "metadata": {"microsoft": {"language": "python"}},
           "source": _APLICAR.splitlines(True), "outputs": [], "execution_count": None}
    nb["cells"][i + 1:i + 1] = [par, apl]
    return nb


def buscar(nombre=NOMBRE):
    return next((i for i in fabric.items(WS, "Notebook") if i["displayName"] == nombre), None)


def desplegar(nombre=NOMBRE, fuente=None):
    contenido = json.dumps(construir_notebook(fuente), ensure_ascii=False)
    partes = {"notebook-content.ipynb": contenido}
    it = buscar(nombre)
    if it:
        c, b = fabric.actualizar_definicion(WS, it["id"], partes, formato="ipynb")
        if c not in (200, 202):
            raise RuntimeError(f"updateDefinition notebook: HTTP {c} {str(b)[:300]}")
        return it
    c, b = fabric.crear_item(WS, nombre, "Notebook", partes, "QA v2 · ETL Validator v9 parametrizado", formato="ipynb")
    if c not in (200, 201):
        raise RuntimeError(f"crear notebook: HTTP {c} {str(b)[:300]}")
    return b if isinstance(b, dict) and b.get("id") else buscar(nombre)


def lanzar(flujos, ejecutar=True, corrida_qa="", nombre=NOMBRE):
    it = buscar(nombre)
    if not it:
        raise RuntimeError(f"no existe {nombre}: correr desplegar()")
    params = {"FLUJOS_JSON": {"value": json.dumps(list(flujos)), "type": "string"},
              "EJECUTAR_TXT": {"value": "true" if ejecutar else "false", "type": "string"},
              "CORRIDA_QA": {"value": corrida_qa, "type": "string"}}
    run = fabric.lanzar(WS, it["id"], "RunNotebook", params)
    return {"notebook": nombre, "item": it["id"], "run": run, "flujos": list(flujos), "ejecutar": ejecutar,
            "lanzado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}


def seguir(lanzamiento, max_s=6 * 3600, avisar=None):
    return fabric.esperar(WS, lanzamiento["item"], lanzamiento["run"], max_s=max_s, cada=60, avisar=avisar)


def veredictos(flujos, desde_utc=None):
    """Ultimo veredicto publicado de cada flujo (opcionalmente posterior a `desde_utc`)."""
    from ..rapido.delta_remoto import a_utc
    out = {}
    for f in flujos:
        ps = [p for p in ol.listar(f"{RAIZ_VAL}/flujos/{f}", True) if not p["isDirectory"] and p["name"].endswith(".json")]
        mejor = None
        for p in sorted(ps, key=lambda p: p["name"]):
            try:
                d = json.loads(ol.leer(p["name"]))
            except Exception:
                continue
            g = d.get("generado_utc")
            if desde_utc and g and a_utc(g) < a_utc(desde_utc):
                continue
            if mejor is None or (g or "") >= (mejor[1].get("generado_utc") or ""):
                mejor = (p["name"], d)
        out[f] = {"ruta": mejor[0], "veredicto": mejor[1]} if mejor else None
    return out


def revision_analitica(flujo, desde_utc=None):
    """Paso 11 del validador (validador/analitica/<flujo>/): la ultima posterior a `desde_utc`."""
    from ..rapido.delta_remoto import a_utc
    ps = sorted(p["name"] for p in ol.listar(f"{RAIZ_VAL}/analitica/{flujo}", True)
                if not p["isDirectory"] and p["name"].endswith(".json"))
    for n in reversed(ps):
        try:
            d = json.loads(ol.leer(n))
        except Exception:
            continue
        if desde_utc and d.get("generado_utc") and a_utc(d["generado_utc"]) < a_utc(desde_utc):
            return None
        return dict(d, ruta_onelake=n)
    return None


def corregir(flujo, veredicto):
    """Roles desde el codigo + confirmacion con commits Delta dentro de la corrida del flujo."""
    from ..inventario import roles
    inv = roles.inventariar(flujo, veredicto=veredicto)
    cf = veredicto.get("corrida_fabric") or {}
    if inv.get("correccion") and cf.get("startTimeUtc") and cf.get("endTimeUtc"):
        inv["confirmacion_delta"] = roles.confirmar_con_delta(inv["correccion"], cf["startTimeUtc"], cf["endTimeUtc"])
    return inv


def resumen(flujo, veredicto, inv=None):
    """Lo que necesita el semaforo: ejecucion, veredicto del validador y roles corregidos."""
    cf = veredicto.get("corrida_fabric") or {}
    r = {"flujo": flujo, "tipo": veredicto.get("tipo"), "se_ejecuto": veredicto.get("se_ejecuto"),
         "estado_corrida": cf.get("status"), "inicio_utc": cf.get("startTimeUtc"), "fin_utc": cf.get("endTimeUtc"),
         "duracion_s": veredicto.get("duracion_segundos"), "veredicto_validador": veredicto.get("veredicto"),
         "pasa_ejecucion": veredicto.get("pasa_ejecucion"), "pasa_validacion": veredicto.get("pasa_validacion"),
         "resultado_validador": veredicto.get("resultado"),
         "pruebas": {p.get("prueba"): p.get("nivel") for p in (veredicto.get("pruebas") or []) if isinstance(p, dict)},
         "bloqueantes": [{k: p.get(k) for k in ("prueba", "objeto", "esperado", "obtenido", "detalle")}
                         for p in (veredicto.get("pruebas") or []) if isinstance(p, dict) and p.get("nivel") == "BLOQUEANTE"],
         "advertencias": [{k: p.get(k) for k in ("prueba", "objeto", "detalle")}
                          for p in (veredicto.get("pruebas") or []) if isinstance(p, dict) and p.get("nivel") == "ADVERTENCIA"]}
    if inv and inv.get("estado") == "SIN_CODIGO":
        # pipeline con actividad Copy (ingesta): sus roles salen de source/sink y el validador los lee bien
        r.update(roles_desde="actividad_copy", roles_invertidos=False,
                 entradas=[x.get("ruta_completa") for x in veredicto.get("entradas") or []],
                 salidas=[x.get("ruta_completa") for x in veredicto.get("salidas") or []],
                 datos_salida=veredicto.get("datos_salida"))
    elif inv:
        r["roles_desde"] = "codigo_del_flujo+_delta_log"
        c = inv.get("correccion") or {}
        d = inv.get("confirmacion_delta") or {}
        r.update(roles_invertidos=c.get("invertido"), entradas=[x["ruta"] for x in c.get("entradas", [])],
                 salidas=[x["ruta"] for x in c.get("salidas", [])], roles_coherentes=d.get("roles_coherentes"),
                 salidas_sin_commit=d.get("salidas_sin_commit"), zip=inv.get("zip"), capa=inv.get("capa"))
    return r


# ----------------------------------------------------------------- dependencias reales
def lanzar_flujo(nombre, ws=None, esperar_fin=True, max_s=4 * 3600):
    """Ejecuta un flujo (DataPipeline) directo, p. ej. un productor que falta para una analitica."""
    cands = fabric.buscar_item(nombre, ("DataPipeline",), ws) if ws else (
        fabric.buscar_item(nombre, ("DataPipeline",), FAB["ws_ingesta"]) or
        fabric.buscar_item(nombre, ("DataPipeline",), FAB["ws_orquestacion"]))
    if not cands:
        raise RuntimeError(f"no se encontro el pipeline {nombre}")
    it = cands[0]
    t0 = time.time()
    run = fabric.lanzar(it["workspaceId"], it["id"], "Pipeline")
    r = {"flujo": nombre, "workspace": it["workspaceId"], "item": it["id"], "run": run}
    if esperar_fin:
        f = fabric.esperar(it["workspaceId"], it["id"], run, max_s=max_s, cada=30)
        r.update(estado=f.get("status"), inicio_utc=f.get("startTimeUtc"), fin_utc=f.get("endTimeUtc"),
                 error=f.get("failureReason"), segundos=round(time.time() - t0))
    return r
