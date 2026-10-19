"""Panel en vivo de los coordinadores (solo lectura, localhost). Lo levanta el hook SessionStart.

  python -m pc panel [--puerto 8765]

Lee archivos locales cada vez que el navegador pide /api/estado (cada 2 s):
  ~/.cache/pc/sesiones/*.json y eventos/*.jsonl   (hooks: coordinadores abiertos, agentes, modelos, comandos)
  trabajos/<T>/bitacora.jsonl · progreso/*.json · grafo (en memoria, se rehace si cambio la bitacora o los partes)
  cookies de Rocket: solo los archivos locales (fecha y JWT), nunca su contenido
No toca Rocket, OneLake, Postgres ni la VPN, y no escribe nada que usen los agentes: no puede demorar el trabajo.
"""
import datetime
import glob
import http.server
import json
import os
import statistics
import threading
import time

from .. import lote as L
from ..config import RAIZ

BASE = os.path.join(os.path.expanduser("~"), ".cache", "pc")
HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
VENTANA_H = 12            # sesiones con actividad en las ultimas 12 h
ETAPAS = ["código", "ETL", "nivel 0/1", "semáforo", "descarga", "nivel 2", "cotejo", "decisión", "acta"]
_CACHE = {}
_LK = threading.Lock()


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc)


def _leer_json(p, defecto=None):
    try:
        return json.load(open(p, encoding="utf8"))
    except Exception:
        return defecto


def _cola(p, n=40):
    """Ultimas n lineas JSON de un archivo (lee solo el final)."""
    try:
        with open(p, "rb") as f:
            f.seek(0, 2)
            tam = f.tell()
            f.seek(max(0, tam - 64 * 1024))
            ls = f.read().decode("utf8", "replace").splitlines()[-n:]
        return [json.loads(x) for x in ls if x.strip().startswith("{")]
    except Exception:
        return []


