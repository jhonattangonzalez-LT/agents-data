"""Bucket de metricas (Azure Blob) con la SAS, sin SDK. Punto de encuentro Stratio <-> Fabric.

metricas-stratio/v3/qa/<clave>/... y metricas-fabric/v3/qa/<clave>/...  La version _vN del
nombre sale de lo que ya existe en el bucket para esa clave.
"""
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from ..config import CFG, secreto_ruta

CUENTA = CFG["bucket"]["cuenta"]
CONT = CFG["bucket"]["contenedores"]
PREFIJO = CFG["bucket"]["prefijo"]
_RE_V = re.compile(r"_v(\d+)\.json$", re.I)


def _sas():
    return open(secreto_ruta("bucket_sas"), encoding="utf8").read().strip().lstrip("?")


def _base(plat):
    return f"https://{CUENTA}.blob.core.windows.net/{CONT[plat.upper()]}"


def listar(plataforma, prefijo=PREFIJO):
    out, marker = [], ""
    while True:
        url = (f"{_base(plataforma)}?{_sas()}&restype=container&comp=list&maxresults=5000"
               f"&prefix={urllib.parse.quote(prefijo)}" + (f"&marker={marker}" if marker else ""))
        with urllib.request.urlopen(url, timeout=180) as x:
            raiz = ET.fromstring(x.read())
        for b in raiz.iter("Blob"):
            n = b.findtext("Name") or ""
            p = b.find("Properties")
            out.append((n, int(p.findtext("Content-Length") or 0), p.findtext("Last-Modified")))
        marker = raiz.findtext("NextMarker") or ""
        if not marker:
            return out


def siguiente_version(plataforma, clave):
    vs = [int(m.group(1)) for n, _s, _m in listar(plataforma, f"{PREFIJO}{clave}/") if (m := _RE_V.search(n))]
    return (max(vs) + 1) if vs else 1


def existe(plataforma, blob):
    url = f"{_base(plataforma)}/{urllib.parse.quote(blob)}?{_sas()}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def bajar(plataforma, blob, destino):
    url = f"{_base(plataforma)}/{urllib.parse.quote(blob)}?{_sas()}"
    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    with urllib.request.urlopen(url, timeout=600) as x, open(destino, "wb") as f:
        f.write(x.read())
    return destino


def subir(plataforma, blob, datos, tipo="application/json", sobrescribir=False):
    """Sube un blob. Por defecto no sobreescribe; reportes_v4 reescribe en sitio la version del lote en curso."""
    if isinstance(datos, str):
        datos = datos.encode("utf8")
    if not sobrescribir and existe(plataforma, blob):
        raise FileExistsError(f"ya existe {plataforma}:{blob}")
    url = f"{_base(plataforma)}/{urllib.parse.quote(blob)}?{_sas()}"
    req = urllib.request.Request(url, data=datos, method="PUT",
                                 headers={"x-ms-blob-type": "BlockBlob", "Content-Type": tipo})
    with urllib.request.urlopen(req, timeout=600):
        return blob
