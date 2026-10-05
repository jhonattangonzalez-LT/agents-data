"""Estado de un TRABAJO de validacion (1 o varios flujos): la fuente de verdad que comparten agentes y usuarios.

El LOTE ya no es la unidad de trabajo: se arma AL FINAL juntando los expedientes de los flujos aprobados
(pc/lote_final.py). Aqui "lote" en los nombres de funcion significa "trabajo" (se conserva por compatibilidad).

trabajos/<trabajo>/
  lote.json                  definicion (la llena el coordinador con el usuario)
  bitacora.jsonl             quien hizo que y cuando (varios usuarios activan agentes)
  etl/                       lanzamientos y veredictos corregidos por flujo
  rapido/<PLAT>/<clave>.json reportes de nivel 0/1
  cotejo_rapido/<clave>.json
  semaforo/<flujo>.json
  nivel2/<PLAT>/<clave>.json reportes completos (motor v15)
  cotejos/                   cotejos completos
  publicado.json             que se subio, donde, y su comprobacion HEAD
  revision/                  resumen para las compuertas + compuertas.json

Definicion de un objeto (tabla) dentro de un flujo:
  {"clave": "agrupadoras_moves_agrup",
   "stratio": {"tipo": "hdfs|pg|sftp", "ruta": "...", "desde": "fecha=2026-01-01", "patron": "..."},
   "fabric":  {"tipo": "delta|files|pg", "ruta": "silver.agrupadoras_moves_agrup"},
   "ventana_fechas": {"columna": "FECHA", "desde": "2026-01-01", "hasta": "2026-09-30"} | null,
   "llave": ["PARTNER"] | null,
   "excluir_columnas": [], "justificaciones": {}}
"""
import datetime
import fcntl
import getpass
import json
import os
import subprocess

from .config import RAIZ

GRUPOS = ("ingesta", "analitica", "orquestador")


def dir_lote(lote):
    return os.path.join(RAIZ, "trabajos", str(lote))


def usuario():
    u = os.environ.get("QA_USUARIO")
    if u:
        return u
    try:
        return subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, timeout=5).stdout.strip() or getpass.getuser()
    except Exception:
        return getpass.getuser()


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


FASES = {"inventario-roles": 1, "etl-validador": 1, "medidor-rapido-fabric": 1, "medidor-rapido-stratio": 1,
         "medidor-rapido": 1, "postgres-fabric": 1, "semaforo": 1, "gestor-descargas": 2, "medidor-completo": 2,
         "cotejador": 2, "publicador-reportes": 2, "consolidador-revision": 3, "compuerta": 3, "acta-final": 3,
         "coordinador": 0}
ESTADOS = ("INICIO", "OK", "ERROR", "AVISO", "DECISION")


