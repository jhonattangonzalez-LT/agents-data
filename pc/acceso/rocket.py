"""Rocket (HDFS de Stratio): listar, bajar y probar lectura por rango.

API: POST {rocket}/<endpoint> con cuerpo {"pathHdfs": ruta} y la cabecera Cookie completa
(stickyrocket + stratio-cookie + JSESSIONID). La cookie caduca; un 401 significa pedir otra.
Rocket es fragil y lento (~10 s por archivo): un objeto a la vez (candado entre procesos) y
muchos hilos dentro del objeto. Una carpeta vacia suele ser Stratio reescribiendo: reintentar.

Requiere VPN de Comfandi y ruta hacia datafabric.comfandi.com.co.
"""
import fcntl
import io
import json
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from ..config import CFG, PAR, RAIZ, secreto_ruta

URL = CFG["stratio"]["rocket"]


class CookieVencida(RuntimeError):
    """HTTP 401 de Rocket: el usuario debe renovar ~/Projects/.rocket_cookie."""


_LK = threading.Lock()
_VENCIDAS = set()
_TURNO = [0]


def _rutas_cookies():
    """1 a 3 cookies: ~/Projects/.rocket_cookie, .rocket_cookie_2, .rocket_cookie_3 (una por sesion de navegador)."""
    base = secreto_ruta("rocket_cookie")
    return [p for p in [base, base + "_2", base + "_3"] if os.path.exists(p)]


def _cookie():
    """La siguiente cookie vigente, en turno rotativo: las peticiones se reparten entre las sesiones."""
    with _LK:
        vivas = [p for p in _rutas_cookies() if p not in _VENCIDAS]
        if not vivas:
            raise CookieVencida("ninguna cookie de Rocket vigente: pedir al usuario una nueva")
        p = vivas[_TURNO[0] % len(vivas)]
        _TURNO[0] += 1
    return p, open(p, encoding="utf8").read().strip()


def post(endpoint, ruta_hdfs, timeout=180, rango=None):
    """POST a Rocket con la siguiente cookie del turno. Un 401 marca esa cookie como vencida y reintenta con otra."""
    for _ in range(3):
        ruta_c, valor = _cookie()
        cab = {"Cookie": valor, "Content-Type": "application/json"}
        if rango:
            cab["Range"] = f"bytes={rango[0]}-{rango[1]}"
        req = urllib.request.Request(f"{URL}/{endpoint}", data=json.dumps({"pathHdfs": ruta_hdfs}).encode(),
                                     headers=cab, method="POST")
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                with _LK:
                    _VENCIDAS.add(ruta_c)
                continue
            if e.code in (429, 503):
                time.sleep(float(e.headers.get("Retry-After") or 15))
                continue
            raise
    raise CookieVencida("Rocket respondio 401 con todas las cookies: pedir cookies nuevas")


def _reintentar(fn, intentos=6, espera=5):
    for i in range(intentos):
        try:
            return fn()
        except CookieVencida:
            raise
        except Exception:
            if i == intentos - 1:
                raise
            time.sleep(espera * (i + 1))


def listar(ruta):
    """[{name, type, size, lastUpdated}] de una carpeta."""
    def ir():
        with post("fileBrowser/findByPath", ruta, 180) as x:
            d = json.load(x)
        return d if isinstance(d, list) else (d.get("content") or d.get("data") or [])
    return _reintentar(ir)


def arbol(ruta, desde=None, hilos=3):
    """[(ruta_completa, bytes, lastUpdated_ms)] recursivo. Ignora _SUCCESS, _* y .*.
    `desde="fecha=2026-01-01"` salta particiones Hive anteriores a ese valor."""
    archivos, pend = [], [ruta]
    with ThreadPoolExecutor(hilos) as ex:
        while pend:
            lotes = list(ex.map(listar, pend))
            pend = []
            for items in lotes:
                for i in items:
                    nom = i.get("name") or ""
                    base = nom.rsplit("/", 1)[-1]
                    if base.startswith(("_", ".")):
                        continue
                    if str(i.get("type", "")).lower() == "directory":
                        if desde and "=" in base and base.split("=")[0] == desde.split("=")[0] and base < desde:
                            continue
                        pend.append(nom)
                    else:
                        archivos.append((nom, int(i.get("size") or 0), i.get("lastUpdated")))
    return sorted(archivos)


