"""Mensajes listos para copiar: UNO por destino, con todos sus flujos dentro.

  python -m pc mensaje --trabajo T [--para desarrollo|comfandi]

  mensajes/desarrollo_analitica.md   chat para el equipo de analitica (DIA): analitica y orquestadores
  mensajes/desarrollo_ingesta.md     chat para el equipo de ingesta (CDS)
  mensajes/comfandi.md               correo para Comfandi: reglas de negocio por confirmar (A_VERIFICAR)
  mensajes/secciones.json            el pedazo de cada flujo (el panel lo muestra al elegir un flujo)

Solo lo que el destinatario necesita: que flujo, que tabla, que falla o que diferencia hay, cifras de cada lado, un
ejemplo, como lo hace Stratio y como Fabric, y que corregir (o que confirmar). Nada del proceso de QA: ni semaforo,
ni ciclos, ni estados, ni quien decidio. Entra a desarrollo un flujo cuya ejecucion falla (semaforo ROJO) o con
diferencias decididas DEVUELTO; a Comfandi, las diferencias A_VERIFICAR. Se usa «reglas de negocio desalineadas»,
nunca «error de codigo». Solo se cita un enlace publicado con HEAD OK.
"""
import datetime
import json
import os
import re

from . import lote as L

EQUIPO = {"ingesta": ("ingesta", "ingesta (CDS)"), "analitica": ("analitica", "analítica (DIA)"),
          "orquestador": ("analitica", "analítica (DIA)")}
TOPE_COMFANDI = 15


def _m(n):
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else ("—" if n is None else str(n))


def _limpio(t, n=420):
    """Sin rastro del proceso de QA ni ruido tecnico: decisiones, propuestas, rutas abfss, trazas de Spark."""
    t = str(t or "")
    t = re.sub(r"Decisi[oó]n del usuario[^:]*:\s*", "", t, flags=re.I)
    t = re.sub(r"DEVUELTO a \w+(\s*\([^)]*\))?\s*(por [^:]*)?:\s*", "", t, flags=re.I)
    t = re.sub(r"\[propuesta:[^\]]*\]", "", t, flags=re.I)
    t = re.sub(r"\s*\|\|.*$", "", t)
    t = re.sub(r"\s*Medido (?:ademas|además|el)\b.*$", "", t, flags=re.I)        # notas internas de la medicion
    t = re.sub(r"\((?:medida|sin medir)\)", "", t, flags=re.I)
    t = re.sub(r"abfss://\S+", "(ruta en OneLake)", t)
    t = re.sub(r"\{\s*\"requestId\".*", "(ver el detalle del error en la ejecución)", t)
    t = re.sub(r"\s*·\s*Spark no pudo leerla:.*", "", t)
    t = t.replace("(sin nombre) · ", "").replace("bloqueante del validador: ", "")
    t = re.sub(r"\s{2,}", " ", t).strip(" ·;")
    return t if len(t) <= n else t[:n - 1] + "…"


def _motivo(m):
    """Un motivo de semaforo ROJO dicho como el problema del flujo."""
    m = _limpio(m, 260)
    m = re.sub(r"^la corrida termino en (\w+)", r"la ejecución del flujo termina en \1", m)
    m = re.sub(r"^corrida_exitosa · corrida termino en Failed:?", "la ejecución termina en Failed:", m)
    m = re.sub(r"^la actividad termino en Failed", "una actividad del pipeline termina en Failed", m)
    m = re.sub(r"^salidas sin commit en la corrida:", "estas salidas no se escriben en la ejecución:", m)
    m = re.sub(r"^corrida del orquestador: sin corrida", "el orquestador no tiene ninguna ejecución registrada", m)
    return m


def _ejemplo(e):
    if not isinstance(e, dict):
        return str(e)[:220]
    fila = e.get("fila")
    partes = []
    if isinstance(fila, dict):
        partes.append("registro " + ", ".join(f"{k}={v}" for k, v in list(fila.items())[:4]))
    for k in ("stratio", "fabric"):
        if k in e:
            partes.append(f"{k.capitalize()}: {e[k]}")
    resto = {k: v for k, v in e.items() if k not in ("fila", "stratio", "fabric")}
    if resto and len(partes) < 2:
        partes.append(json.dumps(resto, ensure_ascii=False, default=str)[:180])
    return " · ".join(partes)[:280]


