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


def _equipo(grupo):
    return {"ingesta": "ingesta · CDS", "analitica": "analítica · DIA", "orquestador": "analítica · DIA"}.get(grupo, grupo)


def _fmt(n):
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else ("—" if n is None else str(n))


# ----------------------------------------------------------------- siguiente paso
def siguiente(trabajo):
    """Por flujo: etapa alcanzada y el proximo paso (comando + agente)."""
    out = []
    for f in (L.leer(trabajo, "lote.json") or {}).get("flujos", []):
        n, k0 = f["nombre_fabric"], [o["clave"] for o in f["objetos"]]
        etl = L.veredicto_etl(trabajo, f)
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
        reu = ((L.leer(trabajo, "v4/ciclos.json", {}) or {}).get(n, {}).get("reutilizado_de") or {}).get("objetos") or {}
        if any(not x.get("comprobado") for x in reu.values()):
            paso = ("comprobar que las tablas Fabric conservadas del ciclo anterior no cambiaron",
                    f"python -m pc ciclo --trabajo {trabajo} --flujo {n} --comprobar", "coordinador")
        rc = L.leer(trabajo, f"codigo/{n}/revision.json") or {}
        codigo = ("no aplica" if f["grupo"] == "orquestador" else rc.get("veredicto") or
                  ("en revisión" if L.leer(trabajo, f"codigo/{n}/fuente.json") else
                   f"pendiente: python -m pc codigo bajar --trabajo {trabajo} --flujo {n} --version N  [revisor-codigo]"))
        out.append({"flujo": n, "grupo": f["grupo"], "estado": est or "EN_CURSO", "paso": paso[0], "comando": paso[1], "agente": paso[2],
                    "codigo": codigo, "paralelos": _carriles(trabajo, f, paso, rc, sem, est),
                    "tablas": {c.get("objeto", {}).get("fabric") or k: c.get("estado") for k, c in zip(k0, cot)}})
    return out


def _carriles(trabajo, f, paso, rc, sem, est):
    """Lo que puede avanzar AL MISMO TIEMPO que el paso principal, porque no depende de la corrida de Fabric:
      codigo   la revision Stratio <-> Fabric (siempre, desde el primer momento)
      Stratio  Stratio es la referencia: su dato no cambia con la corrida de Fabric. Mientras Fabric ejecuta o se
               mide rapido, se descarga y se mide Stratio (descarga anticipada; si el semaforo sale ROJO la cache se
               conserva para el ciclo siguiente). Requiere VPN y cookie, y se avisa antes de descargar como siempre.
    Cada carril: {pista, paso, agente, comando, etapa}."""
    n = f["nombre_fabric"]
    out = []
    if est in ("APROBADO", "APROBADO_CON_JUSTIFICACION", "DEVUELTO") or f["grupo"] == "orquestador":
        return out
    if not rc.get("veredicto") and paso[2] != "revisor-codigo":
        out.append({"pista": "código", "agente": "revisor-codigo", "etapa": 0,
                    "paso": "revisar el código Stratio ↔ Fabric (pedir la versión de Rocket al usuario)",
                    "comando": f"python -m pc codigo bajar --trabajo {trabajo} --flujo {n} --version N"})
    principal_antes_de_descarga = any(x in paso[0] for x in ("ETL", "ejecutar", "niveles 0 y 1", "semáforo")) and \
        not (sem and sem.get("estado") == "ROJO")
    if principal_antes_de_descarga:
        from .cache import gestor
        try:
            man = gestor.manifiesto(trabajo)["entradas"]
        except Exception:
            man = {}
        con_s = [o for o in f["objetos"] if o.get("stratio")]
        sin_bajar = [o["clave"] for o in con_s if f"STRATIO/{o['clave']}" not in man]
        sin_medir = [o["clave"] for o in con_s if f"STRATIO/{o['clave']}" in man and not L.leer(trabajo, f"nivel2/STRATIO/{o['clave']}.json")]
        if sin_bajar:
            out.append({"pista": "Stratio", "agente": "gestor-descargas", "etapa": 4,
                        "paso": f"bajar Stratio por adelantado ({len(sin_bajar)} tabla(s)); no depende de la corrida de Fabric",
                        "comando": f"python -m pc estimar --trabajo {trabajo} --flujo {n} && "
                                   f"python -m pc descargar --trabajo {trabajo} --flujo {n} --anticipada"})
        elif sin_medir:
            out.append({"pista": "Stratio", "agente": "medidor-completo", "etapa": 5,
                        "paso": f"medir Stratio exacto por adelantado ({len(sin_medir)} tabla(s))",
                        "comando": f"python -m pc medir --trabajo {trabajo} --flujo {n} --lado STRATIO"})
    return out


