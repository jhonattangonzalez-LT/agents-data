"""Cierre de un coordinador: dos markdown que salen del grafo y de los JSON del trabajo (nada a mano).

  python -m pc cierre --trabajo T            -> trabajos/<T>/cierre/EXITOSOS_<T>.md y PENDIENTES_<T>.md
  python -m pc trabajo retomar --trabajo T   -> lee las respuestas de desarrollo pegadas en PENDIENTES y propone el ciclo

EXITOSOS (APROBADO, APROBADO_CON_JUSTIFICACION y CON_VERIFICACION tras APRUEBA): resumen de flujos, resumen de
justificaciones, archivos publicados (cotejo de flujo; por tabla cotejo, metricas Stratio y metricas Fabric) con la
URL de navegador del portal de Fabric. Solo se cita lo publicado con HEAD OK en la version del cierre.
PENDIENTES: por flujo no cerrado, estado y motivo con cifras, ficha de devolucion de 7 puntos, subgrafo, archivos
locales que no se borran y un bloque para pegar la respuesta de desarrollo.

Formato `cierre-v1` (front-matter YAML): lo consume el agente de actas para juntar varios cierres.
"""
import datetime
import hashlib
import json
import os
import re
import subprocess

from . import grafo as G
from . import lote as L
from .config import RAIZ

FORMATO = "cierre-v1"
_LISTOS = ("APROBADO", "APROBADO_CON_JUSTIFICACION")


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _f(n):
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else ("—" if n is None else str(n))


def _du(p):
    if not os.path.exists(p):
        return None
    try:
        return int(subprocess.run(["du", "-sb", p], capture_output=True, text=True, timeout=60).stdout.split()[0])
    except Exception:
        return None


def _mb(b):
    return "—" if b is None else f"{b / 1e6:,.1f} MB".replace(",", ".")


def _listo(cf):
    e = (cf.get("encabezado") or {}).get("estado")
    if e == "APROBADO_CON_VERIFICACION":
        return (cf.get("verificacion") or {}).get("decision") == "APRUEBA"
    return e in _LISTOS


def _front(tipo, trabajo, flujos, cuerpo, completo=None):
    h = hashlib.sha256(cuerpo.encode()).hexdigest()
    lin = ["---", f"formato: {FORMATO}", f"tipo: {tipo}", f"trabajo: \"{trabajo}\"", f"generado_utc: \"{_ahora()}\"",
           *([f"completo: {'true' if completo else 'false'}"] if completo is not None else []),
           f"generado_por: \"{L.usuario()}\"", f"grafo: \"trabajos/{trabajo}/grafo/grafo.json\"", f"huella_sha256: \"{h}\"",
           "flujos:"]
    for f in flujos:
        lin.append(f"  - {{flujo: \"{f['flujo']}\", stratio: \"{f.get('stratio') or ''}\", fl: \"{f.get('fl') or ''}\", "
                   f"grupo: {f['grupo']}, version: {f['version']}, estado: {f['estado']}, nodo: \"F:{f['flujo']}\"}}")
    return "\n".join(lin + ["---", ""]) + cuerpo


def _publicados(trabajo):
    """Todo lo registrado como publicado (v4/publicado*.json)."""
    import glob
    out = {}
    for p in sorted(glob.glob(os.path.join(L.dir_lote(trabajo), "v4", "publicado*.json"))):
        try:
            doc = json.load(open(p, encoding="utf8"))
        except ValueError:
            continue
        for x in (doc.get("archivos") if isinstance(doc, dict) else doc) or []:
            if isinstance(x, dict) and x.get("ruta"):
                out[x["ruta"]] = x
    return out


def _head(pub, rutas, comprobar=True):
    """HEAD 200 de cada ruta citada: lo registrado con head_ok se vuelve a comprobar en OneLake (8 hilos)."""
    if not comprobar:
        return pub
    from concurrent.futures import ThreadPoolExecutor
    from .acceso import onelake as ol

    def uno(r):
        try:
            return r, ol.head(r) is not None
        except Exception:
            return r, None
    with ThreadPoolExecutor(8) as ex:
        for r, ok in ex.map(uno, sorted(set(rutas))):
            x = pub.setdefault(r, {"ruta": r})
            x["head_ok"] = bool(ok)
            x["head_comprobado_utc"] = _ahora() if ok is not None else None
    return pub


