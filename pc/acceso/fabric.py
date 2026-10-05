"""API de Fabric y token de OneLake desde el CLI `fab` ya autenticado.

Los tokens duran ~1 h: se renuevan cada 40 min y ante un 401. Nunca se imprimen.
"""
import json
import random
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from ..config import FAB

_L = threading.Lock()
_T = {}          # alcance -> (token, instante)
ALCANCES = {"fabric": "SCOPE_FABRIC_DEFAULT", "onelake": "SCOPE_ONELAKE_DEFAULT"}
RENOVAR_S = 2400


class SinSesion(RuntimeError):
    """El CLI fab no tiene sesion: pedir al usuario `! fab auth login`."""


def token(alcance="fabric", renovar=False):
    with _L:
        t = _T.get(alcance)
        if t and not renovar and time.time() - t[1] < RENOVAR_S:
            return t[0]
        fab = shutil.which("fab")
        if not fab:
            raise SinSesion("no esta instalado el CLI fab")
        py = open(fab).readline().strip()[2:]
        g = ("from fabric_cli.core import fab_constant as con\n"
             "from fabric_cli.core.fab_auth import FabAuth\n"
             f"print(FabAuth().get_access_token(con.{ALCANCES[alcance]}, interactive_renew=False) or '')")
        for i in range(6):
            r = subprocess.run([py, "-c", g], capture_output=True, text=True, timeout=180)
            tok = [l for l in r.stdout.splitlines() if l.startswith("ey")]
            if tok:
                _T[alcance] = (tok[-1], time.time())
                return tok[-1]
            if "login" in (r.stderr or "").lower() or "not logged" in (r.stderr or "").lower():
                raise SinSesion("fab sin sesion: el usuario debe correr `! fab auth login`")
            time.sleep(3 + random.random() * 4 * (i + 1))
        raise SinSesion(f"no se obtuvo token ({alcance}): {(r.stderr or '')[:200]}")


def invalidar():
    with _L:
        _T.clear()


