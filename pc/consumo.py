"""Revisor de consumo de tokens y de asignación de modelo a los agentes. SOLO LEE: no cambia agentes, modelos ni
flujos; lo que propone pasa por una persona y se registra como mejora (`pc mejora registrar`).

  python -m pc consumo resumen [--dias N | --desde AAAA-MM-DD | --sesion S]   tokens y costo por agente y modelo
  python -m pc consumo revisar [--dias N | --desde … | --sesion S]            hallazgos con cifras y propuesta
  python -m pc consumo vivo [--sesion S]                                       esta sesión: contexto ahora, costo, agentes
  python -m pc consumo agentes [--dias N]                                      cada agente: modelo declarado y real, costo/corrida

Fuente: las transcripciones de Claude Code (~/.claude/projects/<proyecto>/<sesion>.jsonl y
<sesion>/subagents/agent-*.jsonl con su .meta.json). Cada respuesta del modelo trae su `usage` exacto; se cuenta una
vez por requestId. Los tokens son exactos; el costo es de referencia (precios de lista en config/consumo.json).
Índice por archivo (tamaño + mtime) en ~/.cache/pc/consumo/indice.json: solo se relee lo que cambió.
"""
import collections
import datetime
import glob
import json
import os
import re

from .config import RAIZ

CFG = json.load(open(os.path.join(RAIZ, "config", "consumo.json"), encoding="utf8"))
PROY = os.path.join(os.path.expanduser("~"), ".claude", "projects", RAIZ.replace("/", "-").replace(".", "-"))
IDX = os.path.join(os.path.expanduser("~"), ".cache", "pc", "consumo", "indice.json")
AGENTES_DIR = os.path.join(RAIZ, ".claude", "agents")
_RE_PC = re.compile(r"-m\s+pc\s+(\w+)(?:\s+([a-z]\w*))?")
_CAMPOS = ("entrada", "salida", "cache_lectura", "cache_5m", "cache_1h")
VERSION_IDX = 3


def _precio(modelo):
    for k, v in CFG["precios_usd_mtok"].items():
        if modelo and modelo.startswith(k):
            return v
    return None


def costo(t, modelo):
    p = _precio(modelo)
    return sum(t.get(c, 0) * p[c] for c in _CAMPOS) / 1e6 if p else 0.0


def declarados():
    out = {}
    for f in glob.glob(os.path.join(AGENTES_DIR, "*.md")):
        m = re.search(r"^model:\s*(\S+)", open(f, encoding="utf8").read(), re.M)
        out[os.path.basename(f)[:-3]] = m.group(1) if m else None
    return out


def cambio_modelo():
    """{agente: fecha ISO del último commit que cambió `model:` en su front-matter} (antes de eso regía otro modelo)."""
    import subprocess
    out = {}
    for ag in declarados():
        try:
            r = subprocess.run(["git", "-C", RAIZ, "log", "-1", "--format=%cI", "-G^model:", "--", f".claude/agents/{ag}.md"],
                               capture_output=True, text=True, timeout=10)
            if r.stdout.strip():
                out[ag] = datetime.datetime.fromisoformat(r.stdout.strip()).astimezone(datetime.timezone.utc).isoformat()
        except Exception:
            pass
    return out


def _clave_herramienta(nombre, entrada):
    if nombre == "Bash":
        m = _RE_PC.search(entrada.get("command") or "")
        return "Bash pc " + " ".join(x for x in m.groups() if x) if m else "Bash"
    if nombre in ("Agent", "Task"):
        return f"Agent {entrada.get('subagent_type') or 'general-purpose'}"
    return nombre