def _vivo(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _etapa(paso, agente, estado):
    if estado in ("APROBADO", "APROBADO_CON_JUSTIFICACION") or "listo para acta" in paso:
        return 8
    if estado == "DEVUELTO" or "devuelto" in paso:
        return -1
    a = agente or ""
    if "etl" in a:
        return 1
    if "medidor-rapido" in a:
        return 2
    if a == "semaforo":
        return 3
    if "gestor-descargas" in a:
        return 4
    if "cotejador" in a and "analiza" in paso:
        return 6
    if "cotejador" in a:
        return 5
    if "decisi" in paso or a == "coordinador":
        return 7
    return 0


def _duraciones():
    """Mediana de duracion por accion, de todas las bitacoras (para el ETA). Se calcula una vez cada 10 min."""
    with _LK:
        c = _CACHE.get("dur")
        if c and time.time() - c[0] < 600:
            return c[1]
    acc = {}
    for p in glob.glob(os.path.join(RAIZ, "trabajos", "*", "bitacora.jsonl")):
        for e in _cola(p, 4000):
            if e.get("duracion_s"):
                acc.setdefault(e.get("accion"), []).append(e["duracion_s"])
    med = {k: {"mediana_s": round(statistics.median(v), 1), "n": len(v)} for k, v in acc.items() if len(v) >= 2}
    with _LK:
        _CACHE["dur"] = (time.time(), med)
    return med


def _trabajo(t):
    base = L.dir_lote(t)
    if not os.path.exists(os.path.join(base, "lote.json")):
        return None
    huella = tuple(os.path.getmtime(p) if os.path.exists(p) else 0 for p in
                   (os.path.join(base, "bitacora.jsonl"), os.path.join(base, "lote.json"), os.path.join(base, "partes")))
    with _LK:
        c = _CACHE.get(("t", t))
    if not c or c[0] != huella:
        from .. import coordinacion as K
        from .. import grafo as G
        try:
            sig = K.siguiente(t)
        except Exception as e:
            sig = [{"flujo": "?", "paso": f"error: {e}", "agente": None, "estado": "?", "comando": ""}]
        try:
            g = G.construir(t, guardar=False)
        except Exception:
            g = {"nodos": {}}
        flujos = []
        for s in sig:
            fn = g["nodos"].get(f"F:{s['flujo']}", {}).get("datos", {})
            difs = [x for x in g["nodos"].values() if x["tipo"] == "diferencia" and x["id"].split(":")[1].split("/")[0] in
                    {o.split(":", 1)[1] for o in [e["a"] for e in g.get("aristas", []) if e["de"] == f"F:{s['flujo']}" and e["rel"] == "contiene"]}]
            flujos.append({"flujo": s["flujo"], "estado": s.get("estado"), "paso": s["paso"], "agente": s.get("agente"),
                           "comando": s.get("comando"), "etapa": _etapa(s["paso"], s.get("agente"), s.get("estado")),
                           "grupo": fn.get("grupo"), "version": fn.get("version"), "semaforo": fn.get("semaforo"),
                           "codigo": fn.get("codigo"), "difs": len(difs),
                           "difs_pendientes": sum(1 for x in difs if x["datos"].get("decision") in ("PENDIENTE", None)),
                           "paralelos": [{k: c[k] for k in ("pista", "etapa", "agente", "paso")} for c in s.get("paralelos") or []],
                           "motivo_ciclo": fn.get("motivo_ciclo") if (fn.get("version") or 1) > 1 else None})
        c = (huella, {"flujos": flujos})
        with _LK:
            _CACHE[("t", t)] = c
    out = dict(c[1])
    fl = out["flujos"]
    out["marcador"] = {"aprobados": sum(1 for f in fl if f["etapa"] == 8), "devueltos": sum(1 for f in fl if f["etapa"] < 0),
                       "en_curso": sum(1 for f in fl if 0 <= f["etapa"] < 8),
                       "decisiones": sum(f["difs_pendientes"] for f in fl)}
    try:
        from .. import parte as P
        out["partes"] = [{k: p_.get(k) for k in ("id", "ts", "agente", "flujo", "clave", "estado", "hecho", "pregunta")}
                         for p_ in P.listar(t, ultimos=8)][::-1]
    except Exception:
        out["partes"] = []
    try:
        from .. import mensajes as MS
        out["mensajes"] = MS.listar(t)
    except Exception:
        out["mensajes"] = []
    prog = []
    for p in glob.glob(os.path.join(base, "progreso", "*.json")):
        x = _leer_json(p)
        if x and _vivo(x.get("pid")):
            prog.append(x)
    out["en_curso"] = prog
    out["bitacora"] = [{k: e.get(k) for k in ("ts", "agente", "accion", "estado", "flujo", "clave", "duracion_s", "error")}
                       for e in _cola(os.path.join(base, "bitacora.jsonl"), 12)][::-1]
    return out


def estado():
    from ..acceso import rocket
    try:
        ck = rocket.estado_cookie()
    except Exception as e:
        ck = {"cookies": [], "aviso": str(e)}
    sesiones = []
    limite = time.time() - VENTANA_H * 3600
    trabajos = set()
    for p in glob.glob(os.path.join(BASE, "sesiones", "*.json")):
        if os.path.getmtime(p) < limite:
            continue
        s = _leer_json(p)
        if not s:
            continue
        ev = _cola(os.path.join(BASE, "eventos", f"{s['session_id']}.jsonl"), 60)
        abiertos = {}
        for e in ev:          # herramientas en curso: Pre sin su Post (un fin de turno cierra lo del coordinador)
            if e["evento"] == "Stop":
                abiertos = {k: v for k, v in abiertos.items() if v.get("agente") or v.get("fondo")}
                continue
            k = (e.get("herramienta"), e.get("comando") or e.get("descripcion") or e.get("pregunta"), e.get("agente_id"))
            if e["evento"] == "PreToolUse":
                abiertos[k] = e
            elif e["evento"] == "PostToolUse":
                abiertos.pop(k, None)
        espera = [e for e in abiertos.values() if e.get("herramienta") == "AskUserQuestion"]
        s["en_curso"] = [e for e in abiertos.values() if e.get("herramienta") != "AskUserQuestion"][-8:]
        s["pregunta"] = espera[-1].get("pregunta") if espera else None
        s["eventos"] = [e for e in ev if e.get("evento") in ("PreToolUse", "SubagentStart", "SubagentStop", "Stop")][-15:][::-1]
        s["segundos_sin_actividad"] = int(time.time() - os.path.getmtime(p))
        s["ave"] = s.get("ave") or {"emoji": "🐦", "nombre": s["session_id"][:6]}
        s["agentes"] = [dict(a, activo=True) for a in (s.get("agentes_activos") or {}).values()] + \
                       [dict(a, activo=False) for a in (s.get("terminados") or [])[-4:]]
        if os.environ.get("PC_PANEL_VER_PRUEBAS") != "1":
            s["trabajos"] = [t for t in s.get("trabajos") or [] if not t.startswith("_")]
        trabajos.update(s.get("trabajos") or [])
        sesiones.append(s)
    sesiones.sort(key=lambda s: s.get("inicio_utc") or "")
    return {"ahora_utc": _ahora().isoformat(timespec="seconds"), "cookies": ck, "etapas": ETAPAS,
            "sesiones": sesiones, "trabajos": {t: _trabajo(t) for t in sorted(trabajos)},
            "duraciones": _duraciones(),
            "vpn": "el panel no la comprueba (la VPN es frágil): se ve en los comandos de cada coordinador"}


def flujo(t, n):
    """Detalle de un flujo para el panel: su historia (quien hizo que y cuanto tardo), lo que respondieron los
    agentes, lo que esta en curso, las decisiones que esperan a una persona (sin comandos) y los mensajes listos."""
    from .. import coordinacion as K
    from .. import parte as P
    f = L.flujo(t, n)
    if not f:
        raise KeyError(n)
    claves = {o["clave"] for o in f["objetos"]}
    hist = [{k: e.get(k) for k in ("ts", "agente", "accion", "estado", "clave", "duracion_s", "error")} |
            {"detalle": json.dumps(e.get("detalle"), ensure_ascii=False, default=str)[:180] if e.get("detalle") else None}
            for e in L.leer_bitacora(t) if e.get("flujo") == n or e.get("clave") in claves][-40:][::-1]
    partes = [{k: p.get(k) for k in ("id", "ts", "agente", "estado", "hecho", "pregunta", "siguiente")} | {"cifras": p.get("cifras")}
              for p in P.listar(t) if p.get("flujo") == n or p.get("clave") in claves][::-1]
    try:
        pend = [x for x in K.pendientes(t) if x.get("flujo") == n and x["tipo"] != "SIN_ANALIZAR"]
    except Exception:
        pend = []
    decisiones = [{"tipo": x["tipo"], "titulo": x["titulo"], "tarjeta": K.tarjeta(x, t, comandos=False)} for x in pend]
    try:
        from .. import mensajes as MS
        sec = MS.secciones(t).get(n) or {}
    except Exception:
        sec = {}
    msgs = ([{"id": f"{n}_dev", "para": "desarrollo", "destino": sec.get("equipo"), "texto": sec["desarrollo"]}] if sec.get("desarrollo") else []) + \
           ([{"id": f"{n}_com", "para": "comfandi", "destino": "Comfandi", "texto": "\n\n".join(sec["comfandi"])}] if sec.get("comfandi") else [])
    en_curso = []
    for p in glob.glob(os.path.join(L.dir_lote(t), "progreso", "*.json")):
        x = _leer_json(p)
        if x and _vivo(x.get("pid")) and (f"--flujo {n}" in x.get("comando", "") or any(f"--clave {k}" in x.get("comando", "") for k in claves)):
            en_curso.append(x)
    return {"flujo": n, "historia": hist, "partes": partes, "decisiones": decisiones, "mensajes": msgs, "en_curso": en_curso,
            "tablas": [{"clave": o["clave"], "stratio": (o.get("stratio") or {}).get("ruta"), "fabric": (o.get("fabric") or {}).get("ruta")}
                       for o in f["objetos"]]}


_CLAVES_NODO = ("estado", "decision", "resultado", "semaforo", "codigo", "grupo", "version", "filas_stratio", "filas_fabric", "delta",
                "filas_afectadas", "control", "columna", "causa", "ruta", "fuente", "version_delta", "bytes", "tipo", "agente", "url",
                "head_ok", "por", "nivel", "resumen", "regla", "stratio", "fl")


def grafo(t):
    """El grafo del trabajo para dibujarlo (datos recortados)."""
    from .. import grafo as G
    g = G.construir(t, guardar=False)
    nodos = []
    for x in g["nodos"].values():
        d = {k: (v if not isinstance(v, str) else v[:160]) for k, v in x["datos"].items() if k in _CLAVES_NODO and not isinstance(v, (dict, list))}
        nodos.append({"id": x["id"], "tipo": x["tipo"], "etiqueta": x["etiqueta"][:80], "datos": d, "n_eventos": x.get("n_eventos", 0)})
    return {"trabajo": t, "construido_utc": g["construido_utc"], "conteo": g["conteo"], "nodos": nodos,
            "aristas": [{"de": e["de"], "rel": e["rel"], "a": e["a"]} for e in g["aristas"]]}


class _H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _enviar(self, cuerpo, tipo):
        b = cuerpo.encode("utf8") if isinstance(cuerpo, str) else cuerpo
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/estado"):
            try:
                self._enviar(json.dumps(estado(), ensure_ascii=False, default=str), "application/json; charset=utf-8")
            except Exception as e:
                self._enviar(json.dumps({"error": f"{type(e).__name__}: {e}"}), "application/json")
        elif self.path.startswith("/api/grafo"):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            try:
                self._enviar(json.dumps(grafo(q["t"][0]), ensure_ascii=False, default=str), "application/json; charset=utf-8")
            except Exception as e:
                self._enviar(json.dumps({"error": f"{type(e).__name__}: {e}"}), "application/json")
        elif self.path.startswith("/api/flujo"):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query)
            try:
                self._enviar(json.dumps(flujo(q["t"][0], q["f"][0]), ensure_ascii=False, default=str), "application/json; charset=utf-8")
            except Exception as e:
                self._enviar(json.dumps({"error": f"{type(e).__name__}: {e}"}), "application/json")
        elif self.path in ("/", "/index.html"):
            self._enviar(open(HTML, encoding="utf8").read(), "text/html; charset=utf-8")
        else:
            self.send_error(404)


def servir(puerto=8765):
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", puerto), _H)
    except OSError:
        print(f"el panel ya está arriba en http://localhost:{puerto}")
        return
    print(f"panel en http://localhost:{puerto}", flush=True)
    srv.serve_forever()
