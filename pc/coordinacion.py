"""Lo que el coordinador necesita para dirigir: que sigue en cada flujo y que hay que preguntarle a una persona.

  python -m pc trabajo siguiente --trabajo T     donde quedo cada flujo y el proximo comando (sirve para retomar)
  python -m pc decision --trabajo T [--clave K]   expediente de decision de cada cosa pendiente de una persona

El coordinador PRESENTA el expediente de decision tal cual en el chat y ESPERA la respuesta: nunca decide solo.
Todo sale del estado en disco (trabajos/<T>/): si el equipo se apaga, se retoma desde aqui.
"""
import json
import os

from . import lote as L


def _v4(t, rel):
    return L.leer(t, f"v4/{rel}") or {}


def _fmt(n):
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else ("—" if n is None else str(n))


# ----------------------------------------------------------------- siguiente paso
def siguiente(trabajo):
    """Por flujo: etapa alcanzada y el proximo paso (comando + agente)."""
    out = []
    for f in (L.leer(trabajo, "lote.json") or {}).get("flujos", []):
        n, k0 = f["nombre_fabric"], [o["clave"] for o in f["objetos"]]
        etl = L.leer(trabajo, f"etl/veredictos/{n}.json")
        sem = L.leer(trabajo, f"semaforo/{n}.json")
        cf = _v4(trabajo, f"flujos/{n}.json")
        est = (cf.get("encabezado") or {}).get("estado")
        rap = all(L.leer(trabajo, f"rapido/{l}/{k}.json") for k in k0 for l in ("FABRIC", "STRATIO") if
                  next(o for o in f["objetos"] if o["clave"] == k).get(l.lower()))
        n2 = all(L.leer(trabajo, f"nivel2/{l}/{k}.json") for k in k0 for l in ("FABRIC", "STRATIO") if
                 next(o for o in f["objetos"] if o["clave"] == k).get(l.lower()))
        cot = [(_v4(trabajo, f"cotejos/{k}.json").get("encabezado") or {}) for k in k0]
        if est in ("APROBADO", "APROBADO_CON_JUSTIFICACION") or (est == "APROBADO_CON_VERIFICACION" and cf.get("verificacion", {}).get("decision") == "APRUEBA"):
            paso = ("listo para acta (expediente generado)", "python -m pc lote disponibles", "consolidador-revision")
        elif est == "DEVUELTO":
            paso = ("devuelto a desarrollo: al corregir, abrir ciclo nuevo", f"python -m pc ciclo --trabajo {trabajo} --flujo {n} --motivo \"…\"", "coordinador")
        elif f["grupo"] != "orquestador" and not etl:
            paso = ("ejecutar y validar con el ETL v10", f"python -m pc etl lanzar --trabajo {trabajo} --flujos {n} --esperar && python -m pc etl recoger --trabajo {trabajo}", "etl-validador")
        elif f["grupo"] == "orquestador":
            paso = ("aprobación por ejecución", f"python -m pc v4 construir --trabajo {trabajo}", "etl-validador") if etl else \
                   ("ejecutar el orquestador", f"python -m pc etl lanzar --trabajo {trabajo} --flujos {n} --esperar", "etl-validador")
        elif not rap and not sem:
            paso = ("niveles 0 y 1 de los dos lados (avisar cookie antes de Stratio)", f"python -m pc stratio cookie && python -m pc rapido --trabajo {trabajo} --flujo {n}", "medidor-rapido-fabric / -stratio")
        elif not sem:
            paso = ("semáforo", f"python -m pc semaforo --trabajo {trabajo} --flujo {n}", "semaforo")
        elif sem["estado"] == "ROJO":
            paso = ("ROJO: informar a desarrollo con los motivos", f"python -m pc decision --trabajo {trabajo}", "coordinador")
        elif not n2:
            paso = ("estimar (avisar el tiempo) → descargar → medir nivel 2", f"python -m pc estimar --trabajo {trabajo} --flujo {n} && python -m pc descargar --trabajo {trabajo} --flujo {n} && python -m pc medir --trabajo {trabajo} --flujo {n}", "gestor-descargas / medidor-completo")
        elif any(c.get("nivel_alcanzado", -1) < 2 for c in cot):
            paso = ("cotejar", f"python -m pc cotejar --trabajo {trabajo} --flujo {n}", "cotejador")
        elif any(c.get("sin_analizar") for c in cot):
            paso = ("el cotejador analiza las dos tablas y registra las diferencias", f"python -m pc comparar --trabajo {trabajo} --clave … · python -m pc diferencia …", "cotejador")
        else:
            paso = ("decisiones de una persona", f"python -m pc decision --trabajo {trabajo}", "coordinador")
        out.append({"flujo": n, "grupo": f["grupo"], "estado": est or "EN_CURSO", "paso": paso[0], "comando": paso[1], "agente": paso[2],
                    "tablas": {c.get("objeto", {}).get("fabric") or k: c.get("estado") for k, c in zip(k0, cot)}})
    return out