def _cifras(fi):
    s, f = fi.get("stratio"), fi.get("fabric")
    if isinstance(s, int) and isinstance(f, int):
        d = f - s
        rel = "las mismas filas" if d == 0 else f"{_m(abs(d))} filas {'más' if d > 0 else 'menos'} que Stratio"
        return f"Stratio {_m(s)} filas · Fabric {_m(f)} filas ({rel})"
    return f"Stratio {_m(s)} filas · Fabric {_m(f)} filas"


def _reglas(rc, columna):
    cols = [c.strip().lower() for c in (columna or "").split(",") if c.strip()]
    out = []
    for r in rc.get("reglas") or []:
        if r.get("resultado") in ("IGUAL", "EQUIVALENTE"):
            continue
        txt = " ".join(str(r.get(k) or "") for k in ("regla", "impacto", "stratio", "fabric")).lower()
        if not cols or any(c in txt for c in cols):
            out.append(r)
    return out


def _enlace(trabajo, rel_ol):
    pub = (L.leer(trabajo, "v4/publicado.json") or {}).get("archivos") or []
    if any(x.get("ruta") == rel_ol and x.get("head_ok") for x in pub):
        from .grafo import url_navegador
        return url_navegador(rel_ol)
    return None


def _tablas(trabajo, f):
    for o in f["objetos"]:
        co = L.leer(trabajo, f"v4/cotejos/{o['clave']}.json") or {}
        yield o, (co.get("metricas") or {}).get("filas") or {}, co.get("justificaciones") or co.get("diferencias") or []


def seccion_desarrollo(trabajo, f):
    """El pedazo de un flujo para desarrollo, o None."""
    from .reportes import v4
    n = f["nombre_fabric"]
    sem = L.leer(trabajo, f"semaforo/{n}.json") or {}
    rc = L.leer(trabajo, f"codigo/{n}/revision.json") or {}
    devs = [(o, fi, d) for o, fi, ds in _tablas(trabajo, f) for d in ds if d.get("decision") == "DEVUELTO"]
    reglas_dev = [r for r in rc.get("reglas") or [] if r.get("decision") == "DEVOLVER"]
    rojo = sem.get("estado") == "ROJO"
    if not rojo and not devs and not reglas_dev:
        return None
    out = [f"*{n}* (Stratio `{f.get('nombre_stratio') or '—'}` · {f.get('fl') or 'sin FL'})"]
    if rojo:
        out.append("No ejecuta correctamente:")
        out += [f"• {_motivo(m)}" for m in (sem.get("motivos_rojo") or [])[:6]]
        ev = L.leer(trabajo, f"etl/evidencia/{n}.json") or {}
        cv = ev.get("corrida_validada") or {}
        if cv.get("inicio_utc"):
            out.append(f"Ejecución revisada: {cv.get('inicio_utc')} · estado {cv.get('estado')}"
                       + (f" · run `{cv.get('run_id') or cv.get('run')}`" if (cv.get("run_id") or cv.get("run")) else ""))
    for r in reglas_dev:
        out.append(f"• Regla de negocio distinta: {_limpio(r.get('regla'), 200)}")
        out.append(f"  Stratio (Rocket v{rc.get('version_stratio')}): {_limpio(r.get('stratio'), 260)}")
        out.append(f"  Fabric: {_limpio(r.get('fabric'), 260)}")
        if r.get("porque"):
            out.append(f"  Efecto: {_limpio(r.get('porque'), 300)}")
    dichas = set()
    for o, fi, d in devs:
        tabla = (o.get("fabric") or {}).get("ruta") or o["clave"]
        out.append(f"• Tabla `{tabla}`" + (f", columna `{d['columna']}`" if d.get("columna") else "") + f": {_cifras(fi)}"
                   + (f" · registros afectados: {_m(d.get('filas_afectadas'))}" if d.get("filas_afectadas") else ""))
        que = _limpio(d.get('que_se_encontro') or d.get('descripcion'))
        out.append(f"  Qué pasa: {que}" if que not in dichas else "  Qué pasa: lo mismo que en la tabla anterior.")
        causa = _limpio(d.get("causa"))
        if causa and causa != que:
            out.append(f"  Por qué: {causa}" if causa not in dichas else "  Por qué: la misma causa de arriba.")
        dichas |= {que, causa}
        for e in (d.get("ejemplos") or [])[:2]:
            out.append(f"  Ejemplo: {_ejemplo(e)}")
        for r in _reglas(rc, d.get("columna"))[:2]:
            out.append(f"  Stratio (Rocket v{rc.get('version_stratio')}): {_limpio(r.get('stratio'), 260)}")
            out.append(f"  Fabric: {_limpio(r.get('fabric'), 260)}")
    fixes = [_limpio(r.get("impacto") or f"que Fabric aplique la regla de Stratio: {r.get('regla')}", 260)
             for r in (reglas_dev or _reglas(rc, None))]
    if fixes:
        out.append("Qué corregir: " + "; ".join(fixes[:4]))
    elif rojo and not devs:
        out.append("Qué corregir: que la ejecución termine bien y escriba sus salidas.")
    else:
        out.append("Qué corregir: que Fabric produzca el mismo resultado que Stratio en lo descrito.")
    v = (L.leer(trabajo, "v4/ciclos.json", {}) or {}).get(n, {}).get("version", 1)
    links = [x for x in (_enlace(trabajo, v4.ruta_ol("cotejo", o["clave"], v, pruebas=v4._pruebas(trabajo))) for o, _fi, _d in devs) if x]
    if links:
        out.append("Evidencia: " + " · ".join(dict.fromkeys(links)))
    return "\n".join(out)