def paralelo(trabajo):
    """Pasos que pueden correr YA, agrupados por agente: el coordinador lanza cada grupo en un mismo mensaje.
    Rocket comparte 8 hilos entre todos (el candado serializa objetos) y OneLake 8: varios flujos por agente
    no abusan de la plataforma, solo esperan su turno."""
    grupos = {}
    for x in siguiente(trabajo):
        if x["agente"] not in ("coordinador", "consolidador-revision"):
            grupos.setdefault(x["agente"], []).append(x["flujo"])
        for c in x.get("paralelos") or []:
            grupos.setdefault(f"{c['agente']} (carril {c['pista']})", []).append(x["flujo"])
    return grupos


def resumen(trabajo):
    """Cifras exactas por flujo y tabla, leidas de v4/*.json (nada se reescribe a mano)."""
    out = []
    ciclos = L.leer(trabajo, "v4/ciclos.json", {}) or {}
    for f in (L.leer(trabajo, "lote.json") or {}).get("flujos", []):
        n = f["nombre_fabric"]
        cf = _v4(trabajo, f"flujos/{n}.json")
        fila = {"flujo": n, "stratio": f.get("nombre_stratio"), "fl": f.get("fl"), "grupo": f["grupo"],
                "version": (ciclos.get(n) or {}).get("version", 1), "estado": (cf.get("encabezado") or {}).get("estado") or "EN_CURSO",
                "semaforo": (L.leer(trabajo, f"semaforo/{n}.json") or {}).get("estado"),
                "codigo": (L.leer(trabajo, f"codigo/{n}/revision.json") or {}).get("veredicto"), "tablas": []}
        for o in f["objetos"]:
            c = _v4(trabajo, f"cotejos/{o['clave']}.json")
            e, m = c.get("encabezado") or {}, (c.get("metricas") or {}).get("filas") or {}
            ctl = {}
            for fam in ((c.get("controles") or {}).get("resumen") or {}).values():
                for v in fam.values():
                    r = v.get("resultado") if isinstance(v, dict) else v
                    ctl[r] = ctl.get(r, 0) + 1
            dif = {}
            for j in c.get("justificaciones") or []:
                dif[j.get("decision")] = dif.get(j.get("decision"), 0) + 1
            fila["tablas"].append({"clave": o["clave"], "estado": e.get("estado"), "nivel": e.get("nivel_alcanzado"),
                                   "filas_stratio": m.get("stratio"), "filas_fabric": m.get("fabric"), "delta": m.get("delta"),
                                   "controles": ctl, "diferencias": dif, "de": f"v4/cotejos/{o['clave']}.json"})
        out.append(fila)
    return out


def imprimir_resumen(r):
    for f in r:
        print(f"{f['estado']:28s} v{f['version']} {f['grupo']:10s} {f['flujo']}  (Stratio {f['stratio'] or '?'} · {f['fl'] or 'FL ?'})"
              f" · semáforo {f['semaforo'] or '—'} · código {f['codigo'] or '—'}")
        for t in f["tablas"]:
            ctl = " ".join(f"{k}={v}" for k, v in sorted(t["controles"].items(), key=lambda kv: str(kv[0])))
            dif = " ".join(f"{k}={v}" for k, v in t["diferencias"].items()) or "sin diferencias"
            print(f"   {str(t['estado'] or 'SIN COTEJO'):26s} {t['clave']}: filas S {_fmt(t['filas_stratio'])} | F {_fmt(t['filas_fabric'])}"
                  f" (Δ {_fmt(t['delta'])}) · {ctl or 'sin controles'} · {dif}")


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


