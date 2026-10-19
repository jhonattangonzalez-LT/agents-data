"""Salida corta de los comandos largos: el detalle va a un archivo y a la consola solo el resumen.

Con PC_RESUMEN=1 (o --resumen en cualquier parte de la linea; --detalle lo apaga) los comandos de
LARGOS escriben todo lo que imprimen en trabajos/<T>/salidas/<comando>_<ts>.log y, al terminar, la
consola recibe: una linea de estado con los eventos de la bitacora de esa corrida, los avisos y errores
(uno por linea) y las lineas de resultado (sin el avance). Las cifras completas siguen en los JSON.

avance(msg, **datos) es el progreso: va al log y a trabajos/<T>/progreso/<pid>.json (lo lee el panel),
nunca al resumen.
"""
import contextlib
import datetime
import io
import json
import os
import sys
import time

from . import lote as L

LARGOS = {"rapido", "descargar", "medir", "cotejar", "semaforo", "etl", "v4", "diferenciar"}
MAX_LINEAS = 25

_ACTUAL = {"trabajo": None, "progreso": None, "log": None, "comando": None, "inicio": None}


def activo(argv):
    """(argv sin las banderas de salida, resumen?). --resumen/--detalle solo se leen en los comandos de LARGOS:
    otros comandos tienen su propio --resumen (p. ej. pc codigo cerrar --resumen "...")."""
    resumen = os.environ.get("PC_RESUMEN") == "1"
    if not argv or argv[0] not in LARGOS:
        return list(argv), resumen
    if "--resumen" in argv:
        resumen = True
    if "--detalle" in argv:
        resumen = False
    return [x for x in argv if x not in ("--resumen", "--detalle")], resumen


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _escribir_progreso(datos):
    p = _ACTUAL["progreso"]
    if not p:
        return
    try:
        tmp = p + ".tmp"
        json.dump(datos, open(tmp, "w"), ensure_ascii=False, default=str)
        os.replace(tmp, p)
    except OSError:
        pass


def avance(msg, **datos):
    """Progreso de un comando largo: log + archivo de progreso. Nunca entra al resumen."""
    print(msg, file=_ACTUAL["log"] or sys.stdout, flush=True)
    if _ACTUAL["progreso"]:
        _escribir_progreso({"pid": os.getpid(), "comando": _ACTUAL["comando"], "inicio_utc": _ACTUAL["inicio"],
                            "ts": _ahora(), "ultimo": str(msg)[:200], **datos})


class _Tee(io.TextIOBase):
    """Todo al log; las lineas de resultado se guardan para el resumen."""

    def __init__(self, log):
        self.log, self.lineas, self._buf = log, [], ""

    def write(self, s):
        self.log.write(s)
        self._buf += s
        while "\n" in self._buf:
            ln, self._buf = self._buf.split("\n", 1)
            if ln.strip():
                self.lineas.append(ln)
        return len(s)

    def flush(self):
        self.log.flush()


@contextlib.contextmanager
def envolver(comando, trabajo, resumen):
    """Rodea la ejecucion de un comando. Sin trabajo, o sin resumen, solo registra el progreso."""
    if not trabajo:
        yield
        return
    base = L.dir_lote(trabajo)
    os.makedirs(os.path.join(base, "progreso"), exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    _ACTUAL.update(trabajo=trabajo, comando=" ".join([comando] + sys.argv[2:])[:300], inicio=_ahora(),
                   progreso=os.path.join(base, "progreso", f"{os.getpid()}.json"))
    _escribir_progreso({"pid": os.getpid(), "comando": _ACTUAL["comando"], "inicio_utc": _ACTUAL["inicio"],
                        "ts": _ACTUAL["inicio"], "ultimo": "inicio"})
    if not (resumen and comando in LARGOS):
        try:
            yield
        finally:
            _fin()
        return
    os.makedirs(os.path.join(base, "salidas"), exist_ok=True)
    ruta = os.path.join(base, "salidas", f"{comando}_{ts}_{os.getpid()}.log")
    n0, t0 = len(L.leer_bitacora(trabajo)), time.time()
    log = open(ruta, "w", encoding="utf8")
    _ACTUAL["log"] = log
    tee = _Tee(log)
    out, err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = tee, log
    fallo = None
    try:
        yield
    except SystemExit as e:
        fallo = e
        if e.code not in (None, 0):
            print(f"SALIDA {e.code}")
    except BaseException as e:
        import traceback
        traceback.print_exc(file=log)
        fallo = e
        print(f"ERROR {type(e).__name__}: {str(e)[:200]}")
    finally:
        sys.stdout, sys.stderr = out, err
        log.close()
        _ACTUAL["log"] = None
        _fin()
        _resumir(comando, trabajo, ruta, n0, time.time() - t0, tee.lineas, fallo)
    if fallo is not None:
        raise SystemExit(1 if not isinstance(fallo, SystemExit) else fallo.code)


def _fin():
    p = _ACTUAL["progreso"]
    _ACTUAL.update(progreso=None)
    if p and os.path.exists(p):
        os.remove(p)


def _resumir(comando, trabajo, ruta, n0, seg, lineas, fallo):
    ev = L.leer_bitacora(trabajo)[n0:]
    cuenta = {e: sum(1 for x in ev if x["estado"] == e) for e in ("OK", "AVISO", "ERROR")}
    malos = [x for x in ev if x["estado"] == "ERROR"]
    estado = "ERROR" if fallo is not None and not (isinstance(fallo, SystemExit) and fallo.code in (None, 0)) \
        else "ERROR" if cuenta["ERROR"] else "AVISO" if cuenta["AVISO"] else "OK"
    rel = os.path.relpath(ruta, L.RAIZ)
    print(f"{estado} · {comando} · {trabajo} · {int(seg // 60)}m{int(seg % 60):02d}s · "
          f"{len(ev)} evento(s): {cuenta['OK']} OK, {cuenta['AVISO']} AVISO, {cuenta['ERROR']} ERROR · detalle: {rel}")
    for x in malos[:MAX_LINEAS]:
        print(f"  {x['estado']:5s} {x['agente']} {x['accion']} {x.get('flujo') or ''} {x.get('clave') or ''}"
              f" · {(x.get('error') or json.dumps(x.get('detalle'), ensure_ascii=False, default=str))[:160]}")
    if len(malos) > MAX_LINEAS:
        print(f"  … {len(malos) - MAX_LINEAS} aviso(s)/error(es) más en el detalle")
    if lineas:
        print("resultado:")
        out, sub = [], 0
        for ln in lineas:
            sub = sub + 1 if ln.startswith(("     ", "\t")) else 0
            if sub == 4:
                out.append("      …")
            if sub < 4:
                out.append(ln)
        for ln in out[:MAX_LINEAS]:
            print("  " + ln[:180])
        if len(out) > MAX_LINEAS:
            print(f"  … {len(out) - MAX_LINEAS} línea(s) más en el detalle")