def bruta(ruta, metodo="GET", cuerpo=None, timeout=180):
    """(codigo, json|texto, cabeceras). Un 401 renueva el token y repite una vez."""
    for intento in (0, 1):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else (b"" if metodo == "POST" else None)
        cab = {"Authorization": f"Bearer {token('fabric', renovar=intento == 1)}"}
        if cuerpo is not None:
            cab["Content-Type"] = "application/json"
        elif metodo == "POST":
            cab["Content-Length"] = "0"
        req = urllib.request.Request(f"{FAB['api']}{ruta}", data=datos, headers=cab, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as x:
                b = x.read().decode()
                return x.status, (json.loads(b) if b.strip() else {}), dict(x.headers)
        except urllib.error.HTTPError as e:
            if e.code == 401 and intento == 0:
                continue
            if e.code == 429 and intento == 0:
                time.sleep(float(e.headers.get("Retry-After") or 20))
                continue
            return e.code, e.read().decode()[:2000], dict(e.headers)
    return 0, "sin respuesta", {}


def api(ruta, metodo="GET", cuerpo=None, timeout=180):
    """Sigue las operaciones asincronas (202 con x-ms-operation-id)."""
    c, b, h = bruta(ruta, metodo, cuerpo, timeout)
    op = h.get("x-ms-operation-id")
    if c == 202 and op:
        espera = float(h.get("Retry-After") or 2)
        for _ in range(150):
            time.sleep(espera)
            c2, b2, _ = bruta(f"/operations/{op}")
            if c2 != 200:
                return c2, b2
            est = (b2 or {}).get("status")
            if est == "Succeeded":
                r = bruta(f"/operations/{op}/result")
                return (r[0], r[1]) if r[0] == 200 else (200, b2)
            if est in ("Failed", "Undefined"):
                return 0, f"operacion {est}: {b2}"
        return 0, "la operacion no termino a tiempo"
    return c, b


def paginar(ruta, clave="value"):
    out, tok = [], None
    while True:
        r = ruta + ((("&" if "?" in ruta else "?") + "continuationToken=" + urllib.parse.quote(tok)) if tok else "")
        c, b = api(r)
        if c != 200:
            raise RuntimeError(f"{ruta}: HTTP {c} · {str(b)[:300]}")
        out += (b or {}).get(clave, [])
        tok = (b or {}).get("continuationToken")
        if not tok:
            return out


def items(ws, tipo=None):
    return paginar(f"/workspaces/{ws}/items" + (f"?type={tipo}" if tipo else ""))


def workspaces():
    return paginar("/workspaces")


def buscar_item(nombre, tipos=("DataPipeline", "SparkJobDefinition", "Notebook"), ws=None):
    """Busca por nombre exacto en los workspaces dados (o en todos los visibles)."""
    wss = [ws] if ws else [w["id"] for w in workspaces()]
    hall = []
    for w in wss:
        try:
            for i in items(w):
                if i["displayName"] == nombre and i["type"] in tipos:
                    hall.append(dict(i, workspaceId=w))
        except RuntimeError:
            continue
    orden = {t: n for n, t in enumerate(tipos)}
    return sorted(hall, key=lambda i: orden.get(i["type"], 99))


def definicion(ws, item_id, formato=None):
    """{ruta_parte: bytes}. Para pipelines la parte util es pipeline-content.json."""
    import base64
    ruta = f"/workspaces/{ws}/items/{item_id}/getDefinition" + (f"?format={formato}" if formato else "")
    c, b = api(ruta, "POST")
    if c != 200 or not isinstance(b, dict):
        raise RuntimeError(f"getDefinition {item_id}: HTTP {c} {str(b)[:300]}")
    return {p["path"]: base64.b64decode(p["payload"]) for p in b["definition"]["parts"]}


def pipeline_json(ws, item_id):
    return json.loads(definicion(ws, item_id)["pipeline-content.json"])


def _partes(partes):
    import base64
    return [{"path": k, "payload": base64.b64encode(v if isinstance(v, bytes) else v.encode()).decode(),
             "payloadType": "InlineBase64"} for k, v in partes.items()]


def crear_item(ws, nombre, tipo, partes, descripcion="", formato=None):
    cuerpo = {"displayName": nombre, "type": tipo, "description": descripcion,
              "definition": dict({"parts": _partes(partes)}, **({"format": formato} if formato else {}))}
    return api(f"/workspaces/{ws}/items", "POST", cuerpo)


def actualizar_definicion(ws, item_id, partes, formato=None):
    cuerpo = {"definition": dict({"parts": _partes(partes)}, **({"format": formato} if formato else {}))}
    return api(f"/workspaces/{ws}/items/{item_id}/updateDefinition", "POST", cuerpo)


def borrar_item(ws, item_id):
    c, b, _ = bruta(f"/workspaces/{ws}/items/{item_id}", "DELETE")
    return c, b


# ----------------------------------------------------------------- trabajos (jobs)
TERMINALES = ("Completed", "Failed", "Cancelled", "Deduped")


def lanzar(ws, item_id, tipo_job, parametros=None, cuerpo=None):
    """Lanza un job (Pipeline, RunNotebook, sparkjob). Devuelve el id de la corrida."""
    cuerpo = cuerpo if cuerpo is not None else ({"executionData": {"parameters": parametros}} if parametros else {})
    for intento in range(4):
        c, b, h = bruta(f"/workspaces/{ws}/items/{item_id}/jobs/instances?jobType={tipo_job}", "POST", cuerpo)
        if c == 202:
            return (h.get("Location") or "").rstrip("/").split("/")[-1]
        time.sleep(15 * (intento + 1))
    raise RuntimeError(f"no se pudo lanzar {item_id}: HTTP {c} {str(b)[:300]}")


def corrida(ws, item_id, run_id):
    c, b = api(f"/workspaces/{ws}/items/{item_id}/jobs/instances/{run_id}")
    return b if c == 200 and isinstance(b, dict) else {"status": f"HTTP {c}", "detalle": str(b)[:300]}


def esperar(ws, item_id, run_id, max_s=7200, cada=20, avisar=None):
    t0 = time.time()
    while time.time() - t0 < max_s:
        r = corrida(ws, item_id, run_id)
        if avisar:
            avisar(r.get("status"), round(time.time() - t0))
        if r.get("status") in TERMINALES:
            r["segundos_espera"] = round(time.time() - t0)
            return r
        time.sleep(cada)
    return {"status": "TIMEOUT", "id": run_id}


def corridas(ws, item_id):
    c, b = api(f"/workspaces/{ws}/items/{item_id}/jobs/instances")
    v = (b or {}).get("value", []) if isinstance(b, dict) else []
    return sorted(v, key=lambda r: r.get("startTimeUtc") or "", reverse=True)


def portal_archivo(ruta_files):
    """Enlace al portal para un archivo de Files/ del lakehouse transversal."""
    sel = urllib.parse.quote(ruta_files if ruta_files.startswith("Files/") else f"Files/{ruta_files}", safe="")
    return (f"{FAB['portal']}/groups/{FAB['ws_datalake']}/lakehouses/{FAB['lh_transversal']}"
            f"?ctid={FAB['tenant']}&experience=fabric-developer&selectedPath={sel}&extensionScenario=openArtifact")
