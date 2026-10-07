"""Cache de resolucion DNS por proceso.

Con la VPN de Comfandi activa, los dos primeros servidores de /etc/resolv.conf (los de la VPN) no responden
nombres publicos (Fabric, OneLake) y cada resolucion espera su vencimiento antes de pasar al siguiente: 9 a 16 s
por llamada HTTP, y sin limite si la VPN se cae a medias (el `timeout` de urlopen no cubre `socket.getaddrinfo`).
Asi se quedo `pc etl evidencia` mas de 3 h el 2026-10-06. Aqui se resuelve cada nombre una vez cada `TTL_S`.
No cambia que se mide ni como: solo cuantas veces se pregunta al DNS.
"""
import socket
import threading
import time

TTL_S = 600
_ORIGINAL = socket.getaddrinfo
_CACHE, _LK = {}, threading.Lock()


def _getaddrinfo(host, port, *a, **k):
    clave = (host, port, a, tuple(sorted(k.items())))
    with _LK:
        h = _CACHE.get(clave)
    if h and time.time() - h[1] < TTL_S:
        return h[0]
    r = _ORIGINAL(host, port, *a, **k)
    with _LK:
        _CACHE[clave] = (r, time.time())
    return r


def activar():
    if socket.getaddrinfo is not _getaddrinfo:
        socket.getaddrinfo = _getaddrinfo