def _codigo(trabajo, flujo, columna=None):
    """Lo que dice la revision de codigo para una diferencia: veredicto, version de Stratio y reglas que nombran la columna."""
    r = L.leer(trabajo, f"codigo/{flujo}/revision.json")
    if not r:
        return {"veredicto": None, "aviso": "sin revision de codigo: no se sabe si la regla es igual en los dos lados"}
    cols = [c.strip().lower() for c in (columna or "").split(",") if c.strip()]
    rel = [x for x in r.get("reglas", []) if cols and any(c in " ".join(str(x.get(k) or "") for k in ("regla", "impacto", "stratio", "fabric")).lower() for c in cols)]
    return {"veredicto": r.get("veredicto"), "version_stratio": r.get("version_stratio"),
            "reglas_de_la_columna": [(x["id"], x["regla"], x["resultado"]) for x in rel]}


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
        rc = L.leer(trabajo, f"codigo/{n}/revision.json") or {}
        if rc.get("veredicto") == "CON_DIFERENCIAS" and not rc.get("decision_persona"):
            # una pregunta por regla que no es igual ni equivalente y sigue sin decidir; la clase dice que se propone
            for x in [g for g in rc.get("reglas", []) if g["resultado"] not in ("IGUAL", "EQUIVALENTE")
                      and g.get("decision") in (None, "PENDIENTE")]:
                if x.get("no_medido"):          # nada llega a una persona con algo sin medir: lo mide el agente
                    out.append({"tipo": "POR_MEDIR", "flujo": n, "titulo": f"{n} · {x['id']}: falta medir {x['no_medido']}",
                                "datos": {}, "opciones": []})
                    continue
                clase = x.get("clase") or "SIN_CLASE"
                base = f"python -m pc codigo comentar --trabajo {trabajo} --flujo {n} --id {x['id']}"
                eq = _equipo(f["grupo"])
                if clase == "LOGICA":
                    titulo = f"{n} · {x['id']}: lógica de negocio distinta"
                    opciones = [(f"REPORTAR a desarrollo ({eq}): el flujo queda DEVUELTO y el chat para {eq} se arma con esta regla",
                                 f"{base} --decision DEVOLVER --comentario \"…\""),
                                ("ANALIZAR MÁS: el cotejador mide el efecto en el dato (filas y columnas afectadas) y vuelve a preguntar",
                                 f"python -m pc diferenciar --trabajo {trabajo} --clave …"),
                                ("ACEPTAR: solo si una medición prueba que no cambia el resultado; queda en el reporte con esa medición",
                                 f"{base} --decision ACEPTADA --comentario \"…\" --verificado-qa \"…\"")]
                elif clase == "FUENTE":
                    titulo = f"{n} · {x['id']}: Fabric lee otra fuente"
                    opciones = [("ACEPTAR como fuente equivalente: queda aceptada en el reporte, con lo medido y la salvedad de lo no medido "
                                 "(p. ej. «la carga a bronze se valida en su flujo de ingesta»)", f"{base} --decision ACEPTADA --comentario \"…\" --verificado-qa \"…\""),
                                ("PEDIR LO QUE FALTA medir antes de decidir: el flujo sigue en revisión", f"{base} --decision PENDIENTE --comentario \"…\""),
                                (f"REPORTAR a desarrollo ({eq}): el flujo queda DEVUELTO y se arma el chat", f"{base} --decision DEVOLVER --comentario \"…\""),
                                ("PREGUNTAR A COMFANDI cuál es la fuente correcta: se arma el correo", f"{base} --decision PENDIENTE --comentario \"consulta a Comfandi\"")]
                else:
                    titulo = f"{n} · {x['id']}: regla distinta sin clasificar (el revisor debe decir por qué difiere)"
                    opciones = [("pedir al revisor de código la clase y el porqué", f"python -m pc codigo regla --trabajo {trabajo} --flujo {n} --id {x['id']} --clase … --porque \"…\" …")]
                out.append({"tipo": "CODIGO", "flujo": n, "nodo": f"R:{n}/{x['id']}", "titulo": titulo,
                            "datos": {"version_stratio": rc.get("version_stratio"), "zip_fabric": rc.get("zip_fabric"), "reglas": [x]},
                            "opciones": opciones})
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
            difs = co.get("diferencias") or co.get("justificaciones") or []     # formato 2: justificaciones
            res_ctl = {c: v for fam in ((co.get("controles") or {}).get("resumen") or {}).values() for c, v in fam.items()}
            filas = (co.get("metricas") or {}).get("filas") or (co.get("nivel_2") or {}).get("filas") or (co.get("nivel_1") or {}).get("filas")
            for d in difs:
                if d["decision"] != "PENDIENTE":
                    continue
                d = dict(d, descripcion=d.get("descripcion") or d.get("que_se_encontro"))
                ctl = (co.get("estado_controles") or {}).get(d["control"]) or res_ctl.get(d["control"]) or {}
                if "decide" in ctl and "rol" not in ctl:
                    ctl = dict(ctl, rol="decide" if ctl["decide"] else "informa")
                out.append({"tipo": "DIFERENCIA", "flujo": n, "clave": o["clave"], "id": d["id"], "nodo": f"X:{o['clave']}/{d['id']}",
                            "titulo": f"{n} · {o['clave']} · {d['id']} · {d['control']} · {d['tipo']}",
                            "datos": {"grupo": f["grupo"], "version": co["encabezado"]["version"],
                                      "control": {"codigo": d["control"], "rol_en_el_grupo": ctl.get("rol"), "resultado": ctl.get("resultado")},
                                      "descripcion": d["descripcion"], "columna": d.get("columna"), "filas_afectadas": d["filas_afectadas"],
                                      "ejemplos": d.get("ejemplos"), "causa_propuesta": d.get("causa"), "causa_medida": d.get("causa_medida"),
                                      "otras_diferencias": [(x["id"], x.get("tipo"), x["decision"]) for x in difs if x["id"] != d["id"]],
                                      "cifras": {"filas": filas, "dato": (co.get("nivel_2") or {}).get("dato")},
                                      "lectura": _lectura(trabajo, f, o), "ejecucion": _ejecucion(trabajo, f),
                                      "codigo": _codigo(trabajo, n, d.get("columna"))},
                            "opciones": [
                                ("JUSTIFICAR (exige causa medida)", f"python -m pc diferencia --trabajo {trabajo} --clave {o['clave']} --id {d['id']} --control {d['control']} --decision JUSTIFICADA --causa \"…\" --medida"),
                                ("PREGUNTAR A COMFANDI (es regla de negocio): se genera el correo", f"python -m pc diferencia --trabajo {trabajo} --clave {o['clave']} --id {d['id']} --control {d['control']} --decision A_VERIFICAR"),
                                (f"DEVOLVER a desarrollo ({_equipo(f['grupo'])}): se genera el mensaje de chat", f"python -m pc diferencia --trabajo {trabajo} --clave {o['clave']} --id {d['id']} --control {d['control']} --decision DEVUELTO"),
                                ("analizar más (pedir otra consulta al cotejador)", f"python -m pc comparar --trabajo {trabajo} --clave {o['clave']} --sql \"…\"")]})
            if (co.get("encabezado") or {}).get("sin_analizar"):
                out.append({"tipo": "SIN_ANALIZAR", "flujo": n, "clave": o["clave"],
                            "titulo": f"{n} · {o['clave']}: diferencias medibles sin analizar ({', '.join(co['encabezado']['sin_analizar'])})",
                            "datos": {"resumen": co["encabezado"].get("resumen"), "lectura": _lectura(trabajo, f, o)},
                            "opciones": [("el cotejador las analiza y las registra (no es decisión de una persona todavía)",
                                          f"python -m pc comparar --trabajo {trabajo} --clave {o['clave']} --solo STRATIO")]})
        if (cf.get("encabezado") or {}).get("estado") == "APROBADO_CON_VERIFICACION" and not cf.get("verificacion"):
            ver = [(o["clave"], d["id"], d.get("descripcion") or d.get("que_se_encontro")) for o in f["objetos"]
                   for d in (_v4(trabajo, f"cotejos/{o['clave']}.json").get("diferencias") or _v4(trabajo, f"cotejos/{o['clave']}.json").get("justificaciones") or [])
                   if d["decision"] == "A_VERIFICAR"]
            out.append({"tipo": "VERIFICACION", "flujo": n, "titulo": f"{n}: pendiente de verificar con QA o Comfandi",
                        "datos": {"a_verificar": ver, "ejecucion": _ejecucion(trabajo, f)},
                        "opciones": [("aprueba (QA o Comfandi)", f"python -m pc verificar --trabajo {trabajo} --flujo {n} --por QA|COMFANDI --decision APRUEBA --nota \"…\""),
                                     ("pide corregir → DEVUELTO", f"python -m pc verificar --trabajo {trabajo} --flujo {n} --por QA|COMFANDI --decision CORREGIR --nota \"…\"")]})
    return out


