"""CLI de la pipeline QA v2. Cada subcomando es la accion de un agente sobre un lote.

  python -m pc lote crear --lote 12 --responsable "Nombre"            (coordinador)
  python -m pc lote flujo --lote 12 --json flujo.json                 (coordinador)
  python -m pc lote tablero --lote 12
  python -m pc roles --flujo 03-moves [--veredicto archivo.json]      (inventario-roles)
  python -m pc etl desplegar | lanzar --lote 12 [--flujos a,b] [--plan] | recoger --lote 12   (etl-validador)
  python -m pc rapido --lote 12 [--flujo F] [--lado FABRIC|STRATIO]   (medidor-rapido-*)
  python -m pc semaforo --lote 12                                     (semaforo)
  python -m pc descargar --lote 12 [--flujo F] [--lado ...]           (gestor-descargas)
  python -m pc medir --lote 12 [--flujo F] [--lado ...]               (medidor-completo)
  python -m pc cotejar --lote 12 [--flujo F]                          (cotejador)
  python -m pc publicar --lote 12 [--pruebas]                         (publicador-reportes)
  python -m pc cache espacio | limpiar --lote 12 [--ejecutar] [--forzar]   (gestor-descargas)
  python -m pc pg asegurar | sql "select ..."                         (postgres-fabric)
  python -m pc revision consolidar|estado|aprobar --lote 12 ...       (consolidador-revision)
"""
import argparse
import datetime
import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor

from . import lote as L
from .config import PAR


def _v4(lote):
    """Despues de cada etapa: los archivos reportes_v4 locales reflejan el estado del lote."""
    try:
        from .reportes import v4
        v4.construir(lote)
    except Exception as e:
        L.bitacora(lote, "publicador-reportes", "construir_v4", estado="ERROR", error=f"{type(e).__name__}: {str(e)[:200]}")


def _p(x):
    print(json.dumps(x, ensure_ascii=False, indent=1, default=str))


def _sel(a):
    for f, o in L.objetos(a.lote):
        if a.flujo and f["nombre_fabric"] != a.flujo:
            continue
        yield f, o


def _ventana(lote, flujo):
    r = (L.leer(lote, f"etl/veredictos/{flujo}.json") or {}).get("resumen") or {}
    if r.get("inicio_utc") and r.get("fin_utc"):
        return {"inicio_utc": r["inicio_utc"], "fin_utc": r["fin_utc"]}
    return None


def _where(o):
    v = o.get("ventana_fechas")
    if not v:
        return None
    c = '"' + v["columna"].replace('"', '""') + '"'
    partes = ([f"{c} >= '{v['desde']}'"] if v.get("desde") else []) + ([f"{c} <= '{v['hasta']}'"] if v.get("hasta") else [])
    return " and ".join(partes) or None


# ----------------------------------------------------------------- lote
def c_lote(a):
    if a.accion == "crear":
        _p(L.crear(a.lote, a.responsable, a.descripcion or "", a.fecha, pruebas=a.pruebas))
    elif a.accion == "siguiente":
        from . import coordinacion as K
        for x in K.siguiente(a.lote):
            print(f"{x['estado']:28s} {x['flujo']}\n   → {x['paso']}  [{x['agente']}]\n     {x['comando']}")
    elif a.accion == "bitacora":
        for e in L.leer_bitacora(a.lote):
            if a.estado and e["estado"] != a.estado:
                continue
            print(f"{e['evento']} {e['ts']} {e['estado']:8s} {e['agente']:22s} {e['accion']:20s} "
                  f"{e.get('flujo') or ''} {e.get('clave') or ''} {'' if e.get('duracion_s') is None else str(e['duracion_s']) + 's'}"
                  f"{' · ' + e['error'] if e.get('error') else ''}")
    elif a.accion == "flujo":
        spec = json.load(open(a.json, encoding="utf8"))
        for f in spec if isinstance(spec, list) else [spec]:
            L.agregar_flujo(a.lote, f["nombre_fabric"], f["grupo"], f.get("objetos"), f.get("nombre_stratio"),
                            f.get("fl"), f.get("orquestador"), f.get("dependencias"), f.get("notas"))
        print(f"lote {a.lote}: {len(L.leer(a.lote, 'lote.json')['flujos'])} flujo(s)")
    elif a.accion == "tablero":
        filas = L.tablero(a.lote)
        cols = ["flujo", "grupo", "clave", "etl", "cotejo_rapido", "semaforo", "nivel2_stratio", "nivel2_fabric", "cotejo_completo"]
        print(" | ".join(cols))
        for f in filas:
            print(" | ".join(str(f.get(c)) for c in cols))


def c_lote_final(a):
    from . import lote_final as LF
    if a.accion == "disponibles":
        for e in LF.disponibles():
            print(f"{e['estado']:28s} {e['grupo']:10s} v{e['version']}  {e['flujo']:50s} trabajo {e['trabajo']}")
    elif a.accion == "armar":
        d = LF.armar(a.lote, a.responsable, a.flujos.split(",") if a.flujos else None)
        print(f"lote {a.lote}: {len(d['expedientes'])} expediente(s) · responsable del acta {a.responsable}")


# ----------------------------------------------------------------- roles
def c_roles(a):
    from .inventario import roles
    v = json.load(open(a.veredicto)) if a.veredicto else None
    r = roles.inventariar(a.flujo, veredicto=v)
    if v and r.get("correccion") and (v.get("corrida_fabric") or {}).get("startTimeUtc"):
        cf = v["corrida_fabric"]
        r["confirmacion_delta"] = roles.confirmar_con_delta(r["correccion"], cf["startTimeUtc"], cf["endTimeUtc"])
    _p(r)