def _enlace(pub, ruta, etiqueta):
    """Solo se cita lo publicado y con HEAD OK; lo demas queda marcado y no se enlaza."""
    x = pub.get(ruta)
    if x and x.get("head_ok"):
        return f"[{etiqueta}]({G.url_navegador(ruta)})"
    if x and x.get("head_ok") is False and x.get("head_comprobado_utc"):
        return f"{etiqueta} — **HEAD 404: no está publicado, no se cita**"
    return f"{etiqueta} — **sin comprobar HEAD: no se cita**"


def _equipo(grupo):
    return {"ingesta": "ingesta (CDS)", "analitica": "analítica (DIA)", "orquestador": "orquestación (DIA)"}.get(grupo, grupo)


def _rutas_citadas(trabajo, exitosos, pr):
    from .reportes import v4
    out = []
    for x in exitosos:
        out.append(v4.ruta_ol("cotejo_flujo", x["flujo"], x["version"], pruebas=pr))
        for o in x["f"]["objetos"]:
            out.append(v4.ruta_ol("cotejo", o["clave"], x["version"], pruebas=pr))
            for lado in ("STRATIO", "FABRIC"):
                if o.get(lado.lower()):
                    out.append(v4.ruta_ol("medicion", o["clave"], x["version"], lado, pr))
    return out


def _quien(d):
    if isinstance(d, dict):
        return f"{d.get('quien') or ''} ({d.get('usuario') or '?'}, {str(d.get('utc') or '')[:10]})".strip()
    return str(d)


