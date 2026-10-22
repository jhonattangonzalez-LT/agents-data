"""Revisor de la evidencia del acta: los JSON publicados que citan los EXITOSOS de los QA.

  python -m pc acta revisar --lote N --exitosos <carpeta o archivos>      (también corre dentro de `pc acta generar`)

No bloquea el acta. Por cada enlace revisa:
  · que exista (HEAD 200) y que sea el correcto: el archivo dice el flujo/tabla y la versión de su nombre, y no hay una
    versión mayor publicada en la misma carpeta (el EXITOSOS citaría una evidencia vieja);
  · que no tenga nada pendiente que el QA dejó abierto: estado EN_CURSO / EN_REVISION / DEVUELTO o distinto del EXITOSOS,
    faltantes, controles sin analizar, diferencias PENDIENTE o DEVUELTO, A_VERIFICAR sin la verificación APRUEBA,
    comprobaciones que no cumplen, diferencias sin ejemplo real. No se advierte lo que el pipeline agregó después de
    publicar (p. ej. dependencias medidas, CP-05.aplicacion): eso no es un pendiente del QA.
Cada hallazgo queda como advertencia (lotes/<N>/acta/advertencias.json) y en un MENSAJE por QA y trabajo
(lotes/<N>/acta/mensajes/<trabajo>.md) para que corrija y vuelva a publicar SOBRE ESE MISMO ENLACE (misma ruta y versión,
sin abrir ciclo nuevo). Al regenerar el acta, el enlace ya no sale en la lista.
"""
import json
import os
import re

from .acceso import fabric, onelake as ol

ABIERTOS = ("EN_CURSO", "EN_REVISION", "DEVUELTO")
REPUBLICAR = ("corregir en el trabajo y volver a publicar sobre este mismo enlace: `python -m pc v4 publicar --trabajo {t}` "
              "(misma versión v{v}, sin abrir ciclo nuevo)")


def hallazgo(md, flujo, clave, documento, ruta, problema, que_hacer=None, version=None):
    t = md.get("trabajo")
    return {"qa": md.get("generado_por") or f"QA del trabajo {t}", "trabajo": t, "exitosos": md.get("ruta"), "flujo": flujo,
            "tabla": clave, "documento": documento, "ruta": ruta, "enlace": fabric.portal_archivo(ruta) if ruta else None,
            "problema": problema, "que_hacer": que_hacer or REPUBLICAR.format(t=t, v=version if version is not None else "N")}


def _sin_traza(x):
    if isinstance(x, dict):
        return {k: _sin_traza(v) for k, v in x.items() if k not in ("trazabilidad", "generado_utc", "publicado_utc", "actualizado_utc")}
    if isinstance(x, list):
        return [_sin_traza(v) for v in x]
    return x


def distinto(local, publicado):
    """Campos que la copia local del QA cambió respecto a lo publicado ([] si nada). Un campo que solo existe en la local
    (lo agregó una versión más nueva del pipeline, p. ej. CP-05.aplicacion) no cuenta: no es una corrección del QA."""
    out = []

    def d(x, y, p):
        if isinstance(x, dict) and isinstance(y, dict):
            for k in y:
                if k not in x:
                    out.append(f"{p}/{k}")
                else:
                    d(x[k], y[k], f"{p}/{k}")
        elif isinstance(x, list) and isinstance(y, list):
            if len(x) != len(y):
                out.append(p)
            else:
                for u, v in zip(x, y):
                    d(u, v, p)
        elif x != y:
            out.append(p)
    d(_sin_traza(local), _sin_traza(publicado), "")
    # un control cambia en varios campos a la vez: basta nombrar el control o la sección
    return list(dict.fromkeys("/".join(c.split("/")[:5]) if "/controles/" in c else "/".join(c.split("/")[:3]) for c in out))


def _cambio(campos):
    return ("la copia local del trabajo cambió después de publicar (lo publicado está desactualizado): "
            + ", ".join(c.strip("/") for c in campos[:4]) + (f" y {len(campos) - 4} más" if len(campos) > 4 else ""))


def version_mayor(ruta):
    """Mayor vN publicada en la carpeta del archivo (o None si no se pudo listar)."""
    carpeta, nombre = ruta.rsplit("/", 1)
    base = re.sub(r"_v\d+\.json$", "", nombre)
    try:
        vs = [int(m.group(1)) for p in ol.listar(carpeta, False)
              if (m := re.search(rf"/{re.escape(base)}_v(\d+)\.json$", p["name"]))]
    except Exception:
        return None
    return max(vs) if vs else None