# ----------------------------------------------------------------- etl
def _etl_validar(lote, flujos, ejecutar, V):
    """Lanza el validador sobre `flujos`, espera y deja registrado el lanzamiento. Devuelve el estado del notebook."""
    lz = V.lanzar(flujos, ejecutar=ejecutar, corrida_qa=f"lote{lote}")
    hist = L.leer(lote, "etl/lanzamientos.json", []) or []
    hist.append(lz)
    L.guardar(lote, "etl/lanzamientos.json", hist)
    L.bitacora(lote, "etl-validador", "lanzar_validador", {"run": lz["run"], "flujos": flujos, "ejecutar": ejecutar}, estado="INICIO")
    r = V.seguir(lz, avisar=lambda e, s: print(f"{datetime.datetime.now():%H:%M:%S} validador {flujos} {e} {s}s", flush=True))
    lz.update(estado=r.get("status"), fin_utc=r.get("endTimeUtc"), fallo=r.get("failureReason"))
    L.guardar(lote, "etl/lanzamientos.json", hist)
    return r.get("status")


def _etl_ejecutar(a, V):
    """Plan de ejecucion del ETL. Nada corre en paralelo: cada paso espera al anterior y se detiene si uno falla.
      --validar x --dependencias a,b     ejecuta a, luego b (sin validarlos) y despues ejecuta y valida x
      --validar y,z,m --encadenados      y, z y m son dependencias entre si: ejecuta y valida cada uno, en ese orden
      --validar a,b --orquestador orq    ejecuta el orquestador UNA vez y valida a y b sin re-ejecutarlos"""
    validar = [x for x in (a.validar or "").split(",") if x]
    if not validar:
        raise SystemExit("--validar es obligatorio")
    modos = sum(bool(x) for x in (a.dependencias, a.encadenados, a.orquestador))
    if modos > 1:
        raise SystemExit("elige uno: --dependencias | --encadenados | --orquestador")
    faltan = [x for x in validar if not L.flujo(a.lote, x)]
    if faltan:
        raise SystemExit(f"no estan en el trabajo: {faltan}")
    plan = {"validar": validar, "modo": "orquestador" if a.orquestador else "encadenados" if a.encadenados else
            "dependencias" if a.dependencias else "directo", "pasos": []}

    def paso(tipo, nombre, **extra):
        plan["pasos"].append(dict({"tipo": tipo, "flujo": nombre, "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}, **extra))
        L.guardar(a.lote, "etl/plan_ejecucion.json", plan)

    def correr(nombre, tolerar=False):
        r = V.lanzar_flujo(nombre)
        L.bitacora(a.lote, "etl-validador", "ejecutar_productor", {"flujo": nombre, "run": r.get("run"), "estado": r.get("estado"),
                   "inicio_utc": r.get("inicio_utc"), "fin_utc": r.get("fin_utc"), "para": validar},
                   estado="OK" if r.get("estado") == "Completed" else "ERROR", flujo=validar[0])
        paso("ejecutar_sin_validar", nombre, run=r.get("run"), estado=r.get("estado"), inicio_utc=r.get("inicio_utc"), fin_utc=r.get("fin_utc"))
        print(f"{nombre}: {r.get('estado')}", flush=True)
        if r.get("estado") != "Completed" and not tolerar:
            raise SystemExit(f"se detiene el plan: {nombre} termino {r.get('estado')} · {str(r.get('error'))[:300]}")

    if a.orquestador:
        # el orquestador ejecuta los flujos; no se re-ejecutan. Si falla, igual se valida: la comprobacion
        # «la falla del orquestador es posterior a este flujo» decide flujo por flujo (pc etl evidencia).
        correr(a.orquestador, tolerar=True)
        est = _etl_validar(a.lote, validar, False, V)
        paso("validar_sin_ejecutar", ",".join(validar), estado=est, orquestador=a.orquestador)
    elif a.encadenados:
        for x in validar:                                   # uno por uno, en el orden dado
            est = _etl_validar(a.lote, [x], True, V)
            paso("ejecutar_y_validar", x, estado=est)
            if est != "Completed":
                raise SystemExit(f"se detiene el plan: el validador de {x} termino {est}")
    else:
        for d in [x for x in (a.dependencias or "").split(",") if x and x not in validar]:
            correr(d)
        for x in validar:
            est = _etl_validar(a.lote, [x], True, V)
            paso("ejecutar_y_validar", x, estado=est)
            if est != "Completed":
                raise SystemExit(f"se detiene el plan: el validador de {x} termino {est}")
    d_ = L.leer(a.lote, "lote.json")
    for f_ in d_["flujos"]:
        if f_["nombre_fabric"] in validar:
            if a.orquestador:
                f_["orquestador"] = a.orquestador
            if a.dependencias:
                f_["dependencias"] = [x for x in a.dependencias.split(",") if x]
    L.guardar(a.lote, "lote.json", d_)
    print("plan terminado; sigue: pc etl recoger y pc etl evidencia", flush=True)


def c_etl(a):
    from .etl import validador as V
    if a.accion == "desplegar":
        _p(V.desplegar())
        return
    if a.accion == "ejecutar":
        _etl_ejecutar(a, V)
        a.accion = "recoger"
        c_etl(a)
        a.accion, a.flujos = "evidencia", a.validar
        c_etl(a)
        return
    if a.accion == "evidencia":
        from .etl import evidencia as E
        d = L.leer(a.lote, "lote.json")
        for n in (a.flujos.split(",") if a.flujos else [f["nombre_fabric"] for f in d["flujos"]]):
            try:
                e = E.medir(a.lote, n)
                v = e.get("corrida_validada") or {}
                print(f"{n}: corrida {v.get('inicio_utc')} {v.get('estado')} · {len(e['entradas'])} entrada(s) · {len(e['salidas'])} salida(s)", flush=True)
            except Exception as x:
                L.bitacora(a.lote, "etl-validador", "medir_evidencia", estado="ERROR", flujo=n, error=f"{type(x).__name__}: {str(x)[:200]}")
                print(f"{n}: ERROR {type(x).__name__}: {str(x)[:200]}", flush=True)
        _v4(a.lote)
        return
    if a.accion == "lanzar":
        d = L.leer(a.lote, "lote.json")
        fl = a.flujos.split(",") if a.flujos else [f["nombre_fabric"] for f in d["flujos"]]
        lz = V.lanzar(fl, ejecutar=not a.plan, corrida_qa=f"lote{a.lote}")
        hist = L.leer(a.lote, "etl/lanzamientos.json", []) or []
        hist.append(lz)
        L.guardar(a.lote, "etl/lanzamientos.json", hist)
        L.bitacora(a.lote, "etl-validador", "lanzar_validador", {"run": lz["run"], "flujos": len(lz["flujos"]), "ejecutar": lz["ejecutar"]}, estado="INICIO")
        _p(lz)
        if a.esperar:
            r = V.seguir(lz, avisar=lambda e, s: print(f"{datetime.datetime.now():%H:%M:%S} {e} {s}s", flush=True))
            lz.update(estado=r.get("status"), fin_utc=r.get("endTimeUtc"), fallo=r.get("failureReason"))
            L.guardar(a.lote, "etl/lanzamientos.json", hist)
            print("notebook:", r.get("status"))
        return
    if a.accion == "recoger":
        hist = L.leer(a.lote, "etl/lanzamientos.json", []) or []
        if not hist:
            raise SystemExit("no hay lanzamientos en este lote")
        ultimo = {}
        for lz in hist:                       # el lanzamiento mas reciente de cada flujo
            for fl_ in lz["flujos"]:
                ultimo[fl_] = lz
        vs = {}
        for fl_, lz in ultimo.items():
            vs.update({k_: (v_, lz) for k_, v_ in V.veredictos([fl_], desde_utc=lz["lanzado_utc"]).items()})
        for f, (x, lz) in vs.items():
            if not x:
                print(f"{f}: sin veredicto nuevo")
                continue
            inv = V.corregir(f, x["veredicto"])
            doc = {"ruta_onelake": x["ruta"], "resumen": V.resumen(f, x["veredicto"], inv), "inventario": inv,
                   "lanzamiento": lz["run"], "veredicto": x["veredicto"]}
            # filas y columnas de entradas/salidas: se miden UNA vez aqui y quedan en disco (no se recalculan al armar)
            from .reportes import v4 as rep_v4
            corr = inv.get("correccion") or {}
            doc["io_medido"] = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                "entradas": rep_v4._filas_delta([e["ruta"] for e in corr.get("entradas") or []]),
                                "salidas": rep_v4._filas_delta([e["ruta"] for e in corr.get("salidas") or []])}
            fl = L.flujo(a.lote, f) or {}
            if fl.get("grupo") == "analitica":
                import re as _re
                rf = (x["veredicto"].get("flujo_resuelto") or {})
                nombres = [f, rf.get("nombre") if isinstance(rf, dict) else rf, _re.sub(r"^\d+[a-z]?[-_]", "", f).replace("-", "_")]
                for nm in [n for n in nombres if n]:
                    doc["revision_analitica"] = V.revision_analitica(nm, lz["lanzado_utc"])
                    if doc["revision_analitica"]:
                        break
            p = L.guardar(a.lote, f"etl/veredictos/{f}.json", doc)
            r = doc["resumen"]
            L.bitacora(a.lote, "etl-validador", "recoger_veredicto", {"resultado": r.get("resultado_validador"),
                       "corrida": r.get("estado_corrida"), "roles_invertidos": r.get("roles_invertidos")},
                       estado="OK" if r.get("estado_corrida") == "Completed" else "AVISO", flujo=f, salidas=[p])
            if r.get("roles_invertidos"):
                L.bitacora(a.lote, "inventario-roles", "roles_corregidos", {"salidas": r.get("salidas")}, estado="AVISO", flujo=f)
            print(f"{f}: {r.get('estado_corrida')} · {r.get('resultado_validador')} · roles {r.get('roles_desde')}"
                  + (" · INVERTIDOS (corregidos)" if r.get("roles_invertidos") else ""))
        _v4(a.lote)


# ----------------------------------------------------------------- rapido
def _ev(lote, agente, accion, f, o, t0, res, nivel=None, salida=None):
    import time as _t
    ok = not str(res).startswith(("ERROR", "REQUIERE"))
    L.bitacora(lote, agente, accion, None if ok else {"resultado": res}, estado="OK" if ok else ("AVISO" if str(res).startswith("REQUIERE") else "ERROR"),
               nivel=nivel, flujo=f["nombre_fabric"], clave=o["clave"], duracion_s=_t.time() - t0,
               salidas=[salida] if salida and ok else None, error=None if ok else str(res)[:300])


def _rapido_obj(lote, f, o, lado):
    import time as _t
    from .rapido import nivel01, postgres, stratio
    k, out = o["clave"], {}
    t0 = _t.time()
    if lado in (None, "FABRIC") and o.get("fabric"):
        src, ven = o["fabric"], _ventana(lote, f["nombre_fabric"])
        try:
            if src["tipo"] == "delta":
                r = nivel01.medir_delta(src["ruta"], ventana=ven)
            elif src["tipo"] == "files":
                r = nivel01.medir_files(src["ruta"], ventana=ven)
            elif src["tipo"] == "pg":
                r = postgres.medir(src["ruta"], "FABRIC", where=_where(o), ventana=ven)
            else:
                raise ValueError(src["tipo"])
            r["objeto"].update(clave=k, flujo=f["nombre_fabric"], grupo=f["grupo"])
            L.guardar(lote, f"rapido/FABRIC/{k}.json", r)
            out["FABRIC"] = "OK"
        except Exception as e:
            out["FABRIC"] = f"ERROR {type(e).__name__}: {str(e)[:160]}"
        _ev(lote, "medidor-rapido-fabric", "medir_rapido", f, o, t0, out["FABRIC"], 1, f"rapido/FABRIC/{k}.json")
        t0 = _t.time()
    if lado in (None, "STRATIO") and o.get("stratio"):
        src = o["stratio"]
        try:
            if src["tipo"] == "pg":
                r = stratio.medir_pg(src["ruta"], where=_where(o))
            elif src["tipo"] == "hdfs":
                r = stratio.medir_hdfs(src["ruta"], desde=src.get("desde"))
                if r.get("estado") == "REQUIERE_DESCARGA":
                    out["STRATIO"] = "REQUIERE_DESCARGA"
                    L.guardar(lote, f"rapido/STRATIO/{k}.pendiente.json", r)
                    _ev(lote, "medidor-rapido-stratio", "medir_rapido", f, o, t0, "REQUIERE_DESCARGA: " + r.get("motivo", ""), 1)
                    return out
            elif src["tipo"] == "sftp":
                r = stratio.medir_sftp_parquet(src["ruta"], src.get("patron"))
                if r.get("estado") == "REQUIERE_DESCARGA":
                    out["STRATIO"] = "REQUIERE_DESCARGA"
                    L.guardar(lote, f"rapido/STRATIO/{k}.pendiente.json", r)
                    _ev(lote, "medidor-rapido-stratio", "medir_rapido", f, o, t0, "REQUIERE_DESCARGA: " + r.get("motivo", ""), 1)
                    return out
            else:
                raise ValueError(src["tipo"])
            r["objeto"].update(clave=k, flujo=f["nombre_fabric"], grupo=f["grupo"])
            L.guardar(lote, f"rapido/STRATIO/{k}.json", r)
            out["STRATIO"] = "OK"
        except Exception as e:
            out["STRATIO"] = f"ERROR {type(e).__name__}: {str(e)[:160]}"
        _ev(lote, "medidor-rapido-stratio", "medir_rapido", f, o, t0, out["STRATIO"], 1, f"rapido/STRATIO/{k}.json")
    S, F = L.leer(lote, f"rapido/STRATIO/{k}.json"), L.leer(lote, f"rapido/FABRIC/{k}.json")
    if S and F:
        from .cotejo import rapido as CR
        c = CR.cotejar(S, F, f["grupo"])
        c.update(clave=k, flujo=f["nombre_fabric"])
        L.guardar(lote, f"cotejo_rapido/{k}.json", c)
        out["cotejo_rapido"] = c["resultado_rapido"] + (f" {c['no_cumple']}" if c["no_cumple"] else "")
        L.bitacora(lote, "medidor-rapido", "cotejo_rapido", {"resultado": c["resultado_rapido"], "no_cumple": c["no_cumple"]},
                   estado="OK" if not c["no_cumple"] else "AVISO", nivel=1, flujo=f["nombre_fabric"], clave=k,
                   salidas=[f"cotejo_rapido/{k}.json"])
    return out


def c_rapido(a):
    objs = [(f, o) for f, o in _sel(a) if f["grupo"] != "orquestador"]
    # Fabric y Postgres en paralelo; Rocket internamente serializa (candado)
    with ThreadPoolExecutor(max(2, PAR["medicion_local_objetos"] * 2)) as ex:
        res = list(ex.map(lambda fo: (fo[1]["clave"], _rapido_obj(a.lote, fo[0], fo[1], a.lado)), objs))
    for k, r in res:
        print(k, r)
    _v4(a.lote)


# ----------------------------------------------------------------- semaforo
def c_semaforo(a):
    from .compuerta import semaforo
    for f in L.leer(a.lote, "lote.json")["flujos"]:
        if a.flujo and f["nombre_fabric"] != a.flujo:
            continue
        etl = (L.leer(a.lote, f"etl/veredictos/{f['nombre_fabric']}.json") or {}).get("resumen")
        ev = L.leer(a.lote, f"etl/evidencia/{f['nombre_fabric']}.json") or {}
        cv = ev.get("corrida_validada") or {}
        if etl is not None and not etl.get("estado_corrida") and cv.get("estado"):
            # validado sin ejecutar (lo corrio un orquestador): la corrida es la medida en Fabric (pc etl evidencia)
            etl = dict(etl, estado_corrida=cv["estado"], inicio_utc=cv.get("inicio_utc"), fin_utc=cv.get("fin_utc"),
                       corrida_desde="evidencia")
        cot = {o["clave"]: L.leer(a.lote, f"cotejo_rapido/{o['clave']}.json") for o in f["objetos"]}
        cot = {k: v for k, v in cot.items() if v}
        s = semaforo.evaluar(f["nombre_fabric"], f["grupo"], etl, cot, claves_esperadas=[o["clave"] for o in f["objetos"]])
        L.guardar(a.lote, f"semaforo/{f['nombre_fabric']}.json", s)
        L.bitacora(a.lote, "semaforo", "evaluar", {"estado": s["estado"], "motivos_rojo": s["motivos_rojo"], "avisos": s["avisos"]},
                   estado="OK" if s["estado"] == "VERDE" else "AVISO", flujo=f["nombre_fabric"])
        print(f"{s['estado']:8s} {f['nombre_fabric']} · {s['siguiente']}")
        for m in s["motivos_rojo"]:
            print("         -", m)
    _v4(a.lote)


# ----------------------------------------------------------------- nivel 2
def _puede_nivel2(lote, f, forzar):
    s = L.leer(lote, f"semaforo/{f['nombre_fabric']}.json")
    if forzar:
        return True
    return bool(s) and s["estado"] in ("VERDE", "AMARILLO")


def _grandes(a):
    from .medir import estimar
    return {(r["clave"], r["lado"]) for r in estimar.estimar(a.lote, a.flujo) if r["grande"]}


def _rapido_desde_descarga(lote, f, o, carpeta, archivos, meta):
    """Rocket no acepta Range: el nivel 0/1 de Stratio (HDFS, SFTP CSV) sale de la descarga, y con el el cotejo rapido."""
    import time as _t
    from .rapido import stratio
    from .cotejo import rapido as CR
    k, t0 = o["clave"], _t.time()
    try:
        if meta.get("lector") == "csv":
            r = stratio.medir_local_csv(archivos, (o.get("stratio") or {}).get("ruta"), (o.get("stratio") or {}).get("csv"))
        else:
            r = stratio.medir_local(carpeta, (o.get("stratio") or {}).get("ruta"))
        r["objeto"].update(clave=k, flujo=f["nombre_fabric"], grupo=f["grupo"])
        L.guardar(lote, f"rapido/STRATIO/{k}.json", r)
        p = os.path.join(L.dir_lote(lote), "rapido", "STRATIO", f"{k}.pendiente.json")
        if os.path.exists(p):
            os.remove(p)
        _ev(lote, "medidor-rapido-stratio", "medir_rapido_desde_descarga", f, o, t0, "OK", 1, f"rapido/STRATIO/{k}.json")
        F = L.leer(lote, f"rapido/FABRIC/{k}.json")
        if F:
            c = CR.cotejar(r, F, f["grupo"])
            c.update(clave=k, flujo=f["nombre_fabric"])
            L.guardar(lote, f"cotejo_rapido/{k}.json", c)
            print(f"   {k}: nivel 0/1 Stratio desde la descarga · cotejo rápido {c['resultado_rapido']} {c['no_cumple'] or ''}")
    except Exception as e:
        _ev(lote, "medidor-rapido-stratio", "medir_rapido_desde_descarga", f, o, t0, f"ERROR {type(e).__name__}: {e}", 1)


def c_descargar(a):
    from .medir import completo as C
    hechos = []
    grandes = set() if a.confirmar_grandes else _grandes(a)
    for f, o in _sel(a):
        if f["grupo"] == "orquestador" or not _puede_nivel2(a.lote, f, a.forzar):
            continue
        k = o["clave"]
        for lado in ("FABRIC", "STRATIO"):
            if a.lado and lado != a.lado:
                continue
            src = o.get(lado.lower())
            if not src:
                continue
            if (k, lado) in grandes:
                hechos.append((k, lado, "OMITIDA: tabla grande; ver `python -m pc estimar` y repetir con --confirmar-grandes"))
                continue
            import time as _t
            t0 = _t.time()
            try:
                if lado == "FABRIC":
                    fn = {"delta": lambda: C.bajar_delta_fabric(a.lote, k, src["ruta"]),
                          "files": lambda: C.bajar_files_fabric(a.lote, k, src["ruta"]),
                          "pg": lambda: C.bajar_pg_fabric(a.lote, k, src["ruta"], _where(o))}[src["tipo"]]
                else:
                    fn = {"hdfs": lambda: C.bajar_hdfs_stratio(a.lote, k, src["ruta"], src.get("desde"), particion=src.get("particion")),
                          "pg": lambda: C.bajar_pg_stratio(a.lote, k, src["ruta"], _where(o)),
                          "sftp": lambda: C.bajar_sftp_stratio(a.lote, k, src["ruta"], src.get("patron"))}[src["tipo"]]
                L.bitacora(a.lote, "gestor-descargas", "descargar", {"lado": lado, "origen": src.get("ruta")}, estado="INICIO",
                           nivel=2, flujo=f["nombre_fabric"], clave=k)
                d, arch, m = fn()
                hechos.append((k, lado, f"{len(arch)} archivo(s)"))
                if lado == "STRATIO" and not L.leer(a.lote, f"rapido/STRATIO/{k}.json"):
                    _rapido_desde_descarga(a.lote, f, o, d, arch, m)
            except Exception as e:
                hechos.append((k, lado, f"ERROR {type(e).__name__}: {str(e)[:160]}"))
            _ev(a.lote, "gestor-descargas", "descargar", f, o, t0, hechos[-1][2], 2)
    for h in hechos:
        print(*h)


def c_medir(a):
    from .cache import gestor
    from .medir import completo as C
    man = gestor.manifiesto(a.lote)["entradas"]
    tareas = []
    for f, o in _sel(a):
        for lado in ("FABRIC", "STRATIO"):
            e = man.get(f"{lado}/{o['clave']}")
            if (a.lado and lado != a.lado) or not e:
                continue
            tareas.append((f, o, lado, e))

    def una(t):
        import time as _t
        f, o, lado, e = t
        t0 = _t.time()
        L.bitacora(a.lote, "medidor-completo", "medir_nivel2", {"lado": lado}, estado="INICIO", nivel=2, flujo=f["nombre_fabric"], clave=o["clave"])
        r = _una(t)
        _ev(a.lote, "medidor-completo", "medir_nivel2", f, o, t0, r[2], 2, f"nivel2/{lado}/{o['clave']}.json")
        return r

    def _una(t):
        f, o, lado, e = t
        try:
            filtro = _where(o) if (o.get(lado.lower()) or {}).get("tipo") != "pg" else None
            out, rep = C.medir(a.lote, o["clave"], lado, e["carpeta"], e["meta"], flujo=f["nombre_fabric"], grupo=f["grupo"],
                               filtro=filtro, excluir=o.get("excluir_columnas", ()), csv=(o.get(lado.lower()) or {}).get("csv"),
                               cast_varchar=(o.get(lado.lower()) or {}).get("cast_varchar"))
            return o["clave"], lado, f"{rep['conteos']['row_count']:,} filas · hash {str(rep['hash'].get('hash_dataset'))[:12]}"
        except Exception as ex:
            traceback.print_exc()
            return o["clave"], lado, f"ERROR {type(ex).__name__}: {str(ex)[:160]}"
    with ThreadPoolExecutor(PAR["medicion_local_objetos"]) as ex:
        for r in ex.map(una, tareas):
            print(*r)
    _v4(a.lote)


def c_cotejar(a):
    from .cache import gestor
    from .cotejo import completo as CC
    idx = L.leer(a.lote, "cotejos/indice.json", {}) or {}
    for f, o in _sel(a):
        k = o["clave"]
        rs = os.path.join(L.dir_lote(a.lote), "nivel2", "STRATIO", f"{k}.json")
        rf = os.path.join(L.dir_lote(a.lote), "nivel2", "FABRIC", f"{k}.json")
        if not (os.path.exists(rs) and os.path.exists(rf)):
            continue
        r = CC.cotejar({"clave": k, "grupo": f["grupo"], "flujo": f["nombre_fabric"], "flujo_stratio": f.get("nombre_stratio"),
                        "justificaciones": o.get("justificaciones", {})}, rs, rf, L.dir_lote(a.lote),
                       datetime.date.today().isoformat(), a.lote)
        doc = json.load(open(r["archivo"]))
        idx[k] = {"archivo": r["archivo"], "resultado": r["resultado"], "dato": doc["veredictos"]["dato"],
                  "filas": doc["veredictos"]["filas"], "justificacion": doc.get("justificacion")}
        for lado in ("STRATIO", "FABRIC"):
            try:
                gestor.marcar(a.lote, lado, k, "COTEJADO")
            except KeyError:
                pass
        print(k, r["veredicto"], r["resumen"])
        L.guardar(a.lote, "cotejos/indice.json", idx)
        L.bitacora(a.lote, "cotejador", "cotejar", {"resultado": r["resultado"], "dato": idx[k]["dato"]},
                   estado="OK" if r["resultado"].startswith("APROBADO") else "AVISO", nivel=2, flujo=f["nombre_fabric"], clave=k,
                   salidas=[os.path.relpath(r["archivo"], L.dir_lote(a.lote))])
    L.guardar(a.lote, "cotejos/indice.json", idx)
    _v4(a.lote)


def c_cache(a):
    from .cache import gestor
    if a.accion == "espacio":
        _p(gestor.espacio())
    elif a.accion == "ver":
        _p(gestor.manifiesto(a.lote))
    elif a.accion == "limpiar":
        r = gestor.limpiar(a.lote, forzar=a.forzar, simular=not a.ejecutar)
        if a.ejecutar:
            L.bitacora(a.lote, "gestor-descargas", "limpiar", r)
        _p(r)


def c_pg(a):
    from .pgfabric import pipeline
    if a.accion == "asegurar":
        _p(pipeline.asegurar())
    elif a.accion == "sql":
        filas, r = pipeline.consultar(a.consulta, timeout=a.timeout)
        _p({"corrida": r, "filas": filas[:200], "total_filas": len(filas)})


def c_revision(a):
    from .compuerta import revision as R
    if a.accion == "consolidar":
        r = R.consolidar(a.lote)
        from . import lote_final as LF
        print(f"resumen {r['huella']} · {os.path.join(LF.dir_lote(a.lote), 'revision', 'RESUMEN_LOTE.md')}")
    elif a.accion == "estado":
        _p(R.estado(a.lote))
    elif a.accion == "aprobar":
        _p(R.registrar(a.lote, a.compuerta, a.decision, a.persona, a.notas or ""))


def c_acta(a):
    from . import acta
    ruta, A = acta.generar(a.lote, a.version)
    print(f"acta: {ruta}\n{len(A['flujos'])} flujo(s) · {A['anexo_enlaces']} enlaces verificados con HEAD · firmantes: "
          + ", ".join(x["nombre"] for x in A["firmantes"]))


def c_mejora(a):
    from . import mejoras as M
    if a.accion == "registrar":
        _p(M.registrar(a.que, a.por_que, [x for x in (a.archivos or "").split(",") if x]))
        print("→ Avísale al usuario: hay una mejora para compartir con el equipo (commit + push).")
    elif a.accion == "compartida":
        M.compartida(a.id, a.commit)
        print(f"{a.id} marcada como COMPARTIDA")
    else:
        p = M.pendientes()
        for x in p["sin_compartir"]:
            print(f"SIN COMPARTIR  {x['id']} · {x['que']}  ({', '.join(x['archivos'])})")
        for c in p["cambios_sin_registrar"]:
            print(f"SIN REGISTRAR  {c}  (cambió en el proceso y no hay mejora anotada)")
        if not p["sin_compartir"] and not p["cambios_sin_registrar"]:
            print("No hay mejoras pendientes de compartir.")


def c_decision(a):
    from . import coordinacion as K
    K.imprimir_pendientes(K.pendientes(a.lote, a.clave))


def c_v4(a):
    from .reportes import v4
    if a.accion == "construir":
        _p(v4.construir(a.lote))
    elif a.accion == "incompletos":
        v4.construir(a.lote)
        falta = v4.incompletos(a.lote)
        for k, v in falta.items():
            print(f"{k}:\n  - " + "\n  - ".join(v))
        print("COMPLETO: se puede publicar" if not falta else f"INCOMPLETO: {len(falta)} archivo(s); no se publica hasta completarlos")
    elif a.accion == "publicar":
        v4.construir(a.lote)
        falta = v4.incompletos(a.lote)
        if falta:
            for k, v in falta.items():
                print(f"{k}:\n  - " + "\n  - ".join(v))
            raise SystemExit(f"NO SE PUBLICA: {len(falta)} archivo(s) con informacion incompleta (pc v4 incompletos --trabajo {a.lote})")
        for h in v4.publicar(a.lote, bucket=not a.sin_bucket):
            print(f"{'OK ' if h['head_ok'] else 'MAL'} {h['tipo']:16s} v{h.get('version')} {h['ruta']}"
                  + ("  + bucket" if h.get("bucket") else "") + (f"  bucket ERROR {h['bucket_error']}" if h.get("bucket_error") else ""))
        L.bitacora(a.lote, "publicador-reportes", "publicar_v4", None)


def c_diferencia(a):
    from .reportes import v4
    d = v4.registrar_diferencia(a.lote, a.clave, a.control, a.tipo, a.descripcion, a.filas_afectadas,
                                json.loads(a.ejemplos) if a.ejemplos else [], a.decision, a.causa, a.medida, a.columna, a.id)
    v4.construir(a.lote)
    _p(d)


def c_ciclo(a):
    from .reportes import v4
    print(f"{a.flujo}: nuevo ciclo v{v4.nuevo_ciclo(a.lote, a.flujo, a.motivo)} · se vuelve a empezar en el nivel 0")


def c_verificar(a):
    from .reportes import v4
    _p(v4.verificar(a.lote, a.flujo, a.por, a.decision, a.nota))
    v4.construir(a.lote)


def c_comparar(a):
    from .cotejo import analisis as A
    con, info = A.abrir(a.lote, a.clave)
    if a.sql:
        cols, filas = A.consultar(con, a.sql, a.limite)
        A.imprimir({"columnas": cols, "filas": filas})
    elif a.solo:
        A.imprimir(A.solo_en(con, a.solo, a.limite))
    elif a.columna:
        A.imprimir(A.columna(con, a.columna, a.limite))
    else:
        A.imprimir(info)


def c_estimar(a):
    from .medir import estimar
    filas = estimar.estimar(a.lote, a.flujo)
    for r in filas:
        print(f"{'GRANDE ' if r['grande'] else '       '}{r['flujo'][:28]:28s} {r['clave'][:40]:40s} {r['lado']:7s} "
              f"{str(r['filas'] or '?'):>12s} filas {r['mb']:>9.1f} MB  {r['total']:>8s}  vía {r['via']}"
              + ("  (sin tamaño: medir rápido primero)" if r["sin_tamano"] else ""))
    g = [r for r in filas if r["grande"]]
    if g:
        print(f"\n{len(g)} tabla(s) grande(s): el nivel 2 pide --confirmar-grandes (preguntar al usuario con la estimación).")


def c_stratio(a):
    from .acceso import rocket, stratio_pg
    if a.accion == "cookie":
        _p(rocket.estado_cookie())
    elif a.accion == "vpn":
        print("VPN ok" if stratio_pg.vpn_ok() else "SIN VPN: no se llega a la Postgres de Stratio")


def main(argv=None):
    p = argparse.ArgumentParser(prog="pc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("trabajo", help="trabajo de validacion (1 o varios flujos)"); x.add_argument("accion", choices=["crear", "flujo", "tablero", "bitacora", "siguiente"])
    x.add_argument("--trabajo", dest="lote", required=True)
    x.add_argument("--pruebas", action="store_true"); x.add_argument("--estado")
    x.add_argument("--responsable"); x.add_argument("--descripcion"); x.add_argument("--fecha"); x.add_argument("--json"); x.set_defaults(fn=c_lote)
    x = s.add_parser("lote", help="LOTE FINAL: se arma con los expedientes aprobados")
    x.add_argument("accion", choices=["disponibles", "armar"]); x.add_argument("--lote"); x.add_argument("--responsable")
    x.add_argument("--flujos"); x.set_defaults(fn=c_lote_final)
    x = s.add_parser("roles"); x.add_argument("--flujo", required=True); x.add_argument("--veredicto"); x.set_defaults(fn=c_roles)
    x = s.add_parser("etl"); x.add_argument("accion", choices=["desplegar", "lanzar", "recoger", "ejecutar", "evidencia"]); x.add_argument("--trabajo", "--lote", dest="lote")
    x.add_argument("--validar"); x.add_argument("--dependencias"); x.add_argument("--encadenados", action="store_true"); x.add_argument("--orquestador")
    x.add_argument("--flujos"); x.add_argument("--plan", action="store_true", help="EJECUTAR=False: solo prevuelo")
    x.add_argument("--esperar", action="store_true"); x.set_defaults(fn=c_etl)
    for nombre, fn in (("rapido", c_rapido), ("descargar", c_descargar), ("medir", c_medir), ("cotejar", c_cotejar),
                       ("semaforo", c_semaforo)):
        x = s.add_parser(nombre); x.add_argument("--trabajo", "--lote", dest="lote", required=True); x.add_argument("--flujo")
        x.add_argument("--lado", choices=["FABRIC", "STRATIO"]); x.add_argument("--forzar", action="store_true")
        x.add_argument("--pruebas", action="store_true"); x.add_argument("--confirmar-grandes", action="store_true"); x.set_defaults(fn=fn)
    x = s.add_parser("cache"); x.add_argument("accion", choices=["espacio", "ver", "limpiar"]); x.add_argument("--trabajo", "--lote", dest="lote")
    x.add_argument("--ejecutar", action="store_true"); x.add_argument("--forzar", action="store_true"); x.set_defaults(fn=c_cache)
    x = s.add_parser("pg"); x.add_argument("accion", choices=["asegurar", "sql"]); x.add_argument("consulta", nargs="?")
    x.add_argument("--timeout"); x.set_defaults(fn=c_pg)
    x = s.add_parser("revision"); x.add_argument("accion", choices=["consolidar", "estado", "aprobar"]); x.add_argument("--trabajo", "--lote", dest="lote", required=True)
    x.add_argument("--compuerta", choices=["revision_qa", "revision_comfandi", "aprobacion"])
    x.add_argument("--decision", choices=["APROBADO", "CON_OBSERVACIONES", "RECHAZADO"]); x.add_argument("--persona"); x.add_argument("--notas")
    x.set_defaults(fn=c_revision)
    x = s.add_parser("v4"); x.add_argument("accion", choices=["construir", "publicar", "incompletos"])
    x.add_argument("--trabajo", "--lote", dest="lote", required=True); x.add_argument("--sin-bucket", action="store_true"); x.set_defaults(fn=c_v4)
    x = s.add_parser("diferencia", help="el cotejador registra una diferencia exacta (max 5 ejemplos)")
    x.add_argument("--trabajo", "--lote", dest="lote", required=True); x.add_argument("--clave", required=True)
    x.add_argument("--control", required=True); x.add_argument("--tipo"); x.add_argument("--descripcion")
    x.add_argument("--filas-afectadas", type=int); x.add_argument("--ejemplos", help="JSON: lista de hasta 5")
    x.add_argument("--decision", default="PENDIENTE", choices=["PENDIENTE", "INFORMATIVA", "JUSTIFICADA", "A_VERIFICAR", "DEVUELTO"])
    x.add_argument("--causa"); x.add_argument("--medida", action="store_true"); x.add_argument("--columna"); x.add_argument("--id")
    x.set_defaults(fn=c_diferencia)
    x = s.add_parser("ciclo", help="correccion de desarrollo: abre vN+1 del flujo desde el nivel 0")
    x.add_argument("--trabajo", "--lote", dest="lote", required=True); x.add_argument("--flujo", required=True); x.add_argument("--motivo", required=True)
    x.set_defaults(fn=c_ciclo)
    x = s.add_parser("verificar", help="cierra una APROBACION CON VERIFICACION")
    x.add_argument("--trabajo", "--lote", dest="lote", required=True); x.add_argument("--flujo", required=True)
    x.add_argument("--por", required=True, choices=["QA", "COMFANDI"]); x.add_argument("--decision", required=True, choices=["APRUEBA", "CORREGIR"])
    x.add_argument("--nota", required=True); x.set_defaults(fn=c_verificar)
    x = s.add_parser("comparar", help="mesa de analisis: S (Stratio) y F (Fabric) en DuckDB")
    x.add_argument("--trabajo", "--lote", dest="lote", required=True); x.add_argument("--clave", required=True)
    x.add_argument("--sql"); x.add_argument("--solo", choices=["STRATIO", "FABRIC"]); x.add_argument("--columna")
    x.add_argument("--limite", type=int, default=5); x.set_defaults(fn=c_comparar)
    x = s.add_parser("estimar", help="tiempo estimado del nivel 2 por tabla y lado")
    x.add_argument("--trabajo", "--lote", dest="lote", required=True); x.add_argument("--flujo"); x.set_defaults(fn=c_estimar)
    x = s.add_parser("acta", help="genera el acta del lote (solo con 3/3 compuertas y por el responsable)")
    x.add_argument("accion", choices=["generar"]); x.add_argument("--lote", required=True); x.add_argument("--version", default="1.0")
    x.set_defaults(fn=c_acta)
    x = s.add_parser("mejora", help="registro de mejoras del proceso para compartir con el equipo")
    x.add_argument("accion", choices=["registrar", "pendientes", "compartida"]); x.add_argument("--que"); x.add_argument("--por-que")
    x.add_argument("--archivos"); x.add_argument("--id"); x.add_argument("--commit"); x.set_defaults(fn=c_mejora)
    x = s.add_parser("decision", help="expediente de decision de todo lo que espera a una persona")
    x.add_argument("--trabajo", "--lote", dest="lote", required=True); x.add_argument("--clave"); x.set_defaults(fn=c_decision)
    x = s.add_parser("stratio"); x.add_argument("accion", choices=["cookie", "vpn"]); x.set_defaults(fn=c_stratio)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
