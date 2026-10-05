"""_delta_log leido en remoto (sin bajar la tabla): archivos vigentes, esquema y commits.

Es la fuente del nivel 0 (esquema, version, commits dentro de la ventana de la corrida) y la
lista de parquet vigentes para el nivel 1 (pies). El registro Delta manda sobre la fecha del
archivo: el commitInfo.timestamp dice que corrida escribio la tabla.
"""
import datetime
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor

from ..acceso import onelake as ol
from ..config import PAR

_RE_JSON = re.compile(r"(\d{20})\.json$")
_RE_CP = re.compile(r"(\d{20})\.checkpoint(\.\d+\.\d+)?\.parquet$")


def resolver_tabla(nombre, ws=None, lh=None):
    """'silver.sap_pscd_DFKKOP' -> 'Tables/silver/sap_pscd_dfkkop' respetando la caja REAL en OneLake.
    Acepta tambien 'Tables/...'. Devuelve None si no existe."""
    if nombre.startswith("Tables/"):
        partes = nombre.split("/")[1:]
    else:
        partes = nombre.replace("`", "").split(".")
    if len(partes) == 1:
        partes = ["dbo"] + partes
    esq, tab = partes[0], partes[-1]
    for e in ol.listar("Tables", recursivo=False, ws=ws, lh=lh):
        if e["isDirectory"] and e["name"].split("/")[-1].lower() == esq.lower():
            for t in ol.listar(e["name"], recursivo=False, ws=ws, lh=lh):
                if t["isDirectory"] and t["name"].split("/")[-1].lower() == tab.lower():
                    return t["name"]
    return None


def _ms_iso(ms):
    if ms is None:
        return None
    return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).isoformat(timespec="seconds")


def _mapa(x):
    """pyarrow entrega los MAP del checkpoint como lista de pares: a dict."""
    if isinstance(x, list) and all(isinstance(t, (tuple, list)) and len(t) == 2 for t in x):
        return {k: v for k, v in x}
    return x if x is not None else {}


def leer_log(base, ws=None, lh=None, todos_los_commits=True):
    """base = 'Tables/<esquema>/<tabla>'. Devuelve dict con vigentes, metaData, commits, version."""
    import pyarrow.parquet as pq
    arch = [p for p in ol.listar(f"{base}/_delta_log", recursivo=False, ws=ws, lh=lh) if not p["isDirectory"]]
    if not arch:
        raise FileNotFoundError(f"sin _delta_log en {base}")
    jsons = sorted((int(m.group(1)), p) for p in arch if (m := _RE_JSON.search(p["name"])))
    cps = {}
    for p in arch:
        m = _RE_CP.search(p["name"])
        if m:
            cps.setdefault(int(m.group(1)), []).append(p)
    vigentes, meta, proto = {}, {}, {}
    desde = -1
    if cps:
        v = max(cps)
        for p in cps[v]:
            t = pq.read_table(io.BytesIO(ol.leer(p["name"], ws, lh)))
            cols = t.column_names
            for fila in t.to_pylist():
                if fila.get("add"):
                    vigentes[fila["add"]["path"]] = fila["add"]
                if "metaData" in cols and fila.get("metaData"):
                    meta = fila["metaData"]
                if "protocol" in cols and fila.get("protocol"):
                    proto = fila["protocol"]
        desde = v
    # commits: los posteriores al checkpoint cambian los vigentes; todos dan el historial
    leer_jsons = [(v, p) for v, p in jsons if v > desde or todos_los_commits]

    def _leer(vp):
        v, p = vp
        return v, ol.leer(p["name"], ws, lh).decode("utf8")

    with ThreadPoolExecutor(PAR["onelake_hilos"]) as ex:
        textos = dict(ex.map(_leer, leer_jsons))
    commits = []
    for v in sorted(textos):
        ci = None
        for ln in textos[v].splitlines():
            if not ln.strip():
                continue
            a = json.loads(ln)
            if v > desde:
                if "add" in a:
                    vigentes[a["add"]["path"]] = a["add"]
                if "remove" in a:
                    vigentes.pop(a["remove"]["path"], None)
                if "metaData" in a:
                    meta = a["metaData"]
                if "protocol" in a:
                    proto = a["protocol"]
            if "commitInfo" in a:
                ci = a["commitInfo"]
        if ci is not None:
            commits.append({"version": v, "utc": _ms_iso(ci.get("timestamp")), "operacion": ci.get("operation"),
                            "metricas": ci.get("operationMetrics") or {},
                            "parametros": {k: ci.get("operationParameters", {}).get(k)
                                           for k in ("mode", "predicate", "partitionBy")
                                           if ci.get("operationParameters", {}).get(k) is not None}})
    version = max([v for v, _ in jsons] + ([desde] if desde >= 0 else []))
    esquema = json.loads(meta["schemaString"]) if meta.get("schemaString") else {"fields": []}
    meta = {k: (_mapa(v) if k in ("configuration", "format") else v) for k, v in (meta or {}).items()}
    conf = _mapa(meta.get("configuration"))
    part = meta.get("partitionColumns") or []
    if isinstance(part, str):
        part = json.loads(part)
    for a in vigentes.values():
        for k in ("partitionValues", "tags"):
            if k in a:
                a[k] = _mapa(a[k])
        if isinstance(a.get("stats"), str):
            try:
                a["stats"] = json.loads(a["stats"])
            except ValueError:
                a["stats"] = None
    return {"base": base, "version": version, "vigentes": vigentes, "esquema": esquema,
            "particiones": part, "column_mapping": conf.get("delta.columnMapping.mode"),
            "configuracion": conf, "protocolo": proto, "commits": commits,
            "ultimo_commit": commits[-1] if commits else None}