def flujo(md, fd, cf, ruta, local=None):
    """Hallazgos del cotejo de flujo publicado."""
    n, ver = fd["flujo"], int(fd["version"])
    e, out = cf.get("encabezado") or {}, []
    H = lambda p, q=None: out.append(hallazgo(md, n, None, "Cotejo del flujo", ruta, p, q, ver))
    if (e.get("flujo") or {}).get("fabric") not in (n, None):
        H(f"el archivo es del flujo {(e.get('flujo') or {}).get('fabric')}, no de {n}: enlace equivocado",
          "corregir el enlace en el EXITOSOS (`python -m pc cierre --trabajo …`) o publicar el reporte correcto en esa ruta")
    if str(e.get("version")) != str(ver):
        H(f"el archivo dice v{e.get('version')} y el EXITOSOS cita v{ver}")
    vm = version_mayor(ruta)
    if vm and vm > ver:
        H(f"hay una versión mayor publicada (v{vm}) y el EXITOSOS cita v{ver}",
          "confirmar cuál es la evidencia vigente; si es la mayor, regenerar el EXITOSOS (`pc cierre`) y pasarlo de nuevo")
    if e.get("estado") in ABIERTOS:
        H(f"estado {e['estado']}: el flujo no está cerrado")
    elif fd.get("estado") and e.get("estado") != fd["estado"]:
        H(f"el EXITOSOS dice {fd['estado']} y el reporte publicado {e.get('estado')}")
    if e.get("faltantes"):
        H("faltantes: " + "; ".join(map(str, e["faltantes"][:6])))
    if e.get("comprobaciones_que_no_cumplen"):
        H("comprobaciones que no cumplen: " + "; ".join(map(str, e["comprobaciones_que_no_cumplen"][:4])))
    if e.get("estado") == "APROBADO_CON_VERIFICACION" and (cf.get("verificacion") or {}).get("decision") != "APRUEBA":
        H("aprobado con verificación, pero la verificación APRUEBA no está registrada (`pc verificar`)")
    # No son pendientes del QA (no se advierten): campos que el pipeline agregó después de publicar (dependencias medidas,
    # CP-05.aplicacion) ni diferencias con una copia local de este equipo. Solo lo que el QA dejó abierto en su reporte.
    return out


def cotejo(md, n, k, vk, co, ruta, flujos_ok, verificado, detalle):
    """Hallazgos del cotejo de una tabla publicado. `detalle` = filas del lector (ejemplo_real por diferencia)."""
    e, out = co.get("encabezado") or {}, []
    H = lambda p, q=None: out.append(hallazgo(md, n, k, "Cotejo Stratio ↔ Fabric", ruta, p, q, vk))
    if (e.get("flujo") or {}).get("fabric") not in flujos_ok:
        H(f"el cotejo es del flujo {(e.get('flujo') or {}).get('fabric')}: enlace equivocado")
    if str(e.get("version")) != str(vk):
        H(f"el archivo dice v{e.get('version')} y el enlace es v{vk}")
    if e.get("estado") in ABIERTOS:
        H(f"estado {e['estado']}: la tabla no está cerrada")
    if e.get("faltantes"):
        H("faltantes: " + "; ".join(map(str, e["faltantes"][:6])))
    if e.get("sin_analizar"):
        H("controles sin analizar: " + ", ".join(map(str, e["sin_analizar"])))
    js = co.get("justificaciones") or []
    ids = lambda xs: ", ".join(f"{j.get('id')} {j.get('control')}" for j in xs)
    for dec in ("PENDIENTE", "DEVUELTO"):
        xs = [j for j in js if j.get("decision") == dec]
        if xs:
            H(f"{len(xs)} diferencia(s) {dec}: {ids(xs)}")
    xs = [j for j in js if j.get("decision") == "A_VERIFICAR"]
    if xs and not verificado:
        H(f"{len(xs)} diferencia(s) A_VERIFICAR sin la verificación APRUEBA del flujo: {ids(xs)}")
    xs = [x for x in detalle or [] if x.get("ejemplo_real") is False]
    if xs:
        H(f"{len(xs)} diferencia(s) sin ejemplo real Stratio | Fabric: {ids(xs)}",
          f"registrar el ejemplo (`pc comparar --clave {k}` → `pc diferencia …`) y volver a publicar sobre este mismo enlace "
          f"(misma versión v{vk})")
    return out


def mensajes(hallazgos, carpeta, lote):
    """Un mensaje por QA y trabajo, listo para pasárselo: qué enlace, qué tiene y qué hacer (sobre el mismo enlace)."""
    os.makedirs(carpeta, exist_ok=True)
    por = {}
    for h in hallazgos:
        por.setdefault((h["qa"], h["trabajo"]), []).append(h)
    rutas = []
    for (qa, t), hs in sorted(por.items(), key=lambda x: str(x[0])):
        lin = [f"# Acta del lote {lote} · correcciones para {qa} (trabajo {t})", "",
               f"El acta del lote {lote} se generó igual; estos enlaces de tu EXITOSOS necesitan corrección. Corrige en tu "
               "trabajo y vuelve a publicar **sobre el mismo enlace** (misma ruta y versión, sin abrir ciclo nuevo). "
               "Cuando estén, avísame y regenero el acta con el mismo enlace.", ""]
        enl = {}
        for h in hs:
            enl.setdefault((h["flujo"], h["tabla"], h["documento"], h["ruta"]), []).append(h)
        for (fl, tb, doc, ruta), xs in enl.items():
            lin.append(f"## {fl}" + (f" · {tb}" if tb else "") + f" · {doc}")
            lin.append(f"- Enlace: {xs[0]['enlace'] or 'sin enlace'}")
            lin.append(f"- Ruta: `{ruta}`")
            for x in xs:
                lin.append(f"- {x['problema']}")
            for q in dict.fromkeys(x["que_hacer"] for x in xs):
                lin.append(f"- Qué hacer: {q}")
            lin.append("")
        p = os.path.join(carpeta, f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', str(t))}.md")
        open(p, "w", encoding="utf8").write("\n".join(lin))
        rutas.append(p)
    return rutas


def guardar(hallazgos, carpeta_acta, lote):
    json.dump(hallazgos, open(os.path.join(carpeta_acta, "advertencias.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    d = os.path.join(carpeta_acta, "mensajes")
    if os.path.isdir(d):                       # los mensajes son del último repaso: los de un enlace ya corregido no quedan
        for x in os.listdir(d):
            if x.endswith(".md"):
                os.remove(os.path.join(d, x))
    return mensajes(hallazgos, d, lote)
