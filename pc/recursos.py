"""Recursos del equipo: cuanto se le exige a ESTE computador antes de una validacion pesada.

  python -m pc recursos                      estado del equipo (RAM, CPU, carga, disco) y el perfil vigente
  python -m pc recursos --perfil maxima      fija el perfil de este equipo: maxima · moderada · promedio
  python -m pc recursos --configurar         lo observado (CPU, MHz, núcleos, RAM, disco) y las preguntas rápidas con
                                             sus opciones sugeridas, en JSON, para que el coordinador pregunte
  python -m pc recursos --perfil maxima --hilos 6 [--ram-gb 16] [--objetos 2] [--red 6]
                                             ajustes de la persona sobre el perfil (0 quita el ajuste)

Por que: nivel 2 abre DuckDB por objeto (memoria e hilos) y varios objetos a la vez; con valores fijos (8 GB, 6 hilos,
2 objetos) un equipo de 8-16 GB se congela. El perfil reparte un presupuesto de RAM y CPU del equipo entre los objetos
que corren a la vez; nunca sube los topes de las plataformas (8 hilos en Rocket y en OneLake).

El perfil es del EQUIPO, no del repositorio: se guarda en ~/.config/pc/recursos.json (PC_PERFIL lo sobreescribe).
Sin perfil guardado se usa «promedio» y el coordinador PREGUNTA cual usar antes del primer paso pesado.
Ajustes de la persona (cada equipo es distinto: 20 GB sin saber los MHz, 16 nucleos para hilos…), sobre el perfil:
  hilos    tope TOTAL de hilos de computo (DuckDB) repartido entre los objetos que corren a la vez
  ram_gb   RAM total que la medicion puede usar (se reparte entre los objetos; nunca mas que la RAM del equipo - 1 GB)
  objetos  objetos medidos a la vez · red  hilos de red por descarga (tope de plataforma: 8)
Antes de descargar, medir o cotejar, `comprobar()` mira la RAM disponible y la carga: si no alcanza, el comando se
detiene (codigo 3) y dice que preguntar; --forzar-recursos sigue igual, bajo responsabilidad de la persona.
"""
import json
import os
import shutil
import socket

ARCHIVO = os.path.join(os.path.expanduser("~"), ".config", "pc", "recursos.json")
PERFILES = {
    # presupuesto de RAM (fraccion del total), de CPU (fraccion de nucleos), objetos a la vez e hilos de red
    "maxima":   {"ram": 0.85, "cpu": 1.00, "objetos": 2, "red": 8, "texto": "capacidad máxima posible"},
    "moderada": {"ram": 0.50, "cpu": 0.60, "objetos": 1, "red": 6, "texto": "capacidad máxima moderada"},
    "promedio": {"ram": 0.35, "cpu": 0.50, "objetos": 1, "red": 4, "texto": "capacidad promedio"},
}
RESERVA_GB = 1.5          # lo que se deja libre al sistema y a las demas aplicaciones
AJUSTES = ("hilos", "ram_gb", "objetos", "red")


def _gb(b):
    return round(b / 2**30, 1)


