"""Roles REALES de entrada/salida de un flujo, desde su codigo (no desde el nombre del parametro).

Por que: en los flujos encadenados de un orquestador, el flujo que escribe una tabla y el que la lee
reciben el MISMO parametro (--xxx-output-path, --xxx-table). El ETL validator decide el rol por el
nombre de la bandera y los invierte. La fuente de verdad es el zip del flujo:
    extract.py -> spark.read.table / read.parquet / load   = ENTRADAS
    load.py    -> writeTo / saveAsTable / save / write      = SALIDAS
    migrations/001_init_schema.py suele crear solo las salidas.
Y se confirma con el _delta_log: toda salida tiene commit dentro de la ventana de la corrida.
"""
import ast
import io
import re
import zipfile

from ..acceso import onelake as ol
from ..config import FAB

NO_RUTA = re.compile(r"(user|password|secret|akv|host|port|driver|url|jdbc|mode|format|options|"
                     r"separator|delimiter|header|encoding|schema_name|partition|log_level|job_id|env|"
                     r"migrations|batch|timeout|flag)", re.I)


def _rel(n):
    return n[len("Files/"):] if n.startswith("Files/") else n


def candidatos_zip(flujo):
    """Zips cuyo nombre de carpeta corresponde al flujo ('03-moves' -> 'moves')."""
    base = re.sub(r"^\d+[a-z]?[-_]", "", flujo.strip()).replace("-", "_").lower()
    todos = [p for p in ol.listar(FAB["assets_flujos"], True) if p["name"].endswith(".zip")]
    exactos = [p for p in todos if p["name"].split("/")[-2].lower() in (flujo.lower(), base)]
    return exactos


def leer_zip(ruta):
    return zipfile.ZipFile(io.BytesIO(ol.leer(ruta)))


def _params_usados(src):
    """Atributos params.X referenciados en el codigo."""
    try:
        t = ast.parse(src)
    except SyntaxError:
        return set(re.findall(r"params\.([A-Za-z_][A-Za-z0-9_]*)", src))
    out = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "params":
            out.add(n.attr)
    return out


def _campos_params(src):
    """Campos declarados en la dataclass Params."""
    try:
        t = ast.parse(src)
    except SyntaxError:
        return []
    for n in ast.walk(t):
        if isinstance(n, ast.ClassDef) and n.name == "Params":
            return [s.target.id for s in n.body if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)]
    return []


def roles_desde_zip(z):
    nombres = z.namelist()
    def src(sufijo):
        ms = [n for n in nombres if n.endswith(sufijo)]
        return "\n".join(z.read(m).decode("utf8", "replace") for m in ms)
    ext, lod, par = src("/extract.py"), src("/load.py"), src("/params.py")
    pasos = "\n".join(z.read(n).decode("utf8", "replace") for n in nombres
                      if "/steps/" in n and n.endswith(".py"))
    mig = src("/001_init_schema.py")
    campos = _campos_params(par)
    lee, escribe = _params_usados(ext), _params_usados(lod)
    lee_pasos = {p for p in _params_usados(pasos)
                 if re.search(r"read\.(table|parquet|csv|load|format|jdbc)|spark\.table|spark\.sql", pasos)}
    modo = {c for c in campos if re.search(r"(write|output)_mode$", c)}
    entradas = sorted(p for p in (lee | lee_pasos) if not NO_RUTA.search(p.split("_")[-1]) or p.endswith(("_path", "_table")))
    salidas = sorted(p for p in escribe if not NO_RUTA.search(p.split("_")[-1]) or p.endswith(("_path", "_table")))
    en_mig = sorted(p for p in campos if p in _params_usados(mig))
    ambiguas = sorted(set(entradas) & set(salidas))
    return {"campos_params": campos, "entradas": [p for p in entradas if p not in ambiguas],
            "salidas": [p for p in salidas if p not in ambiguas], "lee_y_escribe": ambiguas,
            "params_con_modo_escritura": sorted(modo), "creadas_en_migracion": en_mig,
            "archivos": [n for n in nombres if n.endswith((".py",)) and "/steps/" not in n]}


def bandera(param):
    return param.replace("_", "-")


