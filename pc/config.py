"""Lee config/pipeline.json y config/controles.json. Unico sitio con rutas e ids."""
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cargar(n):
    with open(os.path.join(RAIZ, "config", n), encoding="utf8") as f:
        return json.load(f)


CFG = _cargar("pipeline.json")
CONTROLES = _cargar("controles.json")
FAB = CFG["fabric"]
PAR = CFG["paralelismo"]


def ruta(p):
    """~ se expande; una ruta relativa se toma desde la raiz del repositorio."""
    p = os.path.expanduser(p)
    return p if os.path.isabs(p) else os.path.join(RAIZ, p)


def secreto_ruta(nombre):
    """Credenciales fuera del repo. PC_SECRETOS_DIR permite guardarlas en otra carpeta (mismo nombre de archivo)."""
    p = os.path.expanduser(CFG["secretos"][nombre])
    d = os.environ.get("PC_SECRETOS_DIR")
    return os.path.join(os.path.expanduser(d), os.path.basename(p)) if d else p


def control(cod):
    return next((c for c in CONTROLES["controles"] if c["codigo"] == cod), None)


def criterio(cod, grupo):
    c = control(cod)
    return c.get(grupo, "no_aplica") if c else "no_aplica"