def _leer_archivo(ruta):
    """Resume un transcript: por modelo los tokens; contexto por llamada; herramientas y su tamaño de resultado."""
    r = {"modelos": {}, "llamadas": 0, "inicio": None, "fin": None, "ctx": [], "reescrituras": [],
         "herr": {}, "errores": 0, "agent_model": [], "resultados_grandes": []}
    vistos, usos, ult_t = set(), {}, None
    umbral_kb = CFG["umbrales"]["resultado_grande_kb"] * 1000
    for ln in open(ruta, encoding="utf8", errors="replace"):
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        ts, msg = d.get("timestamp"), d.get("message") or {}
        if ts:
            r["inicio"] = r["inicio"] or ts
            r["fin"] = ts
        if d.get("type") == "assistant":
            for c in msg.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    k = _clave_herramienta(c.get("name"), c.get("input") or {})
                    usos[c.get("id")] = k
                    h = r["herr"].setdefault(k, [0, 0])
                    h[0] += 1
                    if c.get("name") in ("Agent", "Task") and (c.get("input") or {}).get("model"):
                        r["agent_model"].append([(c["input"].get("subagent_type") or "general-purpose"), c["input"]["model"], ts])
            rid = d.get("requestId")
            mod = msg.get("model")
            if not rid or rid in vistos or not mod or mod.startswith("<"):
                continue
            vistos.add(rid)
            u = msg.get("usage") or {}
            cc = u.get("cache_creation") or {}
            w1h = cc.get("ephemeral_1h_input_tokens", 0)
            w5m = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) - w1h)
            t = r["modelos"].setdefault(mod, dict.fromkeys(_CAMPOS + ("llamadas",), 0))
            t["entrada"] += u.get("input_tokens", 0)
            t["salida"] += u.get("output_tokens", 0)
            t["cache_lectura"] += u.get("cache_read_input_tokens", 0)
            t["cache_5m"] += w5m
            t["cache_1h"] += w1h
            t["llamadas"] += 1
            r["llamadas"] += 1
            ctx = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            r["ctx"].append(ctx)
            tt = _t(ts)
            if u.get("cache_creation_input_tokens", 0) >= CFG["umbrales"]["reescritura_cache_grande"]:
                r["reescrituras"].append([ts, u["cache_creation_input_tokens"], mod, round(tt - ult_t) if tt and ult_t else None, w1h])
            ult_t = tt or ult_t
        elif d.get("type") == "user" and isinstance(msg.get("content"), list):
            for c in msg["content"]:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    k = usos.get(c.get("tool_use_id"), "?")
                    n = len(json.dumps(c.get("content"), ensure_ascii=False))
                    r["herr"].setdefault(k, [0, 0])[1] += n
                    if c.get("is_error"):
                        r["errores"] += 1
                    if n >= umbral_kb:
                        r["resultados_grandes"].append([k, n, ts])
    # el contexto por llamada se guarda resumido (el índice no debe crecer con cada llamada)
    cx = r.pop("ctx")
    r["ctx_medio"] = sum(cx) // len(cx) if cx else 0
    r["ctx_max"] = max(cx) if cx else 0
    r["ctx_ultimo"] = cx[-1] if cx else 0
    r["resultados_grandes"] = sorted(r["resultados_grandes"], key=lambda x: -x[1])[:30]
    return r


def _t(ts):
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, AttributeError):
        return None


def indice():
    """{ruta: resumen} de todas las transcripciones del proyecto, releyendo solo las que cambiaron."""
    try:
        idx = json.load(open(IDX, encoding="utf8"))
        if idx.get("_version") != VERSION_IDX:
            idx = {}
    except (OSError, ValueError):
        idx = {}
    vivos = {}
    for f in glob.glob(os.path.join(PROY, "*.jsonl")) + glob.glob(os.path.join(PROY, "*", "subagents", "*.jsonl")):
        st = os.stat(f)
        firma = [st.st_size, int(st.st_mtime)]
        x = idx.get(f)
        if not x or x.get("firma") != firma:
            x = _leer_archivo(f)
            x["firma"] = firma
            if "/subagents/" in f:
                mf = f[:-6] + ".meta.json"
                meta = json.load(open(mf, encoding="utf8")) if os.path.exists(mf) else {}
                x["agente"] = meta.get("agentType") or "?"
                x["descripcion"] = (meta.get("description") or "")[:100]
                x["sesion"] = os.path.basename(os.path.dirname(os.path.dirname(f)))
            else:
                x["agente"] = "COORDINADOR"
                x["sesion"] = os.path.basename(f)[:-6]
        vivos[f] = x
    vivos["_version"] = VERSION_IDX
    os.makedirs(os.path.dirname(IDX), exist_ok=True)
    tmp = IDX + ".tmp"
    json.dump(vivos, open(tmp, "w", encoding="utf8"))
    os.replace(tmp, IDX)
    vivos.pop("_version")
    return vivos