def _corto(x, n=200):
    t = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return t if len(t) <= n else t[:n - 1] + "…"


def tarjeta(x, trabajo=None, comandos=True):
    """Plantilla fija de una pregunta a la persona (<= ~12 lineas): que paso, cifras, como se midio, codigo,
    causa, un ejemplo, opciones con su comando y donde ver mas. No supone lecturas anteriores."""
    d = x.get("datos") if isinstance(x.get("datos"), dict) else {}
    out = [f"[{x['tipo']}] {x['titulo']}" + (f"  · nodo {x['nodo']}" if x.get("nodo") else "")]
    if x["tipo"] == "DIFERENCIA":
        c = d.get("control") or {}
        out.append(f"Qué pasó: {_corto(d.get('descripcion'), 260)}")
        f = (d.get("cifras") or {}).get("filas") or {}
        out.append(f"Cifras: filas Stratio {_fmt(f.get('stratio'))} | Fabric {_fmt(f.get('fabric'))} (Δ {_fmt(f.get('delta'))})"
                   f" · afectadas {_fmt(d.get('filas_afectadas'))}" + (f" · columna {d['columna']}" if d.get("columna") else "")
                   + f" · control {c.get('codigo')} {c.get('rol_en_el_grupo') or ''} en {d.get('grupo')}")
        for lado, l in (d.get("lectura") or {}).items():
            out.append(f"Leído {lado}: {l.get('ruta')} · {l.get('fuente')}" + (f" v{l['version_delta']}" if l.get("version_delta") is not None else "")
                       + (f" · commit {str(l['ultimo_commit'])[:16]}" if l.get("ultimo_commit") else "") + f" · medido {str(l.get('medido_utc'))[:16]}")
        cod = d.get("codigo") or {}
        out.append("Código: " + (f"{cod.get('veredicto')} (Stratio v{cod.get('version_stratio')})" if cod.get("veredicto") else cod.get("aviso", "—"))
                   + ("" if not cod.get("reglas_de_la_columna") else " · reglas de la columna: "
                      + "; ".join(f"{r[0]} {r[2]}" for r in cod["reglas_de_la_columna"])))
        out.append(f"Causa propuesta ({'medida' if d.get('causa_medida') else 'SIN medir'}): {_corto(d.get('causa_propuesta') or '—', 260)}")
        if d.get("ejemplos"):
            out.append(f"Ejemplo (1 de {len(d['ejemplos'])}): {_corto(d['ejemplos'][0], 220)}")
    elif x["tipo"] == "ROJO":
        for m in (d.get("motivos") or [])[:4]:
            out.append(f"Motivo: {_corto(m, 220)}")
        ej = d.get("ejecucion") or {}
        out.append(f"Ejecución: {ej.get('estado')} · inicio {ej.get('inicio_utc')} · run {ej.get('run_id')}")
    elif x["tipo"] == "CODIGO":
        out.append(f"Stratio v{d.get('version_stratio')} · zip Fabric {d.get('zip_fabric')}")
        for r in (d.get("reglas") or [])[:4]:
            out.append(f"Regla {r.get('id')} {r.get('resultado')} · {r.get('clase') or 'sin clase'}: {_corto(r.get('regla'), 160)}")
            out.append(f"Qué hace Stratio: {_corto(r.get('stratio'), 260)}")
            out.append(f"Qué hace Fabric: {_corto(r.get('fabric'), 260)}")
            if r.get("porque"):
                out.append(f"Por qué difiere: {_corto(r.get('porque'), 260)}")
            out.append(f"Medido: {_corto(r.get('medido') or 'nada todavía', 300)}")
            if r.get("no_medido"):
                out.append(f"No medido: {_corto(r.get('no_medido'), 260)}")
            if r.get("propuesta"):
                out.append(f"Propuesta: {r['propuesta']}")
    elif x["tipo"] == "TABLA_GRANDE":
        out.append(f"Estimado: {_fmt(d.get('filas'))} filas · {d.get('mb')} MB · {d.get('total')} vía {d.get('via')} (solo se estima el tiempo)")
    elif x["tipo"] == "VERIFICACION":
        for v in (d.get("a_verificar") or [])[:4]:
            out.append(f"A verificar: {v[0]} {v[1]} · {_corto(v[2], 180)}")
    else:
        out.append(_corto(d if d else x.get("datos"), 300))
    for j, (txt, cmd) in enumerate(x["opciones"], 1):
        out.append(f"  {j}) {txt}" + (f"  →  {cmd}" if cmd and comandos else ""))
    if x.get("nodo") and trabajo and comandos:
        out.append(f"Más: python -m pc grafo contexto --trabajo {trabajo} --nodo {x['nodo']}")
    return "\n".join(out)