def seccion_comfandi(trabajo, f):
    """Las consultas de un flujo para Comfandi: lista de bloques, o []."""
    n = f["nombre_fabric"]
    rc = L.leer(trabajo, f"codigo/{n}/revision.json") or {}
    out = []
    for o, fi, ds in _tablas(trabajo, f):
        for d in ds:
            if d.get("decision") != "A_VERIFICAR":
                continue
            tabla = (o.get("fabric") or {}).get("ruta") or o["clave"]
            b = [f"Proceso «{f.get('nombre_stratio') or n}» ({f.get('fl') or 'sin FL'}) · tabla {tabla}"
                 + (f", campo {d['columna']}" if d.get("columna") else "")]
            b.append(f"   Qué sucede: {_limpio(d.get('que_se_encontro') or d.get('descripcion'))}")
            b.append(f"   Registros: {_cifras(fi)}" + (f" · afectados: {_m(d.get('filas_afectadas'))}" if d.get("filas_afectadas") else ""))
            for e in (d.get("ejemplos") or [])[:1]:
                b.append(f"   Ejemplo: {_ejemplo(e)}")
            for r in _reglas(rc, d.get("columna"))[:1]:
                b.append(f"   En Stratio: {_limpio(r.get('stratio'), 260)}")
                b.append(f"   En Fabric: {_limpio(r.get('fabric'), 260)}")
            b.append("   ¿Cuál es la regla de negocio correcta? a) la de Stratio · b) la de Fabric · c) otra (por favor descríbanla)")
            out.append("\n".join(b))
    return out