def filtrar(idx, dias=None, desde=None, sesion=None):
    if dias:
        desde = (datetime.date.today() - datetime.timedelta(days=dias)).isoformat()
    out = {}
    for f, x in idx.items():
        if sesion and not x["sesion"].startswith(sesion):
            continue
        if desde and (x.get("fin") or "") < desde:
            continue
        if x["llamadas"]:
            out[f] = x
    return out


def por_agente(sel):
    """[(agente, modelo, tokens+costo+corridas)] ordenado por costo."""
    agg = {}
    for x in sel.values():
        for mod, t in x["modelos"].items():
            a = agg.setdefault((x["agente"], mod), dict.fromkeys(_CAMPOS + ("llamadas",), 0) | {"corridas": set()})
            for c in _CAMPOS + ("llamadas",):
                a[c] += t[c]
            a["corridas"].add(x["sesion"] if x["agente"] == "COORDINADOR" else id(x))
    filas = []
    for (ag, mod), a in agg.items():
        a["corridas"] = len(a["corridas"])
        a["costo"] = costo(a, mod)
        filas.append((ag, mod, a))
    return sorted(filas, key=lambda f: -f[2]["costo"])


def _mt(n):
    return f"{n / 1e6:,.1f} M" if n >= 1e6 else f"{n / 1e3:,.0f} k"


def resumen(sel):
    filas = por_agente(sel)
    total = sum(a["costo"] for _, _, a in filas) or 1
    out = [f"{'agente':24} {'modelo':18} {'corr':>5} {'llam':>6} {'ctx leído':>10} {'cache esc':>10} {'salida':>9} {'USD ref':>9} {'%':>5}"]
    for ag, mod, a in filas:
        out.append(f"{ag:24} {mod.replace('claude-', ''):18} {a['corridas']:5} {a['llamadas']:6} {_mt(a['cache_lectura'] + a['entrada']):>10} "
                   f"{_mt(a['cache_5m'] + a['cache_1h']):>10} {_mt(a['salida']):>9} {a['costo']:9.2f} {100 * a['costo'] / total:5.1f}")
    out.append(f"TOTAL USD ref {total:,.2f} · {len(sel)} transcripciones · tokens exactos, costo a precio de lista (config/consumo.json)")
    return "\n".join(out)