def estado():
    """RAM total y disponible, nucleos, carga y disco libre de la cache (medido ahora)."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        total, disp = vm.total, vm.available
    except ImportError:
        total = disp = None
        try:
            mi = dict(ln.split(":", 1) for ln in open("/proc/meminfo"))
            total = int(mi["MemTotal"].split()[0]) * 1024
            disp = int(mi["MemAvailable"].split()[0]) * 1024
        except Exception:
            pass
    try:
        carga = os.getloadavg()[0]
    except (OSError, AttributeError):
        carga = None
    cpu = _cpu()
    from .config import RAIZ
    du = shutil.disk_usage(os.path.join(RAIZ, "cache") if os.path.isdir(os.path.join(RAIZ, "cache")) else RAIZ)
    return {"equipo": socket.gethostname(), "nucleos": os.cpu_count() or 1, "ram_total_gb": _gb(total) if total else None,
            "ram_disponible_gb": _gb(disp) if disp else None, "carga_1min": round(carga, 2) if carga is not None else None,
            "disco_libre_gb": _gb(du.free), **cpu}


def _cpu():
    """Modelo, nucleos fisicos y MHz maximos (de /proc y /sys; None donde el sistema no lo dice)."""
    modelo, fisicos, mhz = None, None, None
    try:
        nucleos = set()
        for b in open("/proc/cpuinfo").read().split("\n\n"):
            d = dict((k.strip(), v.strip()) for k, v in (ln.split(":", 1) for ln in b.splitlines() if ":" in ln))
            modelo = modelo or d.get("model name")
            if "core id" in d:
                nucleos.add((d.get("physical id"), d["core id"]))
        fisicos = len(nucleos) or None
    except OSError:
        pass
    try:
        mhz = int(open("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq").read()) // 1000
    except (OSError, ValueError):
        pass
    return {"cpu_modelo": modelo, "nucleos_fisicos": fisicos, "mhz_max": mhz}


def perfil_guardado():
    if os.environ.get("PC_PERFIL") in PERFILES:
        return {"perfil": os.environ["PC_PERFIL"], "origen": "PC_PERFIL"}
    try:
        d = json.load(open(ARCHIVO, encoding="utf8"))
        return d if d.get("perfil") in PERFILES else None
    except (OSError, ValueError):
        return None


def fijar(perfil=None, **ajustes):
    """Guarda el perfil y los ajustes de la persona. Lo que no se pasa se conserva; un ajuste en 0 se quita."""
    import datetime
    previo = perfil_guardado() or {}
    perfil = perfil or previo.get("perfil")
    if perfil not in PERFILES:
        raise ValueError(f"perfil {perfil}: use {', '.join(PERFILES)}")
    aj = dict(previo.get("ajustes") or {})
    for k, v in ajustes.items():
        if k not in AJUSTES or v is None:
            continue
        if v <= 0:
            aj.pop(k, None)
        else:
            aj[k] = round(float(v), 1) if k == "ram_gb" else int(v)
    os.makedirs(os.path.dirname(ARCHIVO), exist_ok=True)
    d = {"perfil": perfil, "equipo": socket.gethostname(), "ajustes": aj,
         "fijado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    json.dump(d, open(ARCHIVO, "w", encoding="utf8"), indent=1)
    return d


def limites(perfil=None, est=None):
    """Valores efectivos para este equipo: memoria e hilos de DuckDB por objeto, objetos a la vez e hilos de red."""
    pg = perfil_guardado()
    perfil = perfil or (pg or {}).get("perfil") or "promedio"
    p, est = PERFILES[perfil], est or estado()
    aj = (pg or {}).get("ajustes") or {}
    total = est["ram_total_gb"] or 8
    presupuesto = max(1.0, total * p["ram"] - (RESERVA_GB if p["ram"] < 0.8 else 0))   # la maxima no guarda reserva
    if aj.get("ram_gb"):
        presupuesto = max(1.0, min(aj["ram_gb"], total - 1))
    objetos = p["objetos"] if total >= 16 else 1          # dos DuckDB a la vez solo con 16 GB o mas
    if aj.get("objetos"):
        objetos = max(1, min(aj["objetos"], 4))
    hilos_total = aj.get("hilos") or int(est["nucleos"] * p["cpu"])
    objetos = max(1, min(objetos, hilos_total))           # cada objeto con al menos un hilo
    hilos = max(1, hilos_total // objetos)
    mem = max(2 if total >= 6 else 1, int(presupuesto / objetos))   # DuckDB desborda a disco por debajo, pero con 1 GB se arrastra
    red = min(8, aj.get("red") or p["red"])
    return {"perfil": perfil, "texto": p["texto"], "guardado": bool(pg), "ajustes": aj, "duckdb_memoria": f"{mem}GB",
            "duckdb_hilos": hilos, "hilos_total": hilos * objetos, "medicion_local_objetos": objetos,
            "onelake_hilos": red, "rocket_hilos_por_objeto": red, "presupuesto_ram_gb": round(mem * objetos, 1)}


def propuesta(est=None):
    """Preguntas rapidas para configurar ESTE equipo, con opciones sacadas de lo observado. El coordinador las hace."""
    est = est or estado()
    n, total = est["nucleos"], est["ram_total_gb"] or 8
    hilos = sorted({n, max(1, n - 2), max(1, n // 2)}, reverse=True)
    ram = sorted({int(total * 0.85), int(total * 0.6), int(total * 0.4)}, reverse=True)
    return [
        {"clave": "perfil", "pregunta": "¿Cuánto se le puede exigir a este equipo durante una validación pesada?",
         "opciones": [{"valor": k, "texto": v["texto"]} for k, v in PERFILES.items()]},
        {"clave": "hilos", "pregunta": f"El equipo tiene {n} hilos lógicos ({est.get('nucleos_fisicos') or '?'} núcleos físicos"
                                       f"{', hasta ' + str(est['mhz_max']) + ' MHz' if est.get('mhz_max') else ''}). ¿Tope de hilos de cómputo?",
         "opciones": [{"valor": h, "texto": f"{h} hilos" + (" (todos)" if h == n else " (deja libres para trabajar)" if h == n - 2 else " (la mitad)")}
                      for h in hilos]},
        {"clave": "ram_gb", "pregunta": f"El equipo tiene {total} GB de RAM ({est['ram_disponible_gb']} libres ahora). ¿Cuánta puede usar la medición?",
         "opciones": [{"valor": r, "texto": f"{r} GB"} for r in ram]},
    ]


def aplicar(cfg, par):
    """Ajusta en memoria la configuracion cargada (config/pipeline.json) al perfil de este equipo. No escribe nada."""
    try:
        lm = limites()
    except Exception:
        return None
    m = cfg.setdefault("medicion", {})
    m["duckdb_memoria"], m["duckdb_hilos"] = lm["duckdb_memoria"], lm["duckdb_hilos"]
    par["medicion_local_objetos"] = lm["medicion_local_objetos"]
    par["onelake_hilos"] = min(par.get("onelake_hilos", 8), lm["onelake_hilos"])
    par["rocket_hilos_por_objeto"] = min(par.get("rocket_hilos_por_objeto", 8), lm["rocket_hilos_por_objeto"])
    return lm


def comprobar(tarea, objetos=None):
    """Antes de un paso pesado: ¿alcanza la RAM disponible para lo que el perfil va a abrir? Devuelve (ok, mensaje)."""
    est, lm = estado(), limites()
    n = min(objetos or lm["medicion_local_objetos"], lm["medicion_local_objetos"])
    necesita = int(lm["duckdb_memoria"][:-2]) * n if tarea in ("medir", "cotejar", "diferenciar", "comparar") else 1
    avisos = []
    if not lm["guardado"]:
        avisos.append("este equipo no tiene perfil de capacidad: preguntar a la persona (máxima posible · máxima moderada · "
                      "promedio) y fijarlo con `python -m pc recursos --perfil …`; mientras tanto se usa «promedio»")
    disp = est["ram_disponible_gb"]
    if disp is not None and disp < necesita + RESERVA_GB:
        avisos.append(f"RAM disponible {disp} GB y {tarea} abriría {necesita} GB ({n} objeto(s) × {lm['duckdb_memoria']}) + "
                      f"{RESERVA_GB} GB de reserva: cerrar aplicaciones, bajar el perfil o seguir con --forzar-recursos")
    if est["carga_1min"] is not None and est["carga_1min"] > est["nucleos"] * 1.5:
        avisos.append(f"carga del equipo {est['carga_1min']} con {est['nucleos']} núcleos: ya hay otro proceso pesado corriendo")
    if tarea == "descargar" and est["disco_libre_gb"] < 10:
        avisos.append(f"solo {est['disco_libre_gb']} GB libres en disco para la caché")
    # memory_limit de DuckDB es un tope, no una reserva: con «maxima» (elegida por la persona) solo se avisa, salvo que la
    # RAM libre no llegue ni a la mitad de lo que se abrira; con los otros perfiles cualquier falta de margen detiene
    corta = disp is not None and disp < necesita + RESERVA_GB
    bloquea = (corta and (lm["perfil"] != "maxima" or disp < necesita / 2)) or (
        est["carga_1min"] is not None and est["carga_1min"] > est["nucleos"] * 1.5 and lm["perfil"] != "maxima")
    return (not bloquea), avisos, est, lm


def texto(est=None, lm=None):
    est, lm = est or estado(), lm or limites()
    cpu = " · ".join(x for x in (est.get("cpu_modelo"), f"{est['nucleos_fisicos']} físicos" if est.get("nucleos_fisicos") else None,
                                 f"{est['mhz_max']} MHz máx." if est.get("mhz_max") else None) if x)
    aj = ", ".join(f"{k}={v}" for k, v in (lm.get("ajustes") or {}).items())
    return (f"equipo {est['equipo']} · {est['nucleos']} hilos lógicos{' (' + cpu + ')' if cpu else ''} · RAM {est['ram_disponible_gb']} de {est['ram_total_gb']} GB disponible · "
            f"carga {est['carga_1min']} · disco libre {est['disco_libre_gb']} GB\n"
            f"perfil {lm['perfil']} ({lm['texto']}{'' if lm['guardado'] else ', SIN GUARDAR: preguntar a la persona'}"
            f"{' · ajustes de la persona: ' + aj if aj else ''}) → "
            f"DuckDB {lm['duckdb_memoria']} × {lm['duckdb_hilos']} hilos por objeto · {lm['medicion_local_objetos']} objeto(s) a la vez · "
            f"OneLake {lm['onelake_hilos']} hilos · Rocket {lm['rocket_hilos_por_objeto']} hilos")