# ----------------------------------------------------------------- decisiones
def _lectura(trabajo, f, o):
    """Como se leyo cada lado (para que la persona sepa de donde salen las cifras)."""
    out = {}
    for lado in ("STRATIO", "FABRIC"):
        m = _v4(trabajo, f"mediciones/{lado}/{o['clave']}.json")
        if not m:
            continue
        e, n0, n1, n2 = m["encabezado"], m.get("nivel_0") or {}, m.get("nivel_1") or {}, m.get("nivel_2") or {}
        r = L.leer(trabajo, f"rapido/{lado}/{o['clave']}.json") or {}
        out[lado] = {"ruta": e.get("objeto"), "fuente": e.get("fuente"), "filas": n2.get("filas", n1.get("filas")),
                     "columnas": n0.get("num_columnas"), "version_delta": n0.get("version_delta"),
                     "ultimo_commit": (n0.get("ultimo_commit") or {}).get("utc"),
                     "codificacion": (r.get("objeto") or {}).get("codificacion"),
                     "descarga": n2.get("descarga"), "medido_utc": e.get("medido_utc")}
    return out


def _ejecucion(trabajo, f):
    cf = _v4(trabajo, f"flujos/{f['nombre_fabric']}.json")
    ej = cf.get("ejecucion") or {}
    return {"estado": ej.get("estado"), "inicio_utc": ej.get("inicio_utc"), "fin_utc": ej.get("fin_utc"),
            "duracion_s": ej.get("duracion_s"), "run_id": ej.get("run_id"),
            "validador": (ej.get("validador") or {}).get("resultado"),
            "roles": (cf.get("roles") or {}).get("desde"), "roles_invertidos": (cf.get("roles") or {}).get("invertidos_por_validador"),
            "salidas": [(x.get("tabla") or x.get("ruta"), x.get("filas"), x.get("commits_en_corrida")) for x in cf.get("salidas") or []]}


