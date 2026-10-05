"""OneLake (DFS): listar, HEAD, leer por rango, bajar y escribir.

La lectura por rango es lo que permite el nivel 0/1 sin descargar: del parquet solo se piden
los ultimos KB (el pie), y del _delta_log solo los JSON y el checkpoint.
"""
import io
import json
import os
import random
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from ..config import FAB
from . import fabric

DFS = FAB["onelake"]
WS, LH = FAB["ws_datalake"], FAB["lh_transversal"]


def _url(rel, ws=None, lh=None):
    return f"{DFS}/{ws or WS}/{urllib.parse.quote((lh or LH) + '/' + rel.lstrip('/'))}"


def _pedir(url, metodo="GET", cab=None, datos=None, timeout=300, intentos=6):
    ult = None
    for i in range(intentos):
        h = {"Authorization": f"Bearer {fabric.token('onelake', renovar=i > 0 and getattr(ult, 'code', 0) == 401)}"}
        h.update(cab or {})
        req = urllib.request.Request(url, data=datos, headers=h, method=metodo)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            ult = e
            if e.code in (404, 409, 400, 403) and e.code != 401:
                raise
            if e.code in (429, 503):          # limite de Fabric: esperar lo que pide, no insistir
                time.sleep(float(e.headers.get("Retry-After") or 10 * (i + 1)))
                continue
        except Exception as e:  # red, VPN, corte
            ult = e
        time.sleep(2 + random.random() * 3 * (i + 1))
    raise ult


def head(rel, ws=None, lh=None):
    """Propiedades del archivo, o None si no existe (404 es definitivo)."""
    try:
        with _pedir(_url(rel, ws, lh), "HEAD", timeout=60) as x:
            return {"bytes": int(x.headers.get("Content-Length") or 0),
                    "modificado": x.headers.get("Last-Modified"),
                    "tipo": x.headers.get("x-ms-resource-type")}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def listar(directorio, recursivo=True, ws=None, lh=None):
    """[{name (relativo al lakehouse), isDirectory, contentLength, lastModified}]."""
    salida, cont = [], None
    pref = (lh or LH) + "/"
    while True:
        url = (f"{DFS}/{ws or WS}?resource=filesystem&recursive={'true' if recursivo else 'false'}"
               f"&directory=" + urllib.parse.quote(pref + directorio.strip('/')))
        if cont:
            url += "&continuation=" + urllib.parse.quote(cont)
        try:
            with _pedir(url, timeout=300) as x:
                ps, cont = json.load(x).get("paths", []), x.headers.get("x-ms-continuation")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            raise
        for p in ps:
            p["name"] = p["name"][len(pref):] if p["name"].startswith(pref) else p["name"]
            p["isDirectory"] = str(p.get("isDirectory", "false")).lower() == "true"
            p["contentLength"] = int(p.get("contentLength") or 0)
        salida += ps
        if not cont:
            return salida


def leer(rel, ws=None, lh=None):
    with _pedir(_url(rel, ws, lh), timeout=600) as x:
        return x.read()


def leer_rango(rel, inicio, fin, ws=None, lh=None):
    """Bytes [inicio, fin] inclusive. Exige 206: un 200 seria el archivo entero."""
    with _pedir(_url(rel, ws, lh), cab={"Range": f"bytes={inicio}-{fin}"}, timeout=120) as x:
        if x.status != 206:
            raise IOError(f"OneLake no respeto el Range (HTTP {x.status})")
        return x.read()


def bajar(rel, local, bytes_esperados=None, ws=None, lh=None):
    """Descarga reanudable por tamano: .part y renombre; si ya esta completo no baja."""
    if os.path.exists(local) and (bytes_esperados is None or os.path.getsize(local) == bytes_esperados):
        return local
    os.makedirs(os.path.dirname(local) or ".", exist_ok=True)
    for i in range(5):
        try:
            with _pedir(_url(rel, ws, lh), timeout=3600) as x, open(local + ".part", "wb") as f:
                shutil.copyfileobj(x, f, 8 << 20)
            if bytes_esperados and os.path.getsize(local + ".part") != bytes_esperados:
                raise IOError("tamano distinto al listado")
            os.replace(local + ".part", local)
            return local
        except urllib.error.HTTPError:
            raise
        except Exception:
            if i == 4:
                raise
            time.sleep(5 * (i + 1))


def escribir(rel, datos, ws=None, lh=None):
    """create + append + flush. Sin el flush el archivo queda en cero bytes."""
    if isinstance(datos, str):
        datos = datos.encode("utf8")
    u = _url(rel, ws, lh)
    with _pedir(u + "?resource=file", "PUT", cab={"Content-Length": "0"}, datos=b""):
        pass
    with _pedir(u + "?action=append&position=0", "PATCH",
                cab={"Content-Type": "application/octet-stream", "Content-Length": str(len(datos))}, datos=datos):
        pass
    with _pedir(u + f"?action=flush&position={len(datos)}", "PATCH", cab={"Content-Length": "0"}, datos=b""):
        pass
    return rel


class ArchivoRemoto(io.RawIOBase):
    """Archivo de solo lectura sobre OneLake con lecturas por rango. pyarrow lo usa para leer
    el pie de un parquet sin bajarlo: pide los ultimos 8 bytes y luego el bloque del pie."""

    def __init__(self, rel, tamano=None, ws=None, lh=None, cache_cola=65536):
        self.rel, self.ws, self.lh = rel, ws, lh
        self.tam = tamano if tamano is not None else (head(rel, ws, lh) or {}).get("bytes", 0)
        self.pos = 0
        self.pedidos = 0
        self.bytes_leidos = 0
        ini = max(0, self.tam - cache_cola)
        self._cola_ini = ini
        self._cola = self._rango(ini, self.tam - 1) if self.tam else b""

    def _rango(self, a, b):
        self.pedidos += 1
        d = leer_rango(self.rel, a, b, self.ws, self.lh)
        self.bytes_leidos += len(d)
        return d

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
        if a >= self._cola_ini:
            d = self._cola[a - self._cola_ini: b - self._cola_ini + 1]
        else:
            d = self._rango(a, b)
        self.pos += len(d)
        return d

    def readinto(self, buf):
        d = self.read(len(buf))
        buf[:len(d)] = d
        return len(d)
