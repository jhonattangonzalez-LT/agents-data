"""Registro de mejoras: cuando algo del proceso se mejora (un agente, una herramienta, una regla), se anota y se
avisa para compartirlo con el equipo. No es algo que deba pasar siempre; cuando pasa, no se pierde.

  python -m pc mejora registrar --que "…" --por-que "…" --archivos pc/x.py,.claude/agents/y.md
  python -m pc mejora pendientes        mejoras sin compartir + archivos del proceso cambiados sin registrar
  python -m pc mejora compartida --id M-003 [--commit abc123]

docs/MEJORAS.md es el registro legible; docs/mejoras.json el estado (SIN_COMPARTIR / COMPARTIDA).
"""
import datetime
import json
import os
import subprocess

from . import lote as L
from .config import RAIZ

J = os.path.join(RAIZ, "docs", "mejoras.json")
MD = os.path.join(RAIZ, "docs", "MEJORAS.md")
DEL_PROCESO = ("pc/", ".claude/agents/", "config/", "CLAUDE.md", "README.md", "docs/REPORTES_V4.md")


def _leer():
    return json.load(open(J, encoding="utf8")) if os.path.exists(J) else []


def _md(m):
    out = ["# Mejoras del proceso", "",
           "Cada mejora se comparte con el equipo (commit + push al repositorio). `SIN_COMPARTIR` = falta hacerlo.", ""]
    for x in reversed(m):
        out += [f"## {x['id']} · {x['fecha'][:10]} · {x['estado']}", "", f"**Qué:** {x['que']}", "", f"**Por qué:** {x['por_que']}", "",
                f"**Archivos:** {', '.join('`' + a + '`' for a in x['archivos']) or '—'} · por {x['autor']}"
                + (f" · compartida en {x['commit']}" if x.get("commit") else ""), ""]
    open(MD, "w", encoding="utf8").write("\n".join(out) + "\n")


def registrar(que, por_que, archivos=()):
    m = _leer()
    x = {"id": f"M-{len(m) + 1:03d}", "fecha": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
         "que": que, "por_que": por_que, "archivos": list(archivos), "autor": L.usuario(), "estado": "SIN_COMPARTIR"}
    m.append(x)
    json.dump(m, open(J, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    _md(m)
    return x


def compartida(id_, commit=None):
    m = _leer()
    for x in m:
        if x["id"] == id_:
            x["estado"], x["commit"] = "COMPARTIDA", commit
    json.dump(m, open(J, "w", encoding="utf8"), indent=1, ensure_ascii=False)
    _md(m)


def sin_registrar():
    """Archivos del proceso modificados en el repositorio local que no tienen una mejora registrada."""
    try:
        r = subprocess.run(["git", "-C", RAIZ, "status", "--porcelain"], capture_output=True, text=True, timeout=20)
    except Exception:
        return []
    cambiados = [ln[3:].strip() for ln in r.stdout.splitlines() if ln.strip()]
    cambiados = [c for c in cambiados if c.startswith(DEL_PROCESO) and not c.startswith("docs/mejoras")]
    cubiertos = {a for x in _leer() if x["estado"] == "SIN_COMPARTIR" for a in x["archivos"]}
    return [c for c in cambiados if c not in cubiertos]


def pendientes():
    return {"sin_compartir": [x for x in _leer() if x["estado"] == "SIN_COMPARTIR"], "cambios_sin_registrar": sin_registrar()}