def generar(trabajo, comprobar_head=True):
    from .reportes import v4
    from .reportes.formato2 import salvedad_stratio
    d = L.leer(trabajo, "lote.json")
    g = G.construir(trabajo)
    pub = _publicados(trabajo)
    pr = bool(d.get("pruebas"))
    ciclos = L.leer(trabajo, "v4/ciclos.json", {}) or {}
    exitosos, pendientes = [], []
    for f in d["flujos"]:
        n = f["nombre_fabric"]
        cf = L.leer(trabajo, f"v4/flujos/{n}.json") or {}
        fila = {"flujo": n, "stratio": f.get("nombre_stratio"), "fl": f.get("fl"), "grupo": f["grupo"],
                "version": (cf.get("encabezado") or {}).get("version") or (ciclos.get(n) or {}).get("version", 1),
                "estado": (cf.get("encabezado") or {}).get("estado") or "EN_CURSO", "f": f, "cf": cf}
        (exitosos if cf and _listo(cf) else pendientes).append(fila)
    pub = _head(pub, _rutas_citadas(trabajo, exitosos, pr), comprobar_head)
    dirc = os.path.join(L.dir_lote(trabajo), "cierre")
    os.makedirs(dirc, exist_ok=True)

    # ------------------------------------------------------------- EXITOSOS
    # formato fijo (pedido por QA): 1 resumen de ejecuciones · 2 resumen de justificaciones y aprobaciones · 3 por flujo:
    # ejecución, cotejos de tablas y métricas. Solo enlaces de los resultados (cotejo de flujo, cotejo y métricas S|F por
    # tabla). Lo que falte no se rellena: se lista en salidas/cierre_faltantes.json y se pregunta al QA.
    falt = []

    def falta(x, que):
        falt.append({"flujo": x["flujo"], "falta": que})

    out = [f"# Flujos exitosos · trabajo {trabajo}", "",
           f"{len(exitosos)} de {len(d['flujos'])} flujo(s) listos para acta · "
           f"{sum(1 for x in exitosos if x['estado'] == 'APROBADO')} APROBADO · "
           f"{sum(1 for x in exitosos if x['estado'] == 'APROBADO_CON_JUSTIFICACION')} con justificación · "
           f"{sum(1 for x in exitosos if x['estado'] == 'APROBADO_CON_VERIFICACION')} con verificación (APRUEBA)", "",
           "## 1. Resumen de ejecuciones", "",
           "| # | Flujo Fabric | Flujo Stratio | FL | Grupo | Versión | Corrida | Inicio (UTC) | Duración | Lanzada por | Dependencias | Tablas |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, x in enumerate(exitosos, 1):
        cv = (x["cf"].get("ejecucion") or {}).get("corrida_validada") or {}
        fd = ((x["cf"].get("analitica") or x["cf"].get("ingesta") or {}).get("flujos_dependientes") or {})
        dep = fd.get("resumen") if fd.get("estado") == "MEDIDO" else None
        if not x["stratio"]:
            falta(x, "nombre del flujo en Stratio")
        if not x["fl"]:
            falta(x, "código FL")
        if not (cv.get("estado") and cv.get("inicio_utc") and cv.get("duracion_s") is not None):
            falta(x, "corrida validada (estado, inicio y duración) en el cotejo de flujo")
        if x["grupo"] != "orquestador" and not dep:
            falta(x, "dependencias medidas (`python -m pc dependencias`)")
        x["_cv"], x["_dep"] = cv, dep
        tabs = len(x["f"]["objetos"]) or (f"en `{x['f']['tablas_en']}`" if x["f"].get("tablas_en") else "por ejecución")
        dur = cv.get("duracion_s")
        out.append(f"| {i} | `{x['flujo']}` | {x['stratio'] or '**FALTA**'} | {x['fl'] or '**FALTA**'} | {x['grupo']} | v{x['version']} | "
                   f"{cv.get('estado') or '**FALTA**'} · `{str(cv.get('run_id') or '')[:8]}` | {str(cv.get('inicio_utc') or '')[:16].replace('T', ' ') or '**FALTA**'} | "
                   f"{(f'{dur // 60} min {dur % 60:02d} s' if dur is not None else '**FALTA**')} | {cv.get('lanzada_por') or '—'} | "
                   f"{dep or ('por ejecución' if x['grupo'] == 'orquestador' else '**FALTA**')} | {tabs} |")
    # aclaraciones del alcance escritas en el lote (flujo agregado al plan, un FL que en Fabric son dos flujos, ...)
    acl = [x for x in exitosos if x["f"].get("nota_cierre")]
    if acl:
        out += ["", "### Aclaraciones del alcance", ""]
        out += [f"- **{x['fl'] or 'sin FL'} · `{x['flujo']}`**: {x['f']['nota_cierre']}" for x in acl]

    out += ["", "## 2. Resumen de justificaciones y aprobaciones", "", "### 2.1 Aprobaciones", "",
            "| Flujo | Estado | Por qué se aprueba | Decidió |", "|---|---|---|---|"]
    for x in exitosos:
        js_ = [j for o in x["f"]["objetos"] for j in (L.leer(trabajo, f"v4/cotejos/{o['clave']}.json") or {}).get("justificaciones") or []
               if j.get("decision") in ("JUSTIFICADA", "INFORMATIVA")]
        quien = {_quien(j["decidido_por"]) for j in js_ if j.get("decidido_por")}
        comp_ = [c for c in x["cf"].get("comprobaciones") or [] if c.get("resultado") == "JUSTIFICADO"]
        quien |= {_quien((c.get("decision") or {})["decidido_por"]) for c in comp_ if (c.get("decision") or {}).get("decidido_por")}
        cod_ = [r_ for r_ in (L.leer(trabajo, f"codigo/{x['flujo']}/revision.json") or {}).get("reglas") or []
                if r_.get("decision") == "ACEPTADA" and r_.get("salvedad")]
        for r_ in cod_:          # quien acepto la regla: el ultimo comentario ACEPTADA
            c_ = next((c for c in reversed(r_.get("comentarios") or []) if c.get("decision") == "ACEPTADA"), None)
            if c_ and c_.get("por"):
                quien.add(f"QA ({c_['por']}, {str(c_.get('utc') or '')[:10]})")
        quien = sorted(quien)
        v_ = x["cf"].get("verificacion") or {}
        if x["estado"] == "APROBADO":
            por = "todos los controles que deciden cumplen, sin diferencias"
        elif x["estado"] == "APROBADO_CON_VERIFICACION":
            por = f"verificación {v_.get('por') or ''} {v_.get('decision') or ''}: {v_.get('nota') or ''}".strip()
        else:
            por = "; ".join(t for t in (f"{len(js_)} diferencia(s) de tablas con causa medida" if js_ else "",
                                         f"{len(comp_)} comprobación(es) del flujo justificadas" if comp_ else "",
                                         f"{len(cod_)} regla(s) de código aceptadas con salvedad" if cod_ else "",
                                         f"tablas cotejadas en `{x['f']['tablas_en']}`" if x["f"].get("tablas_en") else "") if t) + " (ver 2.2)"
        if x["estado"] == "APROBADO_CON_JUSTIFICACION" and not quien:
            falta(x, "quién decidió las justificaciones")
        out.append(f"| `{x['flujo']}` | {x['estado']} | {por} | {', '.join(quien) or (v_.get('persona') or 'QA (sin diferencias)')} |")
    out += ["", "### 2.2 Justificaciones", ""]
    hay = False
    for x in exitosos:
        for o in x["f"]["objetos"]:
            co = L.leer(trabajo, f"v4/cotejos/{o['clave']}.json") or {}
            js = [j for j in co.get("justificaciones") or [] if j.get("decision") in ("JUSTIFICADA", "INFORMATIVA")]
            for j in js:
                hay = True
                ej = (j.get("ejemplos") or [])[:1]
                if not (j.get("causa") or j.get("que_se_encontro")):
                    falta(x, f"{o['clave']} {j['id']}: causa de la justificación")
                if not ej:
                    falta(x, f"{o['clave']} {j['id']}: ejemplo Stratio | Fabric de la diferencia")
                out.append(f"- **{x['flujo']} · {o['clave']} · {j['id']} · {j.get('control')}**"
                           + (f" · `{j['columna']}`" if j.get("columna") else "")
                           + f" · {_f(j.get('filas_afectadas'))} fila(s) · {j['decision']}"
                           + (f" · decidió {_quien(j['decidido_por'])}" if j.get("decidido_por") else ""))
                out.append(f"  - Causa{' medida' if j.get('causa_medida') else ''}: {j.get('causa') or j.get('que_se_encontro')}")
                if ej:
                    out.append(f"  - Ejemplo: `{json.dumps(ej[0], ensure_ascii=False, default=str)[:220]}`")
        # lo que se acepto fuera de las tablas: flujo sin tablas propias, comprobaciones del flujo y reglas de codigo con salvedad
        if x["f"].get("tablas_en"):
            hay = True
            out.append(f"- **{x['flujo']} · sin tablas propias** · se cotejan en `{x['f']['tablas_en']}` · APROBADO_CON_JUSTIFICACION")
            out.append(f"  - Motivo: {x['f'].get('sin_tablas_motivo') or '—'}")
        for c in x["cf"].get("comprobaciones") or []:
            if c.get("resultado") == "JUSTIFICADO":
                hay = True
                d_ = c.get("decision") or {}
                out.append(f"- **{x['flujo']} · comprobación del flujo** · {c['comprobacion']} · JUSTIFICADA"
                           + (f" · decidió {_quien(d_['decidido_por'])}" if d_.get("decidido_por") else ""))
                out.append(f"  - Causa{' medida' if d_.get('causa_medida') else ''}: {d_.get('causa')}")
        for r_ in (L.leer(trabajo, f"codigo/{x['flujo']}/revision.json") or {}).get("reglas") or []:
            s_ = r_.get("salvedad")
            if r_.get("decision") == "ACEPTADA" and s_:
                hay = True
                out.append(f"- **{x['flujo']} · código {r_['id']}** · {r_.get('regla')} · {r_.get('resultado')} · ACEPTADA con salvedad")
                out.append(f"  - Salvedad: {s_.get('motivo') if isinstance(s_, dict) else s_}")
    if not hay:
        out.append("Sin justificaciones: todos los flujos exitosos cumplen sin diferencias.")

    out += ["", "## 3. Flujos: ejecución, cotejos de tablas y métricas", "",
            "Enlaces al portal de Fabric (lakehouse transversal de QA), solo lo publicado con HEAD OK en la versión del cierre.", ""]

    def enl(ruta, etq, x):
        t = _enlace(pub, ruta, etq)
        if not t.startswith("["):
            falta(x, f"enlace {etq} (no publicado o sin HEAD 200)")
        return t
    for x in exitosos:
        v_, nf, cv = x["version"], x["flujo"], x["_cv"]
        dur = cv.get("duracion_s")
        out += [f"### {nf} · v{x['version']} · {x['estado']}", "", "**Ejecución**", "",
                f"- Corrida `{cv.get('run_id') or '—'}` · {cv.get('estado') or '—'} · inicio {str(cv.get('inicio_utc') or '—')[:19].replace('T', ' ')} UTC · "
                f"{(f'{dur // 60} min {dur % 60:02d} s' if dur is not None else 'duración no registrada')} · lanzada por {cv.get('lanzada_por') or '—'}",
                f"- Dependencias: {x['_dep'] or ('por ejecución' if x['grupo'] == 'orquestador' else 'no medidas')}",
                f"- Cotejo del flujo: {enl(v4.ruta_ol('cotejo_flujo', nf, v_, pruebas=pr), f'cotejo_flujo_{nf}_v{v_}', x)}", ""]
        objs = x["f"]["objetos"]
        if objs:
            out += ["**Cotejos de tablas**", "", "| # | Tabla | Filas Stratio | Filas Fabric | Resultado | Cotejo |", "|---|---|---|---|---|---|"]
            for i, o in enumerate(objs, 1):
                k = o["clave"]
                co = L.leer(trabajo, f"v4/cotejos/{k}.json") or {}
                m = (co.get("metricas") or {}).get("filas") or {}
                csl = (co.get("encabezado") or {}).get("como_se_leyo") or {}
                fs_ = m.get("stratio") if m.get("stratio") is not None else (csl.get("stratio") or {}).get("filas")
                ff_ = m.get("fabric") if m.get("fabric") is not None else (csl.get("fabric") or {}).get("filas")
                out.append(f"| {i} | `{k}` | {_f(fs_) if fs_ is not None else 'sin lado Stratio'} | {_f(ff_)} | {(co.get('encabezado') or {}).get('estado') or '**FALTA**'} | "
                           f"{enl(v4.ruta_ol('cotejo', k, v_, pruebas=pr), f'cotejo_{k}_v{v_}', x)} |")
            out += ["", "**Métricas**", "", "| # | Tabla | Métricas Stratio | Métricas Fabric |", "|---|---|---|---|"]
            for i, o in enumerate(objs, 1):
                k = o["clave"]
                ms_ = (enl(v4.ruta_ol("medicion", k, v_, "STRATIO", pr), f"medicion_stratio_{k}_v{v_}", x) if o.get("stratio")
                       else "sin lado Stratio" + (f" (salvedad: {salvedad_stratio(o)['motivo']})" if salvedad_stratio(o) else ""))
                mf_ = enl(v4.ruta_ol("medicion", k, v_, "FABRIC", pr), f"medicion_fabric_{k}_v{v_}", x) if o.get("fabric") else "**FALTA**"
                out.append(f"| {i} | `{k}` | {ms_} | {mf_} |")
            out.append("")
    cuerpo = "\n".join(out) + "\n"
    p_ex = os.path.join(dirc, f"EXITOSOS_{trabajo}.md")
    open(p_ex, "w", encoding="utf8").write(_front("EXITOSOS", trabajo, exitosos, cuerpo, completo=not falt))
    L.guardar(trabajo, "salidas/cierre_faltantes.json", {"generado_utc": _ahora(), "completo": not falt, "faltantes": falt})

    # ------------------------------------------------------------- PENDIENTES
    out = [f"# Flujos pendientes · trabajo {trabajo}", "",
           f"{len(pendientes)} flujo(s) sin cerrar. Para retomar en otro coordinador: pegar la respuesta de desarrollo en el bloque "
           f"de cada flujo y correr `python -m pc trabajo retomar --trabajo {trabajo}`.", ""]
    for x in pendientes:
        f, n = x["f"], x["flujo"]
        sem = L.leer(trabajo, f"semaforo/{n}.json") or {}
        rc = L.leer(trabajo, f"codigo/{n}/revision.json") or {}
        distintas = [r for r in rc.get("reglas") or [] if r.get("resultado") not in ("IGUAL", "EQUIVALENTE")]
        out += [f"## {n} · v{x['version']} · {x['estado']}", "",
                f"- Stratio `{x['stratio'] or '—'}` · {x['fl'] or 'sin FL'} · grupo {x['grupo']} · nodo `F:{n}`",
                f"- Semáforo: {sem.get('estado') or '—'} · revisión de código: {rc.get('veredicto') or 'sin revisión'}"
                + (f" (Stratio v{rc.get('version_stratio')})" if rc.get("version_stratio") else ""), ""]
        for m in sem.get("motivos_rojo") or []:
            out.append(f"- ROJO: {m[:300]}")
        out += ["", "### Motivo con cifras", ""]
        filas_dif = []
        for o in f["objetos"]:
            co = L.leer(trabajo, f"v4/cotejos/{o['clave']}.json") or {}
            e, m = co.get("encabezado") or {}, (co.get("metricas") or {}).get("filas") or {}
            out.append(f"- `{o['clave']}`: {e.get('estado') or 'sin cotejo'} · filas Stratio {_f(m.get('stratio'))} | Fabric "
                       f"{_f(m.get('fabric'))} (Δ {_f(m.get('delta'))})")
            for j in co.get("justificaciones") or []:
                if j.get("decision") in ("JUSTIFICADA", "INFORMATIVA"):
                    continue
                filas_dif.append((o["clave"], j))
                out.append(f"  - {j['id']} {j.get('control')} {j.get('columna') or ''} · {_f(j.get('filas_afectadas'))} fila(s) · "
                           f"**{j.get('decision')}** · {(j.get('causa') or j.get('que_se_encontro') or '')[:240]}")
            for c in e.get("sin_analizar") or []:
                out.append(f"  - sin analizar: {c}")
        if x["estado"] == "DEVUELTO" or distintas:
            out += ["", "### Ficha de devolución (reglas de negocio desalineadas)", "",
                    f"1. **Flujo:** {x['fl'] or 'sin FL'} · Fabric `{n}` · Stratio `{x['stratio'] or '—'}` · va a **{_equipo(x['grupo'])}**.",
                    f"2. **Tablas y hallazgos:** " + ("; ".join(f"`{k}` {j['id']}" for k, j in filas_dif) or "ver motivo"),
                    "3. **Regla en Rocket:** " + ("; ".join(f"{r['id']} · {str(r.get('stratio'))[:200]}" for r in distintas)
                                                or "sin regla registrada por el revisor de código"),
                    "4. **Regla en Fabric:** " + ("; ".join(f"{r['id']} · {str(r.get('fabric'))[:200]}" for r in distintas)
                                                 or "sin regla registrada"),
                    "5. **Efecto medido:** " + ("; ".join(f"`{k}` {j['id']}: {_f(j.get('filas_afectadas'))} fila(s)"
                                                         + (f", ej. `{json.dumps((j.get('ejemplos') or [None])[0], ensure_ascii=False, default=str)[:160]}`"
                                                            if j.get("ejemplos") else "") for k, j in filas_dif[:3]) or "ver motivo"),
                    "6. **Qué corregir:** " + ("; ".join(f"{r['id']}: {r.get('impacto') or r.get('regla')}" for r in distintas)
                                              or "lo define el cotejador con la persona"),
                    "7. **Aceptación de la re-entrega:** ciclo v" + str(x["version"] + 1) +
                    " con los controles que deciden en cumplimiento y las diferencias de arriba resueltas o justificadas con causa medida."]
        out += ["", "### Grafo", "", G.mermaid(trabajo, n, g), "", "### Respuesta de desarrollo", "",
                f"<!-- respuesta:{n} -->", "", f"<!-- /respuesta:{n} -->", ""]
    # archivos locales que se conservan
    from .cache import gestor
    try:
        man = gestor.manifiesto(trabajo)["entradas"]
    except Exception:
        man = {}
    base = L.dir_lote(trabajo)
    out += ["## Archivos locales que se conservan (no se borran)", "", "| Qué | Ruta | Tamaño | Para qué |", "|---|---|---|---|",
            f"| estado del trabajo | `trabajos/{trabajo}/` | {_mb(_du(base))} | lote.json, bitácora, mediciones, cotejos, partes, grafo |",
            f"| grafo | `trabajos/{trabajo}/grafo/grafo.json` | {_mb(_du(os.path.join(base, 'grafo')))} | contexto para retomar y para el acta |",
            f"| historial de ciclos | `trabajos/{trabajo}/historial/` | {_mb(_du(os.path.join(base, 'historial')))} | versiones anteriores vN |"]
    pend = {x["flujo"] for x in pendientes}
    obj_pend = {o["clave"] for x in pendientes for o in x["f"]["objetos"]}
    for k_, e in sorted(man.items()):
        lado, k = k_.split("/", 1)
        if k in obj_pend:
            out.append(f"| caché {lado} `{k}` | `{os.path.relpath(e['carpeta'], RAIZ) if e.get('carpeta') else '—'}` | "
                       f"{_mb(e.get('bytes'))} | reutilizable en el próximo ciclo si la fuente no cambia (estado {e.get('estado')}) |")
    out += ["", "## Cómo retomar", "",
            f"1. Abrir un coordinador en `{RAIZ}` y decir: «retomar el trabajo {trabajo} desde `trabajos/{trabajo}/cierre/PENDIENTES_{trabajo}.md`».",
            f"2. `python -m pc trabajo retomar --trabajo {trabajo}` lee las respuestas pegadas y propone el ciclo de cada flujo "
            "(`codigo`, `fuente --objetos …` o `lado`). Lo confirma una persona.",
            f"3. `python -m pc trabajo siguiente --trabajo {trabajo}` da el próximo paso de cada flujo y qué agentes van en paralelo.", ""]
    cuerpo = "\n".join(out) + "\n"
    p_pe = os.path.join(dirc, f"PENDIENTES_{trabajo}.md")
    previo = open(p_pe, encoding="utf8").read() if os.path.exists(p_pe) else ""
    cuerpo = _conservar_respuestas(previo, cuerpo)
    open(p_pe, "w", encoding="utf8").write(_front("PENDIENTES", trabajo, pendientes, cuerpo))
    L.bitacora(trabajo, "coordinador", "cierre", {"exitosos": [x["flujo"] for x in exitosos], "pendientes": sorted(pend)},
               salidas=[os.path.relpath(p_ex, base), os.path.relpath(p_pe, base)])
    return p_ex, p_pe, exitosos, pendientes, falt


_RESP = re.compile(r"<!-- respuesta:(?P<f>[^ ]+) -->\n(?P<t>.*?)<!-- /respuesta:(?P=f) -->", re.S)


def _conservar_respuestas(previo, nuevo):
    """Regenerar el markdown no borra lo que desarrollo ya pego."""
    pegado = {m.group("f"): m.group("t") for m in _RESP.finditer(previo) if m.group("t").strip()}
    return _RESP.sub(lambda m: f"<!-- respuesta:{m.group('f')} -->\n{pegado.get(m.group('f'), m.group('t'))}<!-- /respuesta:{m.group('f')} -->", nuevo)


_PISTAS = (("codigo", r"c[oó]digo|regla|l[oó]gica|transformaci|notebook|filtro|cruce|join|agregaci|c[aá]lculo"),
           ("fuente", r"fuente|ruta|entrada|insumo|resincroniz|sincroniz|carga hist|ventana|origen"),
           ("lado", r"re-?ejecut|volv\w+ a (correr|ejecutar)|nueva corrida|corri[oó] de nuevo"))


def retomar(trabajo):
    """Propuesta por flujo desde las respuestas pegadas. NO abre ciclos: lo confirma una persona."""
    p = os.path.join(L.dir_lote(trabajo), "cierre", f"PENDIENTES_{trabajo}.md")
    if not os.path.exists(p):
        raise FileNotFoundError(f"no existe {p}: correr antes python -m pc cierre --trabajo {trabajo}")
    out = []
    for m in _RESP.finditer(open(p, encoding="utf8").read()):
        n, t = m.group("f"), m.group("t").strip()
        if not t:
            out.append({"flujo": n, "respuesta": None, "propuesta": None, "comando": None})
            continue
        sin_codigo = re.search(r"(c[oó]digo|regla|l[oó]gica)\s+(\w+\s+)?(no|sin)\s+cambi|no\s+(se\s+)?cambi\w*\s+(el\s+|la\s+)?"
                               r"(c[oó]digo|regla|l[oó]gica)|sin\s+cambios?\s+(de|en|al)\s+(c[oó]digo|regla)", t, re.I)
        alcance = next((a for a, rx in _PISTAS if not (a == "codigo" and sin_codigo) and re.search(
            rx, re.sub(r"(c[oó]digo|regla|l[oó]gica)\s+(\w+\s+)?(no|sin)\s+cambi\w*", "", t, flags=re.I) if a == "codigo" else t, re.I)),
            "fuente" if sin_codigo else "codigo")
        f = L.flujo(trabajo, n) or {"objetos": []}
        objs = [o["clave"] for o in f["objetos"] if o["clave"].lower() in t.lower()
                or str((o.get("fabric") or {}).get("ruta", "")).lower() in t.lower()]
        if alcance == "fuente" and not objs:
            objs = [o["clave"] for o in f["objetos"]]
        cmd = (f"python -m pc ciclo --trabajo {trabajo} --flujo {n} --alcance {alcance}"
               + (f" --objetos {','.join(objs)}" if alcance == "fuente" else "") + f" --motivo \"{t[:120]}\"")
        out.append({"flujo": n, "respuesta": t[:400], "propuesta": alcance, "objetos": objs or None, "comando": cmd})
    return out