def probar_rango(ruta_archivo, n=8):
    """¿Rocket acepta Range? Pide los ultimos n bytes. Devuelve {acepta, status, bytes}."""
    tam = next((s for p, s, _ in arbol(ruta_archivo.rsplit("/", 1)[0]) if p == ruta_archivo), None)
    if not tam:
        return {"acepta": False, "status": None, "motivo": "archivo no encontrado o vacio"}
    with post("fileBrowser/download", ruta_archivo, 120, rango=(tam - n, tam - 1)) as x:
        d = x.read(n + 1)
        return {"acepta": x.status == 206 and len(d) == n, "status": x.status, "bytes": len(d),
                "content_range": x.headers.get("Content-Range"), "tamano": tam}


class ArchivoRocket(io.RawIOBase):
    """Igual que onelake.ArchivoRemoto pero sobre Rocket. Solo sirve si probar_rango() acepta."""

    def __init__(self, ruta, tamano, cola=65536):
        self.ruta, self.tam, self.pos, self.pedidos = ruta, tamano, 0, 0
        self._ci = max(0, tamano - cola)
        self._c = self._rango(self._ci, tamano - 1)

    def _rango(self, a, b):
        self.pedidos += 1
        with post("fileBrowser/download", self.ruta, 120, rango=(a, b)) as x:
            if x.status != 206:
                raise IOError(f"Rocket no respeto el Range (HTTP {x.status})")
            return x.read()

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def size(self):
        return self.tam

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.tam + off)
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.tam - self.pos
        if n <= 0 or self.pos >= self.tam:
            return b""
        a, b = self.pos, min(self.tam, self.pos + n) - 1
        d = self._c[a - self._ci: b - self._ci + 1] if a >= self._ci else self._rango(a, b)
        self.pos += len(d)
        return d


def bajar(ruta, destino, desde=None, hilos=None, log=print):
    """Baja el arbol de `ruta` a `destino`. Un objeto a la vez entre procesos (candado),
    `hilos` dentro del objeto. Reanudable: salta lo que ya tiene el mismo tamano y baja a .part.
    Devuelve (archivos_locales, metadatos)."""
    hilos = hilos or PAR["rocket_hilos_por_objeto"]
    os.makedirs(os.path.join(RAIZ, "cache", ".locks"), exist_ok=True)
    with open(os.path.join(RAIZ, "cache", ".locks", "rocket.lock"), "w") as lf:
        t0 = time.time()
        fcntl.flock(lf, fcntl.LOCK_EX)
        if time.time() - t0 > 5:
            log(f"rocket: espere {time.time() - t0:.0f} s el turno")
        arch = arbol(ruta, desde=desde)
        if not arch:
            raise RuntimeError(f"sin archivos en {ruta} (¿Stratio reescribiendo? reintentar)")
        os.makedirs(destino, exist_ok=True)
        lk, hecho = threading.Lock(), [0]

        def uno(par):
            rem, size, _m = par
            rel = rem[len(ruta.rstrip("/")) + 1:]
            loc = os.path.join(destino, rel)
            if os.path.exists(loc) and os.path.getsize(loc) == size:
                return loc
            os.makedirs(os.path.dirname(loc), exist_ok=True)

            def ir():
                with post("fileBrowser/download", rem, 3600) as x, open(loc + ".part", "wb") as f:
                    shutil.copyfileobj(x, f, 4 << 20)
                if size and os.path.getsize(loc + ".part") != size:
                    raise IOError(f"tamano {os.path.getsize(loc + '.part')} != {size}")
                os.replace(loc + ".part", loc)
            _reintentar(ir)
            with lk:
                hecho[0] += size
            return loc

        with ThreadPoolExecutor(hilos) as ex:
            locs = list(ex.map(uno, arch))
    _limpiar_obsoletos(destino, locs, log)
    total = sum(s for _, s, _m in arch)
    return locs, {"num_archivos": len(arch), "bytes": total, "segundos": round(time.time() - t0, 1),
                  "ultima_modificacion_ms": max((m or 0) for _, _, m in arch)}