_TIPOS = {"string": "string", "long": "bigint", "integer": "int", "short": "smallint", "byte": "tinyint",
          "double": "double", "float": "float", "boolean": "boolean", "date": "date",
          "timestamp": "timestamp", "timestamp_ntz": "timestamp", "binary": "binary", "void": "void"}


def tipo_spark(t):
    if isinstance(t, dict):
        return {"struct": "struct", "array": "array", "map": "map"}.get(t.get("type"), "complejo")
    t = str(t)
    if t.startswith("decimal"):
        return t.replace(" ", "")
    return _TIPOS.get(t, t)


def columnas(log):
    """[{orden, nombre, tipo, nullable, fisico}] desde el schemaString."""
    out = []
    for i, f in enumerate(log["esquema"].get("fields", [])):
        md = f.get("metadata") or {}
        out.append({"orden": i, "nombre": f["name"], "tipo": tipo_spark(f["type"]),
                    "nullable": bool(f.get("nullable", True)),
                    "fisico": md.get("delta.columnMapping.physicalName", f["name"])})
    return out


def a_utc(t):
    """ISO con o sin zona, con 7 decimales (formato de la API de Fabric) -> datetime UTC."""
    if t is None:
        return None
    if isinstance(t, datetime.datetime):
        return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)
    s = str(t).strip().replace("Z", "+00:00")
    m = re.match(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$", s)
    if m:
        s = m.group(1) + ((m.group(2) or "")[:7].ljust(7, "0")[:7] if m.group(2) else "") + (m.group(3) or "")
        s = re.sub(r"(\.\d{6})\d", r"\1", s)
    d = datetime.datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)


def commits_en_ventana(log, inicio_utc, fin_utc, holgura_s=120):
    """Commits con escritura (no OPTIMIZE/VACUUM) dentro de [inicio - holgura, fin + holgura]."""
    sin_dato = {"OPTIMIZE", "VACUUM START", "VACUUM END", "SET TBLPROPERTIES", "FSCK"}
    h = datetime.timedelta(seconds=holgura_s)
    a, b = a_utc(inicio_utc) - h, a_utc(fin_utc) + h
    return [c for c in log["commits"]
            if c["utc"] and a <= a_utc(c["utc"]) <= b and (c["operacion"] or "") not in sin_dato]