def corregir_validador(veredicto, roles):
    """Reasigna las entradas/salidas del veredicto del ETL validator segun el codigo.
    Devuelve {entradas, salidas, cambios, sin_rol} con las rutas reales que el validador resolvio."""
    rol_de = {bandera(p): "entrada" for p in roles["entradas"]}
    rol_de.update({bandera(p): "salida" for p in roles["salidas"]})
    rol_de.update({bandera(p): "lee_y_escribe" for p in roles["lee_y_escribe"]})
    io_ = (veredicto.get("entradas") or []) + (veredicto.get("salidas") or [])
    ent, sal, cambios, sin_rol = [], [], [], []
    for x in io_:
        b = (x.get("tipo") or "").lstrip("-")
        real = rol_de.get(b)
        item = {"bandera": b, "ruta": x.get("ruta_completa") or x.get("carpeta_real"),
                "abfss": x.get("abfss"), "rol_validador": x.get("rol"), "rol_codigo": real}
        if real is None:
            sin_rol.append(item)
            (ent if x.get("rol") == "entrada" else sal).append(item)
            continue
        if real != x.get("rol"):
            cambios.append(item)
        (sal if real in ("salida", "lee_y_escribe") else ent).append(item)
    return {"entradas": ent, "salidas": sal, "cambios": cambios, "sin_rol": sin_rol,
            "invertido": bool(cambios)}


def inventariar(flujo, zip_ruta=None, veredicto=None):
    """Roles del flujo. Si hay varios zips (silver y gold), elige el que mejor casa con las banderas
    del veredicto y reporta la ambiguedad."""
    cands = [zip_ruta] if zip_ruta else [p["name"] for p in candidatos_zip(flujo)]
    if not cands:
        return {"flujo": flujo, "estado": "SIN_CODIGO", "detalle": "no se encontro el zip en Files/assets/flows"}
    banderas = {(x.get("tipo") or "").lstrip("-") for x in
                ((veredicto or {}).get("entradas") or []) + ((veredicto or {}).get("salidas") or [])}
    evaluados = []
    for c in cands:
        r = roles_desde_zip(leer_zip(c))
        casan = len(banderas & {bandera(p) for p in r["campos_params"]}) if banderas else 0
        evaluados.append((casan, c, r))
    evaluados.sort(key=lambda t: -t[0])
    casan, ruta, r = evaluados[0]
    out = {"flujo": flujo, "estado": "OK", "zip": ruta, "capa": ruta.split("/")[-3],
           "grupo_codigo": ruta.split("/")[-4], **r,
           "zips_alternativos": [c for _, c, _ in evaluados[1:]]}
    if veredicto:
        out["correccion"] = corregir_validador(veredicto, r)
    return out


def confirmar_con_delta(correccion, inicio_utc, fin_utc):
    """Regla del acta: una tabla es salida del flujo solo si (1) esta en su load.py y (2) tiene
    commit dentro de la ventana de la corrida. Marca cada salida/entrada con lo que dice el log."""
    from ..rapido import delta_remoto as dr
    out = {"ventana": {"inicio_utc": inicio_utc, "fin_utc": fin_utc}, "salidas": [], "entradas": []}
    for rol in ("salidas", "entradas"):
        for x in correccion[rol]:
            ruta = x.get("ruta") or ""
            fila = dict(x)
            if "." in ruta and "/" not in ruta:
                try:
                    base = dr.resolver_tabla(ruta)
                    log = dr.leer_log(base) if base else None
                    en = dr.commits_en_ventana(log, inicio_utc, fin_utc) if log else []
                    fila.update(commits_en_ventana=len(en), ultimo_commit=(log or {}).get("ultimo_commit"))
                except Exception as e:  # tabla Postgres o ruta no Delta
                    fila["commits_en_ventana"] = None
                    fila["nota"] = f"no Delta: {type(e).__name__}"
            else:
                fila["commits_en_ventana"] = None
            out[rol].append(fila)
    out["salidas_sin_commit"] = [x["ruta"] for x in out["salidas"] if x.get("commits_en_ventana") == 0]
    out["entradas_con_commit"] = [x["ruta"] for x in out["entradas"] if x.get("commits_en_ventana")]
    out["roles_coherentes"] = not out["salidas_sin_commit"] and not out["entradas_con_commit"]
    return out