def _limpiar_obsoletos(destino, vigentes, log=print):
    """Stratio reescribe con nombres nuevos (UUID): lo que ya no esta en origen sale de la cache."""
    v = {os.path.abspath(x) for x in vigentes}
    n = 0
    for raiz, _d, fs in os.walk(destino):
        for f in fs:
            p = os.path.abspath(os.path.join(raiz, f))
            if p not in v and not f.startswith(".") and not f.endswith(".part"):
                os.remove(p)
                n += 1
    if n:
        log(f"cache: {n} archivo(s) obsoleto(s) eliminado(s) en {destino}")


VIDA_ESTIMADA_H = (2.0, 3.0)   # la cookie de Rocket dura en la practica 2 a 3 horas (a veces menos que su JWT)


def _estado_una(p):
    import base64
    import datetime as dt
    ahora = dt.datetime.now(dt.timezone.utc)
    puesta = dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc)
    jwt_exp = None
    for parte in open(p, encoding="utf8").read().strip().split(";"):
        k, _, v = parte.strip().partition("=")
        if k == "stratio-cookie" and v.count(".") == 2:
            try:
                cuerpo = v.split(".")[1] + "=" * (-len(v.split(".")[1]) % 4)
                exp = json.loads(base64.urlsafe_b64decode(cuerpo)).get("exp")
                jwt_exp = dt.datetime.fromtimestamp(exp, dt.timezone.utc) if exp else None
            except Exception:
                pass
    lo, hi = (puesta + dt.timedelta(hours=h) for h in VIDA_ESTIMADA_H)
    vence = min(lo, jwt_exp) if jwt_exp else lo
    resta = round((vence - ahora).total_seconds() / 60)
    if p in _VENCIDAS:
        resta = min(resta, 0)
    return {"archivo": os.path.basename(p), "puesta_utc": puesta.isoformat(timespec="minutes"),
            "edad_h": round((ahora - puesta).total_seconds() / 3600, 2),
            "vence_estimado_utc": f"{lo.isoformat(timespec='minutes')} a {hi.isoformat(timespec='minutes')}",
            "vence_jwt_utc": jwt_exp.isoformat(timespec="minutes") if jwt_exp else None,
            "minutos_restantes_estimados": resta,
            "aviso": ("VENCIDA o por vencer: renovar" if resta <= 15 else
                      f"renovar en ~{resta} min" if resta <= 60 else f"vigente, ~{resta} min restantes")}


def estado_cookie():
    """Estado de cada cookie (1 a 3). Nunca devuelve su contenido. Se informa SIEMPRE al usuario antes de Stratio."""
    rutas = _rutas_cookies()
    if not rutas:
        return {"cookies": [], "aviso": "no hay cookie: pedir una nueva al usuario"}
    est = [_estado_una(p) for p in rutas]
    vigentes = [e for e in est if e["minutos_restantes_estimados"] > 15]
    return {"cookies": est, "vigentes": len(vigentes), "hilos_rocket": PAR["rocket_hilos_por_objeto"],
            "aviso": (f"{len(vigentes)} de {len(est)} vigente(s); los {PAR['rocket_hilos_por_objeto']} hilos se reparten entre ellas"
                      if vigentes else "ninguna vigente: pedir cookies nuevas antes de seguir")}
