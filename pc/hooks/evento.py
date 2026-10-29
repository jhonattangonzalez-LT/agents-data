#!/usr/bin/env python3
"""Hook de Claude Code (proyecto): agrega UNA linea por evento y sale. Nunca bloquea ni imprime al chat,
salvo en SessionStart (una linea con el enlace del panel) y, en PostToolUse del coordinador, un aviso de consumo
(additionalContext, solo para el modelo) la primera vez que el contexto cruza cada umbral de config/consumo.json.

Escribe en ~/.cache/pc/:
  sesiones/<session_id>.json   un coordinador: cwd, inicio, ultimo evento, activo, trabajos que toco
  eventos/<session_id>.jsonl   que agente, que comando de pc, modelo, duracion y resultado

Solo biblioteca estandar y sin importar pc: tiene que tardar milisegundos.
Uso (en .claude/settings.json): python3 pc/hooks/evento.py <Evento>
"""
import datetime
import json
import os
import re
import socket
import subprocess
import sys
import time

BASE = os.path.join(os.path.expanduser("~"), ".cache", "pc")
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PUERTO = int(os.environ.get("PC_PANEL_PUERTO", "8765"))
_RE_TRABAJO = re.compile(r"--(?:trabajo|lote)[ =]([\w.\-]+)")
_RE_PC = re.compile(r"-m\s+pc\s+(\w+)(?:\s+(\w+))?")
_RE_FLUJO = re.compile(r"--flujos?[ =]([\w.\-,]+)")
_RE_CLAVE = re.compile(r"--clave[ =]([\w.\-]+)")
AVES = [("🦜", "Loro"), ("🦉", "Búho"), ("🦅", "Águila"), ("🐧", "Pingüino"), ("🦩", "Flamenco"), ("🦆", "Pato"),
        ("🕊️", "Paloma"), ("🦚", "Pavo real"), ("🐤", "Pollito"), ("🐦", "Gorrión"), ("🦢", "Cisne"), ("🐓", "Gallo")]


def ave(sid):
    """Ave fija de un coordinador: la siguiente libre entre las sesiones abiertas (se guarda en su archivo)."""
    usadas = set()
    for p in os.listdir(os.path.join(BASE, "sesiones")) if os.path.isdir(os.path.join(BASE, "sesiones")) else []:
        if p.startswith(sid):
            continue
        try:
            x = json.load(open(os.path.join(BASE, "sesiones", p), encoding="utf8"))
            if x.get("activo") and time.time() - os.path.getmtime(os.path.join(BASE, "sesiones", p)) < 12 * 3600:
                usadas.add(x.get("ave", {}).get("nombre"))
        except Exception:
            pass
    libres = [a for a in AVES if a[1] not in usadas] or AVES
    e, n = libres[int(sid.replace("-", "")[:8] or "0", 16) % len(libres)] if re.fullmatch(r"[0-9a-f-]+", sid) else libres[0]
    return {"emoji": e, "nombre": n}


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _modelo(agente):
    """Modelo declarado en .claude/agents/<agente>.md (el panel lo muestra)."""
    try:
        for ln in open(os.path.join(RAIZ, ".claude", "agents", f"{agente}.md"), encoding="utf8"):
            if ln.startswith("model:"):
                return ln.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _contexto(ruta):
    """Tokens de contexto de la última respuesta del modelo: lee solo los últimos 256 KB de la transcripción."""
    try:
        with open(ruta, "rb") as f:
            f.seek(max(0, os.path.getsize(ruta) - 262144))
            for ln in reversed(f.read().decode("utf8", "replace").splitlines()):
                if '"usage"' in ln and '"assistant"' in ln:
                    u = (json.loads(ln).get("message") or {}).get("usage") or {}
                    return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    except Exception:
        pass
    return None


def _umbrales():
    try:
        return json.load(open(os.path.join(RAIZ, "config", "consumo.json"), encoding="utf8"))["umbrales"]["contexto_aviso_tokens"]
    except Exception:
        return [250000, 500000, 750000]


def _panel_arriba():
    try:
        with socket.create_connection(("127.0.0.1", PUERTO), timeout=0.2):
            return True
    except OSError:
        return False


def _levantar_panel():
    py = os.path.join(os.path.expanduser("~"), "Projects", ".venv", "bin", "python")
    py = py if os.path.exists(py) else sys.executable
    os.makedirs(os.path.join(BASE, "logs"), exist_ok=True)
    subprocess.Popen([py, "-m", "pc", "panel", "--puerto", str(PUERTO)], cwd=RAIZ, start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=open(os.path.join(BASE, "logs", "panel.log"), "a"),
                     stderr=subprocess.STDOUT)