def revisar(sel):
    """Hallazgos medidos, cada uno con cifras, un ejemplo y una propuesta. Ninguno se aplica solo."""
    u, decl, gen = CFG["umbrales"], declarados(), set(CFG["agentes_genericos"])
    H = []
    coord = [x for x in sel.values() if x["agente"] == "COORDINADOR"]
    total = sum(costo(t, m) for x in sel.values() for m, t in x["modelos"].items()) or 1

    # 1. contexto del coordinador: cada turno relee todo el contexto acumulado
    grandes = [x for x in coord if x["ctx_medio"] > u["contexto_medio_coordinador"]]
    if grandes:
        exceso = 0.0
        for x in grandes:
            for m, t in x["modelos"].items():
                p = _precio(m) or {"cache_lectura": 0}
                exceso += t["llamadas"] * (x["ctx_medio"] - u["contexto_medio_coordinador"]) * p["cache_lectura"] / 1e6
        peor = max(grandes, key=lambda x: x["ctx_medio"])
        H.append({"id": "C1", "tema": "contexto del coordinador", "usd": exceso,
                  "cifras": f"{len(grandes)} de {len(coord)} sesiones con contexto medio > {u['contexto_medio_coordinador'] // 1000} k tokens",
                  "ejemplo": f"sesión {peor['sesion'][:8]}: {peor['llamadas']} llamadas, contexto medio {peor['ctx_medio'] // 1000} k, máx {peor['ctx_max'] // 1000} k",
                  "propuesta": "el estado vive en disco: al cerrar un flujo (o al pasar 250 k) hacer /compact o cerrar la sesión y retomar con `pc trabajo siguiente`; el hook avisa al cruzar 250/500/750 k"})

    # 2. reescrituras grandes de caché: el prefijo cambió o se enfrió (TTL 5 min o 1 h) y se vuelve a pagar entero
    rw = [(x, r) for x in sel.values() for r in x["reescrituras"]]
    if rw:
        def _usd(r):
            p = _precio(r[2]) or {"cache_5m": 0, "cache_1h": 0}
            w1h = r[4] if len(r) > 4 else 0
            return (w1h * p["cache_1h"] + (r[1] - w1h) * p["cache_5m"]) / 1e6
        tramos = collections.Counter("sin dato" if r[3] is None else "> 1 h" if r[3] > 3600 else "5–60 min" if r[3] > 300 else "< 5 min"
                                     for _, r in rw)
        x, r = max(rw, key=lambda xr: xr[1][1])
        H.append({"id": "C2", "tema": "reescrituras de caché", "usd": sum(_usd(r) for _, r in rw),
                  "cifras": f"{len(rw)} reescrituras ≥ {u['reescritura_cache_grande'] // 1000} k tokens · pausa previa: "
                            + ", ".join(f"{k} ×{n}" for k, n in tramos.most_common()),
                  "ejemplo": f"{x['agente']} {x['sesion'][:8]}: {r[1] // 1000} k reescritos el {r[0][:16]} (pausa {r[3]} s)",
                  "propuesta": "lo que se reescribe es el contexto entero: con contexto corto (compactar al cerrar cada flujo) cada reescritura cuesta menos; "
                               "las de pausa < 5 min son cambios del prefijo (compactación, herramientas cargadas a mitad de sesión)"})

    # 3. modelo real distinto del declarado, contando solo desde el último cambio de `model:` en el front-matter
    desde = cambio_modelo()
    mis, viejos = collections.Counter(), collections.Counter()
    usd3 = 0.0
    for x in sel.values():
        ag = x["agente"]
        if ag in decl and decl[ag] and decl[ag] != "inherit":
            for m, t in x["modelos"].items():
                if decl[ag] not in m:
                    if (x.get("fin") or "") >= desde.get(ag, ""):
                        mis[(ag, decl[ag], m)] += 1
                        usd3 += costo(t, m)
                    else:
                        viejos[ag] += 1
    forz = collections.Counter((a, m) for x in coord for a, m, _ in x["agent_model"])
    if mis or forz or viejos:
        H.append({"id": "C3", "tema": "modelo distinto del declarado", "usd": usd3,
                  "cifras": ("; ".join(f"{a} declarado {d} corrió {m.replace('claude-', '')} ×{n}" for (a, d, m), n in mis.most_common(6))
                             or "ninguno desde el último cambio del front-matter")
                            + (f" · ya corregido (antes del cambio de `model:`): " + ", ".join(f"{a} ×{n}" for a, n in viejos.most_common()) if viejos else ""),
                  "ejemplo": "; ".join(f"Agent({a}, model={m}) ×{n}" for (a, m), n in forz.most_common(4)) or "sin `model` forzado en el lanzamiento",
                  "propuesta": "no pasar `model` al lanzar un agente del pipeline: manda el front-matter de .claude/agents/"})

    # 3 bis. un mismo alias que resuelve a versiones distintas (p. ej. «haiku» → 4.5 o 5.5, con 10× de diferencia de precio)
    alias = collections.defaultdict(collections.Counter)
    for x in sel.values():
        if decl.get(x["agente"]) in ("haiku", "sonnet", "opus"):
            for m in x["modelos"]:
                if decl[x["agente"]] in m:
                    alias[decl[x["agente"]]][m] += 1
    for al, c in alias.items():
        if len(c) > 1:
            viejo = min(c, key=lambda m: (_precio(m) or {}).get("entrada", 0) if al != "haiku" else -(_precio(m) or {}).get("entrada", 0))
            usd6 = sum(costo(t, m) for x in sel.values() for m, t in x["modelos"].items() if m == viejo and decl.get(x["agente"]) == al)
            ult = max((x.get("fin") or "") for x in sel.values() for m in x["modelos"] if m == viejo)
            H.append({"id": f"C6-{al}", "tema": f"el alias «{al}» resuelve a versiones distintas", "usd": usd6,
                      "cifras": ", ".join(f"{m.replace('claude-', '')} ×{n}" for m, n in c.most_common()) + f" · último uso de {viejo.replace('claude-', '')}: {ult[:10]}",
                      "ejemplo": ", ".join(sorted({x["agente"] for x in sel.values() if viejo in x["modelos"]}))[:120],
                      "propuesta": f"fijar el modelo con su ID completo en el front-matter (p. ej. `model: claude-{al}-5-5`) tras probarlo en UNA corrida"})

    # 4. agentes genéricos (sin modelo propio: heredan Opus) haciendo trabajo del pipeline
    g = [x for x in sel.values() if x["agente"] in gen]
    if g:
        usd = sum(costo(t, m) for x in g for m, t in x["modelos"].items())
        c = collections.Counter(x["agente"] for x in g)
        pcs = collections.Counter(k for x in g for k in x["herr"] if k.startswith("Bash pc"))
        H.append({"id": "C4", "tema": "agentes genéricos", "usd": usd,
                  "cifras": ", ".join(f"{a} ×{n}" for a, n in c.most_common()) + f" · {100 * usd / total:.1f} % del costo",
                  "ejemplo": "comandos del pipeline que corrieron: " + (", ".join(k[8:] for k, _ in pcs.most_common(5)) or "ninguno"),
                  "propuesta": "usar el agente del pipeline que corresponde (tiene su modelo); para búsquedas, Explore con model=haiku o sonnet; un fork hereda Opus y todo el contexto"})

    # 5. resultados grandes que entran al contexto (cada byte se relee en todos los turnos siguientes)
    rg = collections.Counter()
    rn = collections.Counter()
    for x in coord:
        for k, n, _ in x["resultados_grandes"]:
            rg[k] += n
            rn[k] += 1
    if rg:
        H.append({"id": "C5", "tema": "resultados grandes en el coordinador", "usd": None,
                  "cifras": "; ".join(f"{k} ×{rn[k]} ({rg[k] / 1e6:.1f} MB)" for k, _ in rg.most_common(5)),
                  "ejemplo": f"umbral {u['resultado_grande_kb']} KB por resultado",
                  "propuesta": "Read con offset/limit o delegar la lectura a un agente que devuelva la conclusión; los comandos ya salen resumidos con PC_RESUMEN=1, no pedir --detalle en el coordinador"})

    # 6. ajuste de modelo por agente: Opus haciendo trabajo mecánico · Haiku con muchos errores
    for ag, xs in _agrupar(sel, decl).items():
        modelo = decl.get(ag) or ""
        herr = collections.Counter()
        llam = sum(x["llamadas"] for x in xs)
        err = sum(x["errores"] for x in xs)
        for x in xs:
            for k, (n, _) in x["herr"].items():
                herr[k] += n
        tot = sum(herr.values()) or 1
        pct_pc = 100 * sum(n for k, n in herr.items() if k.startswith("Bash pc")) / tot
        usd = sum(costo(t, m) for x in xs for m, t in x["modelos"].items())
        if modelo == "opus" and pct_pc >= u["agente_opus_mecanico_pct_bash_pc"]:
            H.append({"id": f"M-{ag}", "tema": f"modelo de {ag}", "usd": usd,
                      "cifras": f"opus · {len(xs)} corridas · {pct_pc:.0f} % de sus herramientas son comandos `pc`",
                      "ejemplo": ", ".join(k for k, _ in herr.most_common(4)),
                      "propuesta": f"candidato a sonnet: probarlo en UNA corrida y comparar el parte con la anterior antes de cambiar el front-matter"})
        if modelo == "haiku" and tot > 20 and 100 * err / tot >= u["agente_errores_pct"]:
            H.append({"id": f"M-{ag}", "tema": f"modelo de {ag}", "usd": usd,
                      "cifras": f"haiku · {len(xs)} corridas · {err} de {tot} herramientas con error ({100 * err / tot:.0f} %), {llam} llamadas",
                      "ejemplo": ", ".join(k for k, _ in herr.most_common(4)),
                      "propuesta": "los reintentos cuestan: revisar el prompt del agente o probar sonnet en UNA corrida"})
    return sorted(H, key=lambda h: -(h["usd"] or 0))