def generar(trabajo, flujo=None, para=None):
    """Reescribe los mensajes agregados (`flujo` se ignora: cada mensaje lleva todos los flujos de su destino).
    Devuelve [(id, para, ruta)]."""
    d = L.leer(trabajo, "lote.json") or {}
    base = os.path.join(L.dir_lote(trabajo), "mensajes")
    os.makedirs(base, exist_ok=True)
    for viejo in [x for x in os.listdir(base) if x.endswith(".md") and "__" in x]:      # formato anterior: uno por flujo
        os.makedirs(os.path.join(base, "historial"), exist_ok=True)
        os.replace(os.path.join(base, viejo), os.path.join(base, "historial", viejo))
    dev = {"analitica": [], "ingesta": []}
    com, secc = [], {}
    for f in d.get("flujos", []):
        n = f["nombre_fabric"]
        s = seccion_desarrollo(trabajo, f)
        c = seccion_comfandi(trabajo, f)
        if s:
            dev[EQUIPO.get(f["grupo"], ("analitica",))[0]].append(s)
        com += [(n, x) for x in c]
        if s or c:
            secc[n] = {"desarrollo": s, "equipo": EQUIPO.get(f["grupo"], ("", ""))[1], "comfandi": c}
    textos = {}
    for k, items in dev.items():
        if items:
            eq = {"analitica": "analítica (DIA)", "ingesta": "ingesta (CDS)"}[k]
            textos[f"desarrollo_{k}"] = (f"🔧 *Flujos para revisar · {eq}* · {len(items)} flujo(s)\n\n"
                                         + "\n\n".join(f"{i}. {x}" for i, x in enumerate(items, 1)))
    if com:
        cab = [f"Asunto: Consulta de reglas de negocio · migración Stratio → Fabric · {len({n for n, _ in com})} proceso(s)", "",
               "Hola, equipo de Comfandi:", "",
               "Necesitamos su confirmación sobre las siguientes reglas de negocio, en las que Stratio y Fabric dan resultados distintos:", "", ""]
        cuerpo = [f"{i}. {x}" for i, (_n, x) in enumerate(com[:TOPE_COMFANDI], 1)]
        if len(com) > TOPE_COMFANDI:
            cuerpo.append(f"(Hay {len(com) - TOPE_COMFANDI} consulta(s) más; se las enviamos en un segundo correo para no extender este.)")
        textos["comfandi"] = "\n".join(cab) + "\n\n".join(cuerpo) + f"\n\nQuedamos atentos.\n\nSaludos,\n{L.usuario()} · Equipo VMQA · Quind S.A.S."
    out = []
    for k in ("desarrollo_analitica", "desarrollo_ingesta", "comfandi"):
        tipo = "comfandi" if k == "comfandi" else "desarrollo"
        if para and tipo != para:
            continue
        p = os.path.join(base, f"{k}.md")
        txt = textos.get(k)
        if not txt:
            if os.path.exists(p):
                os.makedirs(os.path.join(base, "historial"), exist_ok=True)
                os.replace(p, os.path.join(base, "historial", f"{k}_{datetime.datetime.now():%Y%m%dT%H%M%S}.md"))
            continue
        if (open(p, encoding="utf8").read() if os.path.exists(p) else None) != txt:
            open(p, "w", encoding="utf8").write(txt)
            L.bitacora(trabajo, "coordinador", f"mensaje_{tipo}", {"destino": k}, estado="AVISO", salidas=[os.path.relpath(p, L.dir_lote(trabajo))])
        out.append((k, tipo, p))
    L.guardar(trabajo, "mensajes/secciones.json", secc)
    return out


def listar(trabajo):
    """Los mensajes agregados vigentes (a lo sumo 3)."""
    base = os.path.join(L.dir_lote(trabajo), "mensajes")
    out = []
    nombres = {"desarrollo_analitica": ("desarrollo", "analítica (DIA)"), "desarrollo_ingesta": ("desarrollo", "ingesta (CDS)"),
               "comfandi": ("comfandi", "Comfandi")}
    for k, (tipo, destino) in nombres.items():
        p = os.path.join(base, f"{k}.md")
        if os.path.exists(p):
            out.append({"id": k, "para": tipo, "destino": destino, "texto": open(p, encoding="utf8").read(),
                        "actualizado": datetime.datetime.fromtimestamp(os.path.getmtime(p), datetime.timezone.utc).isoformat(timespec="seconds")})
    return out


def secciones(trabajo):
    return L.leer(trabajo, "mensajes/secciones.json", {}) or {}