def pendientes(trabajo, clave=None):
    """Todo lo que espera a una persona, con los datos para decidir."""
    out = []
    from .acceso import rocket
    necesita_stratio = any(o.get("stratio") and not L.leer(trabajo, f"nivel2/STRATIO/{o['clave']}.json") for _f, o in L.objetos(trabajo))
    if necesita_stratio:
        try:
            ck = rocket.estado_cookie()
            if not ck.get("vigentes"):
                out.append({"tipo": "COOKIE", "titulo": "Cookie de Rocket vencida o por vencer",
                            "datos": ck, "opciones": [("pegar una cookie nueva (o hasta 3)", "se guarda en ~/Projects/.rocket_cookie[_2|_3], chmod 600")]})
        except Exception as e:
            out.append({"tipo": "COOKIE", "titulo": "No hay cookie de Rocket", "datos": str(e), "opciones": [("pegar una cookie", "")]})
    try:
        from .medir import estimar
        for r in estimar.estimar(trabajo):
            if r["grande"] and not L.leer(trabajo, f"nivel2/{r['lado']}/{r['clave']}.json"):
                out.append({"tipo": "TABLA_GRANDE", "titulo": f"{r['clave']} · {r['lado']}: {_fmt(r['filas'])} filas, {r['mb']} MB, ~{r['total']} vía {r['via']}",
                            "datos": r, "opciones": [("medir ahora", f"python -m pc descargar --trabajo {trabajo} --flujo {r['flujo']} --confirmar-grandes"),
                                                     ("dejar para después", "")]})
    except Exception:
        pass
    for f in (L.leer(trabajo, "lote.json") or {}).get("flujos", []):
        n = f["nombre_fabric"]
        sem = L.leer(trabajo, f"semaforo/{n}.json")
        if sem and sem["estado"] == "ROJO":
            out.append({"tipo": "ROJO", "titulo": f"{n}: vuelve a desarrollo", "flujo": n, "datos": {"motivos": sem["motivos_rojo"], "ejecucion": _ejecucion(trabajo, f)},
                        "opciones": [("confirmar la devolución a desarrollo", "(se informa el motivo con las cifras)"),
                                     ("revisar antes: forzar el nivel 2", f"python -m pc descargar --trabajo {trabajo} --flujo {n} --forzar")]})
        cf = _v4(trabajo, f"flujos/{n}.json")
        for o in f["objetos"]:
            if clave and o["clave"] != clave:
                continue
            co = _v4(trabajo, f"cotejos/{o['clave']}.json")
            if not co:
                continue
            for d in co.get("diferencias") or []:
                if d["decision"] != "PENDIENTE":
                    continue
                ctl = (co.get("estado_controles") or {}).get(d["control"]) or {}
                out.append({"tipo": "DIFERENCIA", "flujo": n, "clave": o["clave"], "id": d["id"],
                            "titulo": f"{n} · {o['clave']} · {d['id']} · {d['control']} · {d['tipo']}",
                            "datos": {"grupo": f["grupo"], "version": co["encabezado"]["version"],
                                      "control": {"codigo": d["control"], "rol_en_el_grupo": ctl.get("rol"), "resultado": ctl.get("resultado")},
                                      "descripcion": d["descripcion"], "columna": d.get("columna"), "filas_afectadas": d["filas_afectadas"],
                                      "ejemplos": d.get("ejemplos"), "causa_propuesta": d.get("causa"), "causa_medida": d.get("causa_medida"),
                                      "otras_diferencias": [(x["id"], x["tipo"], x["decision"]) for x in co["diferencias"] if x["id"] != d["id"]],
                                      "cifras": {"filas": (co.get("nivel_2") or {}).get("filas") or (co.get("nivel_1") or {}).get("filas"),
                                                 "dato": (co.get("nivel_2") or {}).get("dato")},
                                      "lectura": _lectura(trabajo, f, o), "ejecucion": _ejecucion(trabajo, f)},
                            "opciones": [
                                ("JUSTIFICAR (exige causa medida)", f"python -m pc diferencia --trabajo {trabajo} --clave {o['clave']} --id {d['id']} --control {d['control']} --decision JUSTIFICADA --causa \"…\" --medida"),
                                ("VERIFICAR con QA o Comfandi", f"python -m pc diferencia --trabajo {trabajo} --clave {o['clave']} --id {d['id']} --control {d['control']} --decision A_VERIFICAR"),
                                ("DEVOLVER a desarrollo", f"python -m pc diferencia --trabajo {trabajo} --clave {o['clave']} --id {d['id']} --control {d['control']} --decision DEVUELTO"),
                                ("analizar más (pedir otra consulta al cotejador)", f"python -m pc comparar --trabajo {trabajo} --clave {o['clave']} --sql \"…\"")]})
            if (co.get("encabezado") or {}).get("sin_analizar"):
                out.append({"tipo": "SIN_ANALIZAR", "flujo": n, "clave": o["clave"],
                            "titulo": f"{n} · {o['clave']}: diferencias medibles sin analizar ({', '.join(co['encabezado']['sin_analizar'])})",
                            "datos": {"resumen": co["encabezado"].get("resumen"), "lectura": _lectura(trabajo, f, o)},
                            "opciones": [("el cotejador las analiza y las registra (no es decisión de una persona todavía)",
                                          f"python -m pc comparar --trabajo {trabajo} --clave {o['clave']} --solo STRATIO")]})
        if (cf.get("encabezado") or {}).get("estado") == "APROBADO_CON_VERIFICACION" and not cf.get("verificacion"):
            ver = [(o["clave"], d["id"], d["descripcion"]) for o in f["objetos"]
                   for d in (_v4(trabajo, f"cotejos/{o['clave']}.json").get("diferencias") or []) if d["decision"] == "A_VERIFICAR"]
            out.append({"tipo": "VERIFICACION", "flujo": n, "titulo": f"{n}: pendiente de verificar con QA o Comfandi",
                        "datos": {"a_verificar": ver, "ejecucion": _ejecucion(trabajo, f)},
                        "opciones": [("aprueba (QA o Comfandi)", f"python -m pc verificar --trabajo {trabajo} --flujo {n} --por QA|COMFANDI --decision APRUEBA --nota \"…\""),
                                     ("pide corregir → DEVUELTO", f"python -m pc verificar --trabajo {trabajo} --flujo {n} --por QA|COMFANDI --decision CORREGIR --nota \"…\"")]})
    return out


def imprimir_pendientes(p):
    if not p:
        print("Nada espera a una persona en este trabajo.")
        return
    for i, x in enumerate(p, 1):
        print(f"\n### {i}. [{x['tipo']}] {x['titulo']}")
        print(json.dumps(x.get("datos"), ensure_ascii=False, indent=1, default=str))
        print("Opciones:")
        for j, (txt, cmd) in enumerate(x["opciones"], 1):
            print(f"  {j}) {txt}" + (f"\n     {cmd}" if cmd else ""))