def _agrupar(sel, decl):
    g = collections.defaultdict(list)
    for x in sel.values():
        if x["agente"] in decl:
            g[x["agente"]].append(x)
    return g


def texto_revision(H, sel):
    total = sum(costo(t, m) for x in sel.values() for m, t in x["modelos"].items())
    out = [f"REVISIÓN DE CONSUMO · {len(sel)} transcripciones · USD ref {total:,.2f} · solo lectura, nada se aplica solo"]
    for h in H:
        out.append(f"\n[{h['id']}] {h['tema']}" + (f" · USD ref {h['usd']:,.2f}" if h["usd"] else ""))
        out.append(f"  cifras:    {h['cifras']}")
        out.append(f"  ejemplo:   {h['ejemplo']}")
        out.append(f"  propuesta: {h['propuesta']}")
    out.append("\nAplicar una propuesta = mejora: se confirma con la persona y `pc mejora registrar`.")
    return "\n".join(out)


def agentes(sel):
    decl = declarados()
    out = [f"{'agente':24} {'declarado':9} {'corrió en':28} {'corr':>5} {'USD/corrida':>11} {'llam/corr':>9} {'err %':>6}"]
    for ag, xs in sorted(_agrupar(sel, decl).items()):
        mods = collections.Counter(m.replace("claude-", "") for x in xs for m in x["modelos"])
        usd = sum(costo(t, m) for x in xs for m, t in x["modelos"].items())
        llam = sum(x["llamadas"] for x in xs)
        herr = sum(n for x in xs for n, _ in x["herr"].values()) or 1
        err = sum(x["errores"] for x in xs)
        out.append(f"{ag:24} {decl[ag] or '—':9} {', '.join(f'{m}×{n}' for m, n in mods.most_common()):28} {len(xs):5} "
                   f"{usd / len(xs):11.2f} {llam // len(xs):9} {100 * err / herr:6.1f}")
    return "\n".join(out)