def bitacora(lote, agente, accion, detalle=None, *, estado="OK", nivel=None, flujo=None, clave=None,
             duracion_s=None, salidas=None, error=None, fase=None):
    """Log de agentes (reportes_v4 · log_agentes_<lote>.jsonl). Una linea por evento. Nunca credenciales."""
    assert estado in ESTADOS, estado
    os.makedirs(dir_lote(lote), exist_ok=True)
    p = os.path.join(dir_lote(lote), "bitacora.jsonl")
    with open(p, "a+", encoding="utf8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        n = sum(1 for _ in f)
        f.seek(0, 2)
        f.write(json.dumps({"evento": f"e-{n + 1:06d}", "ts": _ahora(), "lote": str(lote), "usuario": usuario(),
                            "agente": agente, "accion": accion, "fase": fase if fase is not None else FASES.get(agente),
                            "nivel": nivel, "flujo": flujo, "clave": clave, "estado": estado,
                            "duracion_s": round(duracion_s, 2) if duracion_s is not None else None,
                            "detalle": detalle, "salidas": salidas or [], "error": error},
                           ensure_ascii=False, default=str) + "\n")


def leer_bitacora(lote):
    p = os.path.join(dir_lote(lote), "bitacora.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    for ln in open(p, encoding="utf8"):
        if ln.strip():
            e = json.loads(ln)
            if "evento" not in e:          # formato anterior: se normaliza al leer
                e = {"evento": None, "ts": e.get("utc"), "lote": str(lote), "usuario": e.get("usuario"),
                     "agente": e.get("agente"), "accion": e.get("accion"), "fase": FASES.get(e.get("agente")),
                     "nivel": None, "flujo": None, "clave": None, "estado": "OK", "duracion_s": None,
                     "detalle": e.get("detalle"), "salidas": [], "error": None}
            out.append(e)
    for i, e in enumerate(out, 1):
        e["evento"] = e.get("evento") or f"e-{i:06d}"
    return out


def guardar(lote, rel, doc):
    p = os.path.join(dir_lote(lote), rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + f".{os.getpid()}.tmp"
    json.dump(doc, open(tmp, "w"), indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, p)
    return p


def leer(lote, rel, defecto=None):
    p = os.path.join(dir_lote(lote), rel)
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else defecto


def crear(lote, responsable_acta, descripcion="", fecha_entrega=None, pruebas=False):
    if leer(lote, "lote.json"):
        raise FileExistsError(f"el lote {lote} ya existe")
    doc = {"lote": str(lote), "descripcion": descripcion, "creado_utc": _ahora(), "creado_por": usuario(),
           "responsable_acta": responsable_acta, "fecha_entrega": fecha_entrega, "pruebas": bool(pruebas), "flujos": []}
    guardar(lote, "lote.json", doc)
    bitacora(lote, "coordinador", "crear_lote", {"responsable_acta": responsable_acta})
    return doc


def agregar_flujo(lote, nombre_fabric, grupo, objetos=None, nombre_stratio=None, fl=None, orquestador=None,
                  dependencias=None, notas=None):
    assert grupo in GRUPOS, grupo
    d = leer(lote, "lote.json")
    if not d:
        raise FileNotFoundError(f"no existe el lote {lote}")
    d["flujos"] = [f for f in d["flujos"] if f["nombre_fabric"] != nombre_fabric]
    d["flujos"].append({"nombre_fabric": nombre_fabric, "nombre_stratio": nombre_stratio, "fl": fl,
                        "grupo": grupo, "orquestador": orquestador, "dependencias": dependencias or [],
                        "objetos": objetos or [], "notas": notas, "agregado_por": usuario(), "agregado_utc": _ahora()})
    guardar(lote, "lote.json", d)
    bitacora(lote, "coordinador", "agregar_flujo", {"flujo": nombre_fabric, "grupo": grupo, "objetos": len(objetos or [])})
    return d


def flujo(lote, nombre):
    return next((f for f in leer(lote, "lote.json")["flujos"] if f["nombre_fabric"] == nombre), None)


def objetos(lote):
    for f in leer(lote, "lote.json")["flujos"]:
        for o in f["objetos"]:
            yield f, o


def tablero(lote):
    """Estado de cada flujo y objeto en cada etapa (lo que el coordinador muestra al usuario)."""
    d = leer(lote, "lote.json")
    filas = []
    for f in d["flujos"]:
        n = f["nombre_fabric"]
        etl = leer(lote, f"etl/veredictos/{n}.json")
        sem = leer(lote, f"semaforo/{n}.json")
        for o in f["objetos"] or [{"clave": "(orquestador)"}]:
            k = o["clave"]
            cr = leer(lote, f"cotejo_rapido/{k}.json")
            filas.append({
                "flujo": n, "grupo": f["grupo"], "clave": k,
                "etl": (etl or {}).get("resumen", {}).get("estado_corrida") if etl else None,
                "rapido_stratio": os.path.exists(os.path.join(dir_lote(lote), f"rapido/STRATIO/{k}.json")),
                "rapido_fabric": os.path.exists(os.path.join(dir_lote(lote), f"rapido/FABRIC/{k}.json")),
                "cotejo_rapido": (cr or {}).get("resultado_rapido"),
                "semaforo": (sem or {}).get("estado"),
                "nivel2_stratio": os.path.exists(os.path.join(dir_lote(lote), f"nivel2/STRATIO/{k}.json")),
                "nivel2_fabric": os.path.exists(os.path.join(dir_lote(lote), f"nivel2/FABRIC/{k}.json")),
                "cotejo_completo": (leer(lote, f"cotejos/indice.json", {}) or {}).get(k, {}).get("resultado")})
    return filas