def agrupar(p):
    """Las diferencias con la misma causa en el mismo flujo (p. ej. la copia Postgres y la de HDFS de una tabla) van en
    una sola pregunta: la decision se aplica a todas. Devuelve la lista con un campo `aplica_a` [(clave, id)]."""
    import re as _re
    out, grupos = [], {}
    for x in p:
        if x["tipo"] != "DIFERENCIA":
            out.append(x)
            continue
        d = x["datos"]
        causa = _re.sub(r"[\d.,%]+", "#", str(d.get("causa_propuesta") or d.get("descripcion") or ""))[:160]
        k = (x["flujo"], d["control"]["codigo"], d.get("columna"), causa)
        if k in grupos:
            grupos[k]["aplica_a"].append((x["clave"], x["id"]))
            continue
        x = dict(x, aplica_a=[(x["clave"], x["id"])])
        grupos[k] = x
        out.append(x)
    for x in out:
        if len(x.get("aplica_a") or []) > 1:
            x["titulo"] += f"  (+{len(x['aplica_a']) - 1} igual(es): " + ", ".join(f"{c} {i}" for c, i in x["aplica_a"][1:]) + ")"
    return out


def imprimir_pendientes(p, detalle=False, trabajo=None):
    if not p:
        print("Nada espera a una persona en este trabajo.")
        return
    agente = [x for x in p if x["tipo"] in ("SIN_ANALIZAR", "POR_MEDIR")]
    total = sum(1 for x in p if x["tipo"] not in ("SIN_ANALIZAR", "POR_MEDIR"))
    persona = agrupar([x for x in p if x["tipo"] not in ("SIN_ANALIZAR", "POR_MEDIR")])
    if len(persona) < total:
        print(f"{total} decisión(es) agrupadas en {len(persona)} pregunta(s): las de igual causa se deciden juntas.")
    print(f"{len(persona)} pregunta(s) para una persona · {len(agente)} tabla(s) con trabajo pendiente del cotejador")
    for i, x in enumerate(persona, 1):
        if detalle:
            print(f"\n### {i}. [{x['tipo']}] {x['titulo']}")
            print(json.dumps(x.get("datos"), ensure_ascii=False, indent=1, default=str))
            print("Opciones:")
            for j, (txt, cmd) in enumerate(x["opciones"], 1):
                print(f"  {j}) {txt}" + (f"\n     {cmd}" if cmd else ""))
        else:
            print(f"\n### {i}. " + tarjeta(x, trabajo))
    if agente:
        print("\nPara los agentes (no es decisión de una persona todavía: primero se mide):")
        for x in agente:
            print(f"  - {x['titulo']}")