def main():
    ev = sys.argv[1] if len(sys.argv) > 1 else "?"
    try:
        e = json.load(sys.stdin)
    except Exception:
        e = {}
    sid = e.get("session_id") or "sin-sesion"
    for d in ("sesiones", "eventos"):
        os.makedirs(os.path.join(BASE, d), exist_ok=True)
    ps = os.path.join(BASE, "sesiones", f"{sid}.json")
    try:
        ses = json.load(open(ps, encoding="utf8"))
    except Exception:
        ses = {"session_id": sid, "cwd": e.get("cwd"), "inicio_utc": _ahora(), "trabajos": [], "agentes_activos": {}}
    if not ses.get("ave"):
        ses["ave"] = ave(sid)
    ses["ultimo_utc"] = _ahora()
    ses["activo"] = ev not in ("SessionEnd",)
    ses["esperando_persona"] = ev == "Stop"
    linea = {"ts": _ahora(), "t": time.time(), "evento": ev}
    agente = e.get("agent_type") or e.get("subagent_type")
    if agente or e.get("agent_id"):
        linea.update(agente=agente, agente_id=e.get("agent_id"), modelo=_modelo(agente) if agente else None)
    if ev in ("PreToolUse", "PostToolUse"):
        ti = e.get("tool_input") or {}
        linea["herramienta"] = e.get("tool_name")
        if e.get("tool_name") == "Bash":
            cmd = ti.get("command") or ""
            m = _RE_PC.search(cmd)
            if m:
                linea["pc"] = " ".join(x for x in m.groups() if x)
            t = _RE_TRABAJO.search(cmd)
            if t and os.path.exists(os.path.join(RAIZ, "trabajos", t.group(1), "lote.json")):
                linea["trabajo"] = t.group(1)
                if t.group(1) not in ses["trabajos"]:
                    ses["trabajos"].append(t.group(1))
            linea["comando"] = cmd[:240]
            fl, cl = _RE_FLUJO.search(cmd), _RE_CLAVE.search(cmd)
            if fl:
                linea["flujo"] = fl.group(1)
            if cl:
                linea["clave"] = cl.group(1)
            linea["fondo"] = bool(ti.get("run_in_background"))
        elif e.get("tool_name") in ("Agent", "Task"):
            linea["lanza"] = ti.get("subagent_type") or "general"
            linea["descripcion"] = (ti.get("description") or "")[:120]
            linea["modelo"] = ti.get("model") or _modelo(ti.get("subagent_type") or "")
            if ev == "PreToolUse":      # el encargo que le da el coordinador: lo vera el panel como mensaje
                ses.setdefault("encargos", {})[linea["lanza"]] = {"descripcion": linea["descripcion"], "ts": _ahora(),
                                                                  "prompt": (ti.get("prompt") or "")[:300]}
        elif e.get("tool_name") == "AskUserQuestion":
            qs = ti.get("questions") or []
            linea["pregunta"] = (qs[0].get("question") if qs else "")[:200]
            ses["esperando_persona"] = ev == "PreToolUse"
        if ev == "PostToolUse":
            r = e.get("tool_response")
            if isinstance(r, dict):
                linea["error"] = bool(r.get("is_error") or r.get("interrupted"))
    if ev == "SubagentStart" and agente:
        enc = (ses.get("encargos") or {}).get(agente) or {}
        ses["agentes_activos"][e.get("agent_id") or agente] = {"agente": agente, "inicio_utc": _ahora(), "modelo": _modelo(agente),
                                                              "encargo": enc.get("descripcion")}
    if ev == "PreToolUse" and agente and e.get("agent_id") in ses["agentes_activos"]:
        x = ses["agentes_activos"][e["agent_id"]]
        x.update({k: linea[k] for k in ("pc", "flujo", "clave", "trabajo") if linea.get(k)})
        x["ultimo_utc"] = _ahora()
    if ev == "SubagentStop":
        x = ses["agentes_activos"].pop(e.get("agent_id") or agente or "", None)
        if x:
            x["fin_utc"] = _ahora()
            ses["terminados"] = (ses.get("terminados") or [])[-7:] + [x]
    aviso = None
    if ev == "PostToolUse" and not e.get("agent_id") and e.get("transcript_path"):
        # consumo en vivo del coordinador: el panel lo muestra y, una vez por umbral, se le avisa (no bloquea nada)
        ctx = _contexto(e["transcript_path"])
        if ctx:
            ses["contexto_tokens"] = ctx
            cruzados = [u for u in _umbrales() if ctx >= u]
            if cruzados and cruzados[-1] > (ses.get("contexto_avisado") or 0):
                ses["contexto_avisado"] = cruzados[-1]
                aviso = (f"CONSUMO: el contexto de esta sesión va en {ctx // 1000} k tokens (umbral {cruzados[-1] // 1000} k); cada turno "
                         "lo relee entero. En el próximo punto de corte (flujo cerrado, decisión tomada, antes de una espera larga) "
                         "propón a la persona /compact o cerrar y retomar con `pc trabajo siguiente` (el estado está en disco). "
                         "Detalle: `python -m pc consumo vivo`.")
            elif ctx < (ses.get("contexto_avisado") or 0) // 2:
                ses["contexto_avisado"] = 0     # se compactó: vuelve a avisar cuando crezca
    if ev == "SessionStart":
        linea["fuente"] = e.get("source")
        if not _panel_arriba():
            try:
                _levantar_panel()
            except Exception:
                pass
    tmp = ps + f".{os.getpid()}.tmp"
    json.dump(ses, open(tmp, "w", encoding="utf8"), ensure_ascii=False)
    os.replace(tmp, ps)
    with open(os.path.join(BASE, "eventos", f"{sid}.jsonl"), "a", encoding="utf8") as f:
        f.write(json.dumps(linea, ensure_ascii=False) + "\n")
    if aviso:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": aviso}}, ensure_ascii=False))
    if ev == "SessionStart":
        a_ = ses["ave"]
        print(f"Eres el coordinador {a_['emoji']} {a_['nombre']} (sesión {sid[:8]}). Preséntate así al usuario. "
              f"Panel en vivo: http://localhost:{PUERTO}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