def vivo(idx, sesion=None):
    coord = [x for x in idx.values() if x["agente"] == "COORDINADOR" and x["llamadas"]]
    if sesion:
        coord = [x for x in coord if x["sesion"].startswith(sesion)]
    if not coord:
        return "sin sesión"
    s = max(coord, key=lambda x: x.get("fin") or "")
    subs = [x for x in idx.values() if x["sesion"] == s["sesion"] and x["agente"] != "COORDINADOR" and x["llamadas"]]
    cs = sum(costo(t, m) for m, t in s["modelos"].items())
    ca = sum(costo(t, m) for x in subs for m, t in x["modelos"].items())
    av = [a for a in CFG["umbrales"]["contexto_aviso_tokens"] if s["ctx_ultimo"] >= a]
    out = [f"SESIÓN {s['sesion'][:8]} · contexto ahora {s['ctx_ultimo'] // 1000} k (medio {s['ctx_medio'] // 1000} k, máx {s['ctx_max'] // 1000} k) · "
           f"{s['llamadas']} llamadas · USD ref coordinador {cs:.2f} + agentes {ca:.2f}"]
    if av:
        out.append(f"⚠ contexto sobre {av[-1] // 1000} k: proponer /compact o cerrar y retomar (el estado está en disco)")
    for x in sorted(subs, key=lambda x: -sum(costo(t, m) for m, t in x["modelos"].items()))[:10]:
        c = sum(costo(t, m) for m, t in x["modelos"].items())
        out.append(f"  {x['agente']:22} {'/'.join(m.replace('claude-', '') for m in x['modelos']):18} {x['llamadas']:4} llam · "
                   f"USD ref {c:6.2f} · {x.get('descripcion', '')[:50]}")
    return "\n".join(out)


def guardar(H, sel):
    """Deja la última revisión en ~/.cache/pc/consumo/revision.json (el panel y el agente la leen)."""
    p = os.path.join(os.path.dirname(IDX), "revision.json")
    json.dump({"fecha_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "transcripciones": len(sel), "hallazgos": H,
               "por_agente": [{"agente": a, "modelo": m, **{k: v for k, v in t.items()}} for a, m, t in por_agente(sel)]},
              open(p, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    return p
