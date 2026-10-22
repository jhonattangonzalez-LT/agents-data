"""Acta de entrega de flujos · formato normalizado (Lote 9 v2.0 en adelante). Copia en el repo del generador de
qa-etl-validador-agent-v2/actas/generar_acta_normalizada.py (2026-10-22) para que todo el equipo la tenga:
el dato del acta lo arma `pc/acta.py` desde los trabajos del pipeline (reportes v4 locales), sin scripts por lote.

    python -m pc acta generar --lote N [--trabajos T1,T2] [--version 1.0]

Estructura fija (pedida por el cliente el 2026-09-29):
  Portada · Control de versiones · Participantes
  1. Objeto del acta
  2. Resumen de resultados                       indicadores + graficas
  3. Flujos entregados                           3.1 ingesta · 3.2 analitica · 3.3 orquestadores:
                                                 nombre en Fabric, nombre en Stratio, FL-0xxx, capa
  4. Ejecucion de los flujos                     corrida, inicio, duracion, dependencias + grafica
  5. Cotejo de tablas completas por flujo        por objeto: capa, filas a cada lado, columnas
                                                 identicas, huella, resultado + grafica
  6. Controles de calidad                        ingesta VG, ID y CP · analitica VG e ID
  7. Diferencias y su justificacion              puntual: diferencia, ejemplo de la comparacion,
                                                 justificacion en una linea
  8. Declaracion y aprobacion                    firmas
  9. Anexo de evidencia                          todos los enlaces, por flujo y objeto, al lakehouse,
                                                 verificados con HEAD (ninguno roto)
"""
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import graficas as G  # noqa: E402
import graficas_acta as GA  # noqa: E402
import capas as CAPAS  # noqa: E402
from pc.acceso.fabric import portal_archivo as url  # noqa: E402
from lector_formato2 import resumir  # noqa: E402
from estilo import (AZUL, GRIS, TINTA, FONDO_OK, FONDO_AV, FONDO_QD, run, parrafo, h1, h2, tabla, enlace,  # noqa: E402
                    imagen, pie_grafica, firmas, salto, guardar, _abrir_tabla, celda, FONDO_CAB,
                    _celda_xml, ORIGEN, DESTINO, FONDO_VAL, VERDE)


def _tabla_dif_compacta(filas, anchos=(2500, 3700, 3600)):
    """(lote 12 v1.0, L["sec7_compacta"]) Punto 7 compacto: una fila por diferencia con
    [titulo, diferencia, ejemplo, justificacion corta, decision]. El ejemplo «clave · Stratio: x · Fabric: y»
    se muestra como dos lineas enfrentadas con el color de cada lado."""
    def corta(v, n=170):
        v = str(v).strip()
        return v if len(v) <= n else v[:n - 1].rstrip(" ,;·") + "…"

    def ejemplo(txt):
        t = str(txt or "")
        i, j = t.find(" · Stratio: "), t.rfind(" · Fabric: ")
        if i < 0 or j <= i:
            return [parrafo(run(corta(t, 260), 16), despues=0, linea=240)]
        clave, vs, vf = corta(t[:i], 120), corta(t[i + 12:j]), corta(t[j + 11:])
        ps = []
        if clave:
            ps.append(parrafo(run(clave, 15, GRIS, i=True), despues=40, linea=240))
        ps.append(parrafo(run("STRATIO  ", 14, ORIGEN, b=True) + run(vs, 16), despues=30, linea=240))
        ps.append(parrafo(run("FABRIC  ", 14, DESTINO, b=True) + run(vf, 16), despues=0, linea=240))
        return ps
    xml = [_abrir_tabla(list(anchos))]
    xml.append("<w:tr><w:trPr><w:tblHeader/></w:trPr>" + "".join(
        celda(c, anchos[k], FONDO_CAB, b=True, color=AZUL)
        for k, c in enumerate(["Diferencia", "Ejemplo de la comparación", "Justificación"])) + "</w:tr>")
    for tit, dif, ej, js, dec in filas:
        xml.append("<w:tr><w:trPr><w:cantSplit/></w:trPr>"
                   + _celda_xml([parrafo(run(tit, 16, AZUL, b=True), despues=40, linea=240),
                                 parrafo(run(dif, 16), despues=0, linea=240)], anchos[0])
                   + _celda_xml(ejemplo(ej), anchos[1], FONDO_VAL)
                   + _celda_xml([parrafo(run("✔ ", 16, VERDE, b=True) + run(js, 16), despues=40, linea=240),
                                 parrafo(run(dec, 14, GRIS), despues=0, linea=240)], anchos[2])
                   + "</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + parrafo(run("", 8), despues=0)
PARTICIPANTES, FIRMAS = [], []      # los pone pc/acta.py desde config/acta.json (L["participantes"]); sin firmas por defecto

REP = os.path.join(os.path.expanduser("~"), "Projects", "reportes")   # pc/acta.py lo cambia a lotes/<N>/acta
GRUPOS = [("ingesta", "Ingesta"), ("analitica", "Analítica"), ("orquestadores", "Orquestadores")]
CRIT = {"ingesta": "VG, ID y CP · paridad exacta del dato", "analitica": "VG e ID · pruebas de integración; filas informativas",
        "orquestadores": "ejecución terminada en Completed"}
HIST9 = [
    ["1.0", "2026-09-26", "Emisión del acta de entrega del lote 9."],
    ["1.1–1.6", "2026-09-27/28", "Ajustes de alcance y de la ejecución por flujo, sin cambio en las cifras de la entrega."],
    ["1.7", "2026-09-28", "El punto de evidencia enlaza el cotejo de valor y el cotejo por flujo."],
]
HIST6 = [
    ["1.0", "2026-09-21", "Emisión del acta de entrega del lote 6: la extracción completa de Novar, 16 flujos de analítica "
                          "de agrupadoras, contactabilidad y globales, y los dos orquestadores de contactabilidad."],
    ["1.1", "2026-09-24", "Se cierra la verificación de la ingesta de Novar: el origen corrige el reporte 315 DANE y las 30 "
                          "salidas quedan cotejadas con sus controles CP, ID y VG."],
]
HIST8 = [
    ["1.0", "2026-09-25", "Emisión del acta de entrega del lote 8, con el resultado de la ejecución y de la "
                          "verificación de los flujos entregados y de sus tablas de salida."],
]
HIST7 = [
    ["1.0", "2026-09-24", "Emisión del acta de entrega del lote 7, con la ejecución y la verificación de los flujos "
                          "de analítica de familias, afiliados, empresas, servicios y tableros."],
]
HIST = {6: HIST6, 7: HIST7, 8: HIST8, 9: HIST9}
DESC = {
    6: "Formato normalizado. Se reemplaza la estructura de diez puntos por la de nueve: flujos separados en ingesta, "
       "analítica y orquestadores con su nombre en Fabric y en Stratio, su código FL y su capa; ejecución y cotejo de "
       "tablas completas por flujo, cada uno con su gráfica; capa por tabla; diferencias puntuales con el ejemplo de la "
       "comparación y su justificación en una línea. Se integran en el acta la validación de la ingesta de Novar del 24 "
       "de septiembre y el anexo de enlaces del lote, y el punto 9 reúne todos los enlaces al lakehouse verificados uno "
       "por uno. Las cifras de Novar son las del cotejo cerrado el 24 de septiembre, con el reporte 315 DANE ya corregido "
       "en el origen.",
    8: "Normalización de formato, sin cambios en las cifras de la entrega. Se reemplaza la estructura de diez puntos "
       "por la de nueve: flujos separados en ingesta, analítica y orquestadores con su nombre en Fabric y en Stratio, "
       "su código FL y su capa; ejecución y cotejo de tablas completas por flujo, cada uno con su gráfica; capa por "
       "tabla; diferencias puntuales con el ejemplo de la comparación y su justificación en una línea; y un anexo con "
       "todos los enlaces al lakehouse, verificados uno por uno. El alcance queda en los 38 flujos del lote —los dos "
       "flujos de SAP PSCD que la versión 1.0 recogía se entregan en el lote 9—, y se incorporan las dos salidas del "
       "lote cuya medición se cerró después de la emisión: silver.aportes_aportes y "
       "silver.mercadeo_transacciones_en_linea_ventas.",
    7: "Formato normalizado, con la evidencia del lote completada. Se reemplaza la estructura de diez puntos por la de "
       "nueve: flujos separados en ingesta, analítica y orquestadores con su nombre en Fabric y en Stratio, su código FL "
       "y su capa; ejecución y cotejo de tablas completas por flujo, cada uno con su gráfica; capa por tabla; diferencias "
       "puntuales con el ejemplo de la comparación y su justificación en una línea; y un anexo con todos los enlaces al "
       "lakehouse, verificados uno por uno. Las tablas que a la fecha de entrega -24 de septiembre, 17:40- no tenían un "
       "cotejo Stratio ↔ Fabric propio se volvieron a ejecutar en el área de trabajo de calidad y se cotejaron de nuevo: "
       "el acta cita, por tabla, la medición del origen, la medición del destino y el cotejo que las compara, los tres "
       "salidos de la misma corrida.",
    9: "Formato normalizado: flujos por ingesta, analítica y orquestadores con su nombre en Fabric y en Stratio, su código FL "
       "y su capa; cotejo de tablas completas y ejecución por flujo con gráficas; diferencias puntuales con el ejemplo de la "
       "comparación; anexo con todos los enlaces al lakehouse, verificados uno por uno. Se completan los anexos de cotejo de "
       "valor y de cotejo por flujo.",
}


# ── formato ───────────────────────────────────────────────────────────────────
def n(v):
    if v is None:
        return "no aplica"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(v):,}".replace(",", ".")


PCT_DEC = 2          # un lote puede pedir más decimales con L["pct_decimales"] (lote 11 v1.1: 4, el valor del JSON sin redondear)


def pct(v):
    return "no aplica" if v is None else (v if isinstance(v, str) else f"{v:.{PCT_DEC}f}%".replace(".", ","))


def seg(a, b):
    import datetime as dt
    if not a or not b:
        return None
    f = lambda s: dt.datetime.fromisoformat(str(s)[:19])
    return int((f(b) - f(a)).total_seconds())


def dur(s):
    return "no registrada" if s is None else (f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s")


def hora(s):
    return str(s)[:16].replace("T", " ") + " UTC" if s else "no registrada"


def ver_txt(v):
    return {"APROBADO": "Aprobado", "APROBADO_CON_JUSTIFICACION": "Aprobado con justificación",
            "APROBADO_CON_VERIFICACION": "Aprobado con verificación de QA"}.get(v, v)


def filas_compactas(dif):
    """Punto 7 compacto: agrupa por (tabla, causa final); cada grupo con sus Dn y controles, la cifra del primero, el
    mejor ejemplo real y la justificación corta (a mano en justif_corta_loteN.py o resumida de la causa vigente)."""
    grupos = {}
    for o in dif:
        for x in o["detalle_diferencias"]:
            causa = x.get("causa_final") or x.get("justificacion_corta") or x["justificacion"]
            grupos.setdefault((o["clave"], causa), []).append(x)
    out = []
    for (clave, causa), xs in grupos.items():
        ids = ", ".join(x["id"] for x in xs)
        ctl = ", ".join(dict.fromkeys(x["control"] for x in xs))
        ej = next((x for x in xs if x.get("ejemplo_real")), xs[0])
        dif_ = xs[0].get("diferencia_corta") or resumir(xs[0]["diferencia"], 200)
        if len(xs) > 1:
            dif_ += f" ({len(xs)} diferencias con la misma causa)"
        js = xs[0].get("justificacion_corta") or xs[0].get("justificacion_corta_auto") or resumir(causa, 240)
        out.append([f"{clave}\n{ids} · {ctl}", dif_, ej["ejemplo"], js, xs[-1].get("decision_txt") or ""])
    return out


def filas_por_tabla(dif):
    """Punto 7 resumido (por defecto desde 2026-10-22, pedido de QA: «la sección 7 está demasiado extensa»): una fila por
    tabla con cuántas diferencias tiene y de qué controles, la cifra de la principal, un ejemplo real Stratio | Fabric y la
    justificación final (la vigente con la que se aprobó) de la diferencia principal, resumida. Cada diferencia, con su
    causa completa, está en el cotejo enlazado."""
    out = []
    for o in dif:
        xs = o["detalle_diferencias"]
        ppal = max(xs, key=lambda x: (x.get("decision") == "JUSTIFICADA", x.get("filas_afectadas") or 0))
        ult = ppal
        ej = next((x for x in [ppal] + xs if x.get("ejemplo_real") or (" · Stratio: " in str(x.get("ejemplo")))), ppal)
        ids = xs[0]["id"] if len(xs) == 1 else f"{xs[0]['id']}–{xs[-1]['id']}"
        ctl = ", ".join(dict.fromkeys(x["control"] for x in xs))
        dif_ = ppal.get("diferencia_corta") or resumir(ppal["diferencia"], 200)
        if len(xs) > 1:
            dif_ = f"{len(xs)} diferencias ({ctl}). La principal: {dif_}"
        causa = ult.get("justificacion_corta") or ult.get("justificacion_corta_auto") or resumir(ult.get("causa_final") or ult["justificacion"], 240)
        otras = len({(x.get("causa_final") or x.get("justificacion_corta") or x["justificacion"]) for x in xs}) - 1
        if otras > 0:
            causa += f" Las otras {otras} causa(s) están medidas en el cotejo enlazado en el anexo."
        out.append([f"{o['clave']}\n{ids} · {ctl}", dif_, ej["ejemplo"], causa, ult.get("decision_txt") or ""])
    return out


def cp05_txt(c):
    """CP-05 en una línea: si aplica, con qué se probó; si no aplica, por qué (y que no bloquea)."""
    if not c:
        return "sin dato en el cotejo"
    r = c.get("resultado")
    como = (c.get("como_se_prueba") or "").split(":")[0]
    if r == "no_aplica" or c.get("aplica") is False:
        return f"no aplica: {c.get('por_que') or c.get('detalle') or 'sin corrida que citar'} · no bloquea"
    if r in ("ok", "justificado"):
        return ("cumple" if r == "ok" else "justificado") + (f" · {como}" if como else "")
    return f"{(r or 'sin resultado').replace('_', ' ')}" + (f" · {c.get('detalle')}" if c.get("detalle") else "")


def ruta_corta(r):
    t, _, x = str(r).partition(":")
    return {"hdfs": "HDFS", "pg": "Postgres", "pgsql": "Postgres", "pgfab": "Postgres", "delta": "Delta",
            "files": "Files", "sftp": "SFTP"}.get(t, t) + " · " + x


# ── graficas ──────────────────────────────────────────────────────────────────
ST, FB = (61, 90, 152), (168, 106, 0)          # Stratio azul, Fabric ambar (validados: CVD dE 21,6)


def _barra(d, x0, y0, x1, y1, col):
    """Barra con el extremo de dato redondeado; recta si es tan corta que no cabe el radio."""
    if (x1 - x0) > 5 * G.E:
        d.rounded_rectangle([x0, y0, x1, y1], radius=2 * G.E, fill=col)
    else:
        d.rectangle([x0, y0, max(x1, x0 + G.E), y1], fill=col)


def barras(items, ruta, titulo, sub, valor_txt, ref=None, maximo=None, cierre=None):
    """Barras horizontales, una serie. items = [(etiqueta, valor, color)]."""
    if not items:
        return None
    an, fil = 640, 14
    al = 64 + fil * len(items) + (40 if cierre else 12)
    im, d = G._lienzo(an, al)
    G._txt(d, (0, 4), titulo, G.fuente(13, True), G.AZUL)
    G._txt(d, (0, 26), sub, G.fuente(10), G.GRIS)
    ml, mr = 250, 70
    ancho = an - ml - mr
    mx = maximo or max(v for _, v, _ in items) or 1
    y = 56
    if ref is not None:
        xr = ml + ancho * ref / mx
        d.line([xr * G.E, (y - 4) * G.E, xr * G.E, (y + fil * len(items)) * G.E], fill=G.GRIS_CL, width=2 * G.E)
    for et, v, col in items:
        w = ancho * min(v, mx) / mx
        _barra(d, ml * G.E, y * G.E, (ml + w) * G.E, (y + 9) * G.E, col)
        et = et if len(et) <= 46 else et[:45] + "…"
        G._txt(d, (ml - 6, y + 4), et, G.fuente(8), G.TINTA, "rm")
        G._txt(d, (ml + w + 6, y + 4), valor_txt(v), G.fuente(8), G.GRIS, "lm")
        y += fil
    if cierre:
        y += 8
        d.rectangle([0, y * G.E, an * G.E, (y + 26) * G.E], fill=G.SUAVE)
        d.rectangle([0, y * G.E, 3 * G.E, (y + 26) * G.E], fill=G.AZUL)
        G._txt(d, (10, y + 7), cierre, G.fuente(10, True), G.TINTA)
    return G._guardar(im, ruta)


def pares(items, ruta, titulo, sub):
    """Filas de Stratio y de Fabric enfrentadas por objeto (dos series, leyenda + etiqueta directa)."""
    if not items:
        return None
    an, fil = 640, 22
    al = 84 + fil * len(items) + 12
    im, d = G._lienzo(an, al)
    G._txt(d, (0, 4), titulo, G.fuente(13, True), G.AZUL)
    G._txt(d, (0, 26), sub, G.fuente(10), G.GRIS)
    for i, (t, c) in enumerate((("Stratio", ST), ("Fabric", FB))):
        d.rounded_rectangle([(i * 80) * G.E, 46 * G.E, (i * 80 + 10) * G.E, 56 * G.E], radius=2 * G.E, fill=c)
        G._txt(d, (i * 80 + 14, 51), t, G.fuente(9), G.TINTA, "lm")
    ml, mr = 250, 90
    ancho = an - ml - mr
    mx = max(max(a, b) for _, a, b in items) or 1
    y = 68
    for et, a, b in items:
        for k, (v, c) in enumerate(((a, ST), (b, FB))):
            w = ancho * v / mx
            yy = y + k * 9
            _barra(d, ml * G.E, yy * G.E, (ml + w) * G.E, (yy + 7) * G.E, c)
            G._txt(d, (ml + w + 5, yy + 3), n(v), G.fuente(7), G.GRIS, "lm")
        et = et if len(et) <= 46 else et[:45] + "…"
        G._txt(d, (ml - 6, y + 8), et, G.fuente(8), G.TINTA, "rm")
        y += fil
    return G._guardar(im, ruta)


# ── documento ─────────────────────────────────────────────────────────────────
class Doc:
    def __init__(self, img_dir):
        self.d, self.img, self.rels, self.pie, self.rid, self.dir = [], {}, {}, 0, 0, img_dir
        os.makedirs(img_dir, exist_ok=True)

    def add(self, x):
        self.d.append(x)

    def grafica(self, ruta, texto):
        """Una ruta o una lista (gráfica partida en hojas: «hoja k de n»). Se escala por el ancho real del PNG, así una
        imagen a doble resolución sale nítida y del mismo tamaño en la hoja."""
        rutas = [r for r in (ruta if isinstance(ruta, (list, tuple)) else [ruta]) if r]
        if not rutas:
            return
        self.pie += 1
        from PIL import Image
        for k, r in enumerate(rutas, 1):
            rid = f"rIdG{self.pie}{k:02d}"
            self.img[rid] = r
            an, al = Image.open(r).size
            self.add(imagen(rid, 640, int(al * 640 / an), texto))
            self.add(pie_grafica(f"Gráfica {self.pie}" + (f" (hoja {k} de {len(rutas)})" if len(rutas) > 1 else "") + f". {texto}"))

    def link(self, texto, rel_files):
        self.rid += 1
        rid = f"rIdU{self.rid}"
        self.rels[rid] = url(rel_files)
        return enlace(texto, rid)


def tabla_links(D, cab, filas, anchos):
    """filas: [(c1, c2, texto, ruta_files)] -> tabla con el enlace en la tercera columna."""
    xml = [_abrir_tabla(anchos), "<w:tr><w:trPr><w:tblHeader/></w:trPr>"
           + "".join(celda(c, anchos[i], FONDO_CAB, b=True, color=AZUL) for i, c in enumerate(cab)) + "</w:tr>"]
    for a, b, txt, r in filas:
        cel = (f'<w:tc><w:tcPr><w:tcW w:w="{anchos[2]}" w:type="dxa"/></w:tcPr>'
               '<w:p><w:pPr><w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/></w:pPr>'
               + D.link(txt, r) + "</w:p></w:tc>")
        xml.append("<w:tr>" + celda(a, anchos[0], "FFFFFF", b=True, color=AZUL, sz=16) + celda(b, anchos[1], sz=16)
                   + cel + "</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + parrafo(run("", 8), despues=0)


def acta(L):
    global PCT_DEC
    lote, fecha, ver = L["lote"], L["fecha"], L["version"]
    PCT_DEC = L.get("pct_decimales", 2)
    participantes = L.get("participantes") or [list(p) for p in PARTICIPANTES]
    bloques_firma = L.get("firmas") or FIRMAS
    # con pendientes (lote 11 v1.1) el punto 8 es «Pendientes» y la declaración y el anexo pasan a 9 y 10
    # con atención de observaciones del cliente (lote 6 v2.2) también: el punto 8 es «Atención de observaciones»
    P_DECL, P_ANEXO = (9, 10) if (L.get("pendientes") or L.get("observaciones")) else (8, 9)
    # con anexo de hallazgos atendidos (lote 10 v1.2): 10 = anexo de hallazgos, 11 = anexo de evidencia (al final)
    P_HALL = None
    if L.get("anexo_hallazgos"):
        P_HALL, P_ANEXO = P_ANEXO, P_ANEXO + 1
    RET = L.get("retirados") or []
    # una versión nueva puede pedir su propia carpeta de gráficas para no pisar la de la versión anterior (lote 6 v2.2)
    D = Doc(f"{REP}/{L['graficas_dir']}" if L.get("graficas_dir") else f"{REP}/graficas_acta_lote{lote}")
    F = {g: [f for f in L["flujos"] if f["grupo"] == g] for g, _ in GRUPOS}
    OB = {g: [o for f in F[g] for o in f["objetos"]] for g, _ in GRUPOS}
    tot = len(L["flujos"])
    nobj = sum(len(v) for v in OB.values())

    # portada
    D.add(parrafo(run("Proyecto de Migración de la Plataforma de Datos  ·  Stratio → Microsoft Fabric", 17, GRIS), antes=40, despues=600))
    D.add(parrafo(run("ACTA DE ENTREGA DE FLUJOS", 60, AZUL, b=True), antes=800, despues=40, linea=240))
    D.add(parrafo(run(f"Lote {lote} · {tot} flujos entregados en el ambiente de QA: {len(F['ingesta'])} de ingesta, "
                      f"{len(F['analitica'])} de analítica y {len(F['orquestadores'])} orquestadores"
                      + (f" · {len(RET)} {L.get('retirados_portada') or 'retirados del lote'}" if RET else ""), 28, TINTA, b=True), despues=60, linea=260))
    ncot = sum(1 for g in ("ingesta", "analitica") for o in OB[g] if o.get("filas_s") is not None)
    D.add(parrafo(run((f"{nobj} tablas cotejadas completas contra Stratio" if ncot == nobj else
                       f"{nobj} tablas verificadas completas, {ncot} de ellas cotejadas contra Stratio")
                      + " · ingesta por VG, ID y CP · analítica por VG e ID · orquestadores por ejecución",
                      22, GRIS), despues=400, linea=260))
    D.add(parrafo(run("COMFANDI  /  QUIND S.A.S.", 20, TINTA, b=True), despues=200))
    for t in ("Equipo Quind · VMQA", f"Versión {ver} · Fecha: {fecha}", "Ambiente: QA · Aprobación para el despliegue a producción"):
        D.add(parrafo(run(t, 18, GRIS), despues=120))
    if L.get("portada_nota"):                       # qué cambia en esta versión, dicho en la presentación (lote 6 v2.2)
        D.add(parrafo(run(L["portada_nota"], 18, TINTA), despues=120, linea=260))
    D.add(parrafo(run("Confidencial", 18, GRIS), despues=200))
    D.add(salto())

    D.add(h1("Control de versiones"))
    hist = (L.get("historial") or HIST.get(lote, [])) + [[ver, fecha, L.get("descripcion_version") or DESC.get(lote, f"Emisión del acta de entrega del lote {lote} en el formato normalizado.")]]
    D.add(tabla(["Versión", "Fecha", "Descripción"], hist, [1300, 1700, 6800], negritas={i: {0} for i in range(len(hist))},
                fondos={len(hist) - 1: FONDO_QD}))
    if L.get("reemplazos"):
        D.add(parrafo(run("Evidencia de la versión anterior que esta versión reemplaza (queda como antecedente). Filas Stratio → "
                          "Fabric y resultado de cada tabla.", 20)))
        D.add(tabla(["Flujo · tabla", "Versión anterior", f"Versión {ver}"], [list(r) for r in L["reemplazos"]],
                    [3800, 3000, 3000], monos={0}))
    D.add(h1("Participantes"))
    D.add(tabla(["Nombre", "Organización", "Rol"], [list(p) for p in participantes], [3600, 2600, 3600],
                negritas={i: {0} for i in range(len(participantes))}))

    # 1 · objeto
    D.add(h1("1. Objeto del acta"))
    D.add(parrafo(run(
        f"Dejar constancia de la verificación de los {tot} flujos del lote {lote} de la migración de la plataforma de datos de "
        "Comfandi y solicitar la aprobación para su despliegue a producción. Cada flujo se ejecutó en el ambiente de QA de "
        "Microsoft Fabric y cada tabla que escribe se cotejó completa contra su contraparte en Stratio.", 20)))
    if L.get("nota_objeto"):
        D.add(parrafo(run(L["nota_objeto"], 20)))
    D.add(tabla(["Grupo", "Flujos", "Tablas cotejadas", "Criterio de aprobación"],
                [[t, str(len(F[g])), str(len(OB[g])) if g != "orquestadores" else "no escriben tablas", CRIT[g]] for g, t in GRUPOS],
                [1800, 1100, 1900, 5000], negritas={0: {0}, 1: {0}, 2: {0}}))

    # 2 · resumen
    D.add(h1("2. Resumen de resultados"))
    todos = [o for g in ("ingesta", "analitica") for o in OB[g]]
    exactas = [o for o in todos if o["filas_s"] == o["filas_f"]]
    hash_ok = [o for o in OB["ingesta"] if o.get("hash_igual")]
    vg_med = [o for o in todos if o.get("vg") is not None]
    vg_ok = [o for o in vg_med if o["vg"] in (100.0, 100)]
    fs, ff = sum(o["filas_s"] or 0 for o in todos), sum(o["filas_f"] or 0 for o in todos)
    D.add(tabla(["Indicador", "Resultado"], [
        ["Flujos entregados", f"{tot}: {len(F['ingesta'])} de ingesta, {len(F['analitica'])} de analítica, {len(F['orquestadores'])} orquestadores"],
        ["Ejecución en QA", f"{sum(1 for f in L['flujos'] if f['ejecucion'].get('estado') == 'Completed')} de {tot} con su " + ("corrida verificada" if L.get("ejecucion_verificada") else "última corrida") + " en Completed"],
        ["Tablas cotejadas completas", f"{ncot} de {len(todos)} · {len(exactas)} con las mismas filas en los dos lados"
                                      if ncot != len(todos) else f"{len(todos)} · {len(exactas)} con las mismas filas en los dos lados"],
        ["Filas cotejadas", f"Stratio {n(fs)} · Fabric {n(ff)}"],
        ["Huella del dato (ingesta)", f"{len(hash_ok)} de {len(OB['ingesta'])} tablas con huella idéntica"],
        ["VG sin fallas", L.get("vg_resumen") or f"{len(vg_ok)} de {len(vg_med)} tablas evaluadas"],
        ["Veredicto", f"{sum(1 for f in L['flujos'] if f['veredicto'] == 'APROBADO')} aprobados · "
                      f"{sum(1 for f in L['flujos'] if f['veredicto'] == 'APROBADO_CON_JUSTIFICACION')} aprobados con justificación"
                      + (f" · {sum(1 for f in L['flujos'] if f['veredicto'] == 'APROBADO_CON_VERIFICACION')} aprobados con verificación de QA"
                         if any(f['veredicto'] == 'APROBADO_CON_VERIFICACION' for f in L['flujos']) else "")]]
        + [list(x) for x in (L.get("resumen_extra") or [])],
        [3200, 6600], negritas={i: {0} for i in range(7 + len(L.get("resumen_extra") or []))}))
    items = [(t, len(F[g]), (G.AZUL_CL if g == "ingesta" else FB if g == "analitica" else G.GRIS)) for g, t in GRUPOS if F[g]]
    D.grafica(GA.barras(items, f"{D.dir}/g_grupos", "Flujos entregados por grupo",
                     f"{tot} flujos · cada grupo se aprueba con su propio criterio",
                     lambda v: f"{v:.0f} flujo" + ("s" if v != 1 else "")),
              "Flujos entregados por grupo. La longitud de cada barra es el número de flujos del grupo.")

    # 3 · flujos entregados
    D.add(h1("3. Flujos entregados"))
    D.add(parrafo(run("Cada flujo con su nombre en Fabric, su nombre en Stratio, su código FL y la capa del lakehouse en la que "
                      "escribe. Cuando un dato no está asignado en el inventario se indica expresamente.", 20)))
    con_reval = any(f.get("revalida_txt") for f in L["flujos"])
    if con_reval:
        D.add(parrafo(run("La columna «Revalidación del lote» indica el lote y la versión del acta de origen que el flujo "
                          "revalida, con el veredicto que tenía en esa acta; si aparece en más de una, se listan todas.", 20)))
    k = 0
    for g, t in GRUPOS:
        if not F[g]:
            continue
        k += 1
        D.add(h2(f"3.{k}  {t} · {len(F[g])} flujo" + ("s" if len(F[g]) != 1 else "")))
        filas = [[f["fabric"], f["stratio"] or "sin nombre en el inventario", f["fl"] or L.get("fl_vacio", "sin código FL asignado"), f["capa"],
                  str(len(f["objetos"])) if g != "orquestadores" else "orquesta", ver_txt(f["veredicto"])] for f in F[g]]
        if con_reval:
            # lote y acta de origen que el flujo revalida, y el veredicto que tenía allí (buscado en los datos de esas actas)
            for fila, f in zip(filas, F[g]):
                fila.insert(4, f.get("revalida_txt") or "sin acta anterior")
            D.add(tabla(["Flujo en Fabric", "Flujo en Stratio", "Código", "Capa", "Revalidación del lote", "Tablas", "Veredicto"],
                        filas, [2050, 2050, 850, 750, 2100, 650, 1350], monos={0, 1}))
            continue
        D.add(tabla(["Flujo en Fabric", "Flujo en Stratio", "Código", "Capa", "Tablas", "Veredicto"], filas,
                    [2500, 2500, 1100, 1100, 700, 1900], monos={0, 1}))
    SEC3 = {g: f"3.{i + 1}" for i, g in enumerate(g for g, _ in GRUPOS if F[g])}
    if RET:
        k += 1
        SEC3["retirados"] = f"3.{k}"
        D.add(h2(f"3.{k}  {L.get('titulo_retirados') or 'Retirados del lote'} · {len(RET)} flujo" + ("s" if len(RET) != 1 else "")))
        D.add(parrafo(run(L.get("nota_retirados") or "Flujos que estaban en la versión anterior del acta y que esta versión retira "
                          "del lote. No se aprueban en esta acta y sus enlaces no se listan como evidencia aprobada.", 20)))
        D.add(tabla(["Flujo en Fabric", "Flujo en Stratio", "Código", "Capa", "Tablas", "Estado"],
                    [[r["fabric"], r["stratio"], r["fl"], r["capa"], str(len(r["tablas"])), r["estado"]] for r in RET],
                    [2500, 2500, 1100, 1100, 700, 1900], monos={0, 1}))
    for FL_ in L.get("fuera_lote") or []:        # (lote 7 v2.3) flujos que salen a otro lote: se listan sin enlaces
        k += 1
        SEC3[FL_["clave"]] = f"3.{k}"
        n_ = len(FL_["flujos"])
        D.add(h2(f"3.{k}  {FL_['titulo']} · {n_} flujo" + ("s" if n_ != 1 else "")))
        D.add(parrafo(run(FL_["nota"], 20)))
        D.add(tabla(["Flujo en Fabric", "Flujo en Stratio", "Código", "Capa", "Tablas", "Estado"],
                    [[r["fabric"], r["stratio"], r["fl"], r["capa"], str(len(r["tablas"])), r["estado"]] for r in FL_["flujos"]],
                    [2500, 2500, 1100, 1100, 700, 1900], monos={0, 1}))

    # 4 · ejecucion
    D.add(h1("4. Ejecución de los flujos"))
    D.add(parrafo(run("Corrida verificada de cada flujo en el ambiente de QA —la que escribió la versión Delta medida—: estado, inicio, duración, versión Delta y lo que se ejecutó delante." if L.get("ejecucion_verificada") else "Última corrida de cada flujo en el ambiente de QA: estado, inicio, duración y lo que se ejecutó delante.", 20)))
    if L.get("nota_ejecucion"):
        D.add(parrafo(run(L["nota_ejecucion"], 20)))
    k = 0
    for g, t in GRUPOS:
        if not F[g]:
            continue
        k += 1
        D.add(h2(f"4.{k}  {t}"))
        filas = []
        for f in F[g]:
            e = f["ejecucion"]
            dep = ", ".join(f"{a} ({b})" for a, b in (e.get("dependencias") or [])) or (
                f"{e['corridas']} corrida" + ("s" if e["corridas"] != 1 else "") + " en QA"
                if e.get("corridas") else "sin dependencias")
            if e.get("lanzado_por"):
                dep += " · corrida de desarrollo"
            if e.get("delta"):
                dep = e["delta"] + " · " + dep
            if e.get("dependencias_txt"):
                dep = e["dependencias_txt"]
            filas.append([f["fabric"], e.get("estado") or "no registrada", hora(e.get("inicio")), dur(seg(e.get("inicio"), e.get("fin"))), dep])
        D.add(tabla(["Flujo", "Estado", "Inicio", "Duración", "Dependencias"], filas, [2700, 1100, 1900, 1200, 2900], monos={0}))
        its = [(f["fabric"], (seg(f["ejecucion"].get("inicio"), f["ejecucion"].get("fin")) or 0) / 60, FB if g == "analitica" else G.AZUL_CL)
               for f in F[g] if seg(f["ejecucion"].get("inicio"), f["ejecucion"].get("fin"))]
        its.sort(key=lambda x: -x[1])
        if its:
            tm = sum(v for _, v, _ in its)
            D.grafica(GA.barras(its, f"{D.dir}/g_dur_{g}", f"Duración de la {'corrida verificada' if L.get('ejecucion_verificada') else 'última corrida'} · {t.lower()}",
                             (f"{len(its)} flujo" + ("s" if len(its) != 1 else "") + f" · {tm:.1f} minutos en total").replace(".", ","), lambda v: f"{v:.1f} min".replace(".", ","),
                             cierre=f"El más largo {its[0][1]:.1f} min · el más corto {its[-1][1]:.1f} min".replace(".", ",")),
                      f"Duración de la {'corrida verificada' if L.get('ejecucion_verificada') else 'última corrida'} de cada flujo de {t.lower()}, en minutos. La barra más larga es la corrida que más tardó.")

    # dependencias entre flujos (medidas con pc dependencias): directas = misma cascada, indirectas = alimentan sus entradas
    con_dep = [f for f in L["flujos"] if (f["ejecucion"].get("dependencias_medidas") or {}).get("estado") == "MEDIDO"]
    if con_dep:
        k += 1
        D.add(h2(f"4.{k}  Dependencias entre flujos"))
        D.add(parrafo(run("Directa: el flujo que escribe una de sus entradas corre en la misma cascada (un orquestador invoca a los "
                          "dos y el productor va antes); se ejecutan juntos y en ese orden. Indirecta: el flujo que escribe la "
                          "entrada la alimenta, pero corre por su cuenta. Medido sobre las definiciones de Fabric: quién escribe "
                          "cada entrada sale del código del flujo o del destino de la copia, no del nombre del parámetro.", 20)))
        D.add(tabla(["Flujo", "Directas (cascada)", "Indirectas (alimentan sus entradas)", "Entradas sin flujo productor"],
                    [[f["fabric"],
                      (", ".join(dm["directas"]) + (f" · {', '.join(dm['cascada'])}" if dm["cascada"] else "")) if dm["directas"] else "ninguna",
                      ", ".join(dm["indirectas"]) or "ninguna",
                      (", ".join(dm["sin_productor"][:3]) + (" …" if len(dm["sin_productor"]) > 3 else "")) if dm["sin_productor"] else "ninguna"]
                     for f in con_dep for dm in [f["ejecucion"]["dependencias_medidas"]]],
                    [2500, 2400, 2700, 2200], monos={0}))
        nd = sum(1 for f in con_dep if f["ejecucion"]["dependencias_medidas"]["directas"])
        ni = sum(1 for f in con_dep if f["ejecucion"]["dependencias_medidas"]["indirectas"] and not f["ejecucion"]["dependencias_medidas"]["directas"])
        D.grafica(GA.barras([("Con dependencias directas", nd, FB), ("Solo indirectas", ni, G.AZUL_CL),
                             ("Sin dependencias de otros flujos", len(con_dep) - nd - ni, G.GRIS)],
                            f"{D.dir}/g_dependencias", "Dependencias entre flujos", f"{len(con_dep)} flujos con dependencias medidas",
                            lambda v: f"{v:.0f} flujo" + ("s" if v != 1 else "")),
                  "Flujos según sus dependencias. Un flujo con directas debe ejecutarse en su cascada; las indirectas se refrescan por su cuenta.")
    tl = [(f["fabric"], f["ejecucion"].get("inicio"), f["ejecucion"].get("fin"),
           G.AZUL_CL if f["grupo"] == "ingesta" else FB if f["grupo"] == "analitica" else G.GRIS) for f in L["flujos"]
          if f["ejecucion"].get("inicio") and f["ejecucion"].get("fin")]
    D.grafica(GA.linea_tiempo(tl, f"{D.dir}/g_linea_tiempo", "Línea de tiempo de las corridas",
                              "hora real de cada corrida (UTC) y lo que tardó · azul ingesta, ámbar analítica, gris orquestación"),
              "Corridas verificadas en su hora real: qué corrió a la vez, en qué orden y cuánto tardó cada una.")

    # 5 · cotejo de tablas completas
    D.add(h1("5. Cotejo de tablas completas por flujo"))
    D.add(parrafo(run("Cada tabla se midió completa en los dos lados con el mismo motor (conteo, huella por fila y por columna y "
                      "perfil de cada columna) y se cotejó columna a columna. La columna Filas Fabric / Stratio es la proporción "
                      "de filas escritas en Fabric frente a las de Stratio.", 20)))
    if L.get("nota_cotejo"):
        D.add(parrafo(run(L["nota_cotejo"], 20)))
    k = 0
    for g, t in GRUPOS[:2]:
        if not OB[g]:
            continue
        k += 1
        D.add(h2(f"5.{k}  {t} · {len(OB[g])} tablas"))
        filas = []
        for f in F[g]:
            for o in f["objetos"]:
                # una tabla que Stratio no publica se acredita con su registro Delta: se escribe qué pasa, no un guion
                sinc = o["filas_s"] is None
                if o.get("pendiente"):
                    cau = str(o["pendiente"])
                    filas.append([f"{f['fabric']}\n{o['clave']}", o["capa"], "pendiente",
                                  n(o["filas_f"]) if o.get("filas_f") is not None else "pendiente", "medición pendiente",
                                  cau if len(cau) <= 60 else cau[:59].rstrip() + "…", ver_txt(o.get("resultado") or "PENDIENTE")])
                    continue
                filas.append([f"{f['fabric']}\n{o['clave']}", o["capa"],
                              "sin salida en Stratio" if sinc else n(o["filas_s"]), n(o["filas_f"]),
                              "acreditada por el registro Delta" if sinc else pct(o["pct"]),
                              f"{o['cols']} columnas en destino" if sinc else
                              (f"{o['cols_iguales']} de {o['cols']}" if o.get("cols_iguales") is not None else L.get("cols_no_evaluada_txt") or "no se evaluó"),
                              (o.get("huella_txt") or ("idéntica" if o.get("hash_igual") else ("no calculada" if "hash_igual" in o and o["hash_igual"] is None else "distinta"))) if g == "ingesta" else ver_txt(o["resultado"])])
        D.add(tabla(["Flujo · tabla", "Capa", "Filas Stratio", "Filas Fabric", "Fabric / Stratio", "Columnas idénticas",
                     "Huella" if g == "ingesta" else "Resultado"], filas, [2900, 1100, 1250, 1250, 1000, 1100, 1200], monos={0}))
        # enfrentar dos series exige tener las dos: una tabla sin contraparte medida no entra en esta gráfica
        ps = [(o["clave"], o["filas_s"], o["filas_f"]) for o in OB[g] if o["filas_s"] is not None and o["filas_f"] is not None]
        ps.sort(key=lambda x: -max(x[1], x[2]))
        # todas las tablas (en varias hojas si hace falta) y escala logarítmica cuando conviven tablas de tamaños muy distintos
        D.grafica(GA.pares(ps, f"{D.dir}/g_filas_{g}", f"Filas por tabla · {t.lower()}", f"Stratio contra Fabric · {len(ps)} tablas"),
                  f"Filas de cada tabla de {t.lower()} en Stratio (azul) y en Fabric (ámbar), con la diferencia a la derecha. "
                  "Dos barras iguales son la misma cantidad de filas.")
        D.grafica(GA.diferencias(ps, f"{D.dir}/g_dif_{g}", f"Diferencia de filas Fabric − Stratio · {t.lower()}",
                                 "porcentaje sobre las filas de Stratio · a la derecha Fabric tiene más, a la izquierda menos · verde = iguales"),
                  f"Diferencia relativa de filas de cada tabla de {t.lower()}, centrada en cero. Hace visible una diferencia pequeña "
                  "que en la gráfica anterior no se distingue por el tamaño de la tabla.")
        its = [(o["clave"], 100 * o["cols_iguales"] / o["cols"], G.VERDE if o["cols_iguales"] == o["cols"] else FB)
               for o in OB[g] if o.get("cols") and o.get("cols_iguales") is not None]
        its.sort(key=lambda x: x[1])
        D.grafica(GA.barras(its, f"{D.dir}/g_cols_{g}", f"Columnas con perfil idéntico · {t.lower()}",
                         "porcentaje de columnas cuyo perfil (nulos, distintos, mínimo, máximo, suma) coincide en los dos lados",
                         lambda v: f"{v:.0f}%", ref=100, maximo=100),
                  f"Proporción de columnas con perfil idéntico en cada tabla de {t.lower()}. En verde, la tabla con todas sus columnas idénticas.")

    hs = [(f, o) for g, _ in GRUPOS[:2] for f in F[g] for o in f["objetos"] if o.get("hash_s") and o.get("hash_f")]
    if hs:
        k += 1
        D.add(h2(f"5.{k}  Huella SHA-256 del dato · {len(hs)} tablas de los reportes v4"))
        D.add(parrafo(run("SHA-256 canónico del dato completo de cada lado, tal como lo registra el cotejo. En ingesta la huella "
                          "decide (CP-03); en analítica es informativa.", 20)))
        D.add(tabla(["Tabla", "SHA-256 en Stratio", "SHA-256 en Fabric", "Resultado"],
                    [[o["clave"], o["hash_s"], o["hash_f"], "idéntica" if o["hash_igual"] else "distinta"] for _, o in hs],
                    [2500, 3200, 3200, 900], monos={0, 1, 2}))

    # 6 · controles
    D.add(h1("6. Controles de calidad"))
    D.add(parrafo(run("Ingesta se aprueba con VG (esquema y metadata), ID (integridad) y CP (puntos de control); analítica con VG "
                      "e ID, y sus filas son informativas. Un control en falla a los dos lados es heredado de Stratio y no cuenta "
                      "como regresión.", 20)))
    if any(o.get("vg_txt") for g in ("ingesta", "analitica") for o in OB[g]):
        D.add(parrafo(run("En las tablas de los reportes v4 se indica cuántos de los controles que deciden cumplen (los "
                          "justificados por QA se nombran); en las demás, el porcentaje de controles que cumplen.", 20)))
    con_cp05 = any(o.get("cp05") for g in ("ingesta", "analitica") for o in OB[g])
    if con_cp05:
        D.add(parrafo(run("CP-05 · la corrida escribió lo que se midió. ", 20, AZUL, b=True) + run(
            "Se exige siempre, en los dos grupos: prueba que la tabla medida es la que escribió la corrida verificada y no una "
            "escritura anterior. Cómo se prueba depende del destino: en una tabla Delta, un commit del _delta_log dentro de la "
            "corrida; en archivos de OneLake, archivos escritos dentro de la corrida; en una tabla de Postgres (sin _delta_log), "
            "la copia exitosa de la corrida con sus filas copiadas; en el SFTP, la fecha de modificación del archivo. Solo «no "
            "aplica» cuando no hay una corrida de Fabric que citar (orquestadores, que no escriben tablas): en ese caso se dice "
            "por qué y no bloquea la aprobación.", 20)))
    k = 0
    for g, t in GRUPOS[:2]:
        if not OB[g]:
            continue
        k += 1
        D.add(h2(f"6.{k}  {t}"))
        cab = ["Tabla", "VG", "ID"] + (["CP"] if g == "ingesta" else []) + (["CP-05 · corrida"] if con_cp05 else []) + ["Regresiones"]
        filas = []
        for o in OB[g]:
            sin = o.get("nota_control") or "cotejo por partes"
            p6 = lambda c: o.get(c + "_txt") or ((o[c] if isinstance(o[c], str) else f"{o[c]:.2f}%".replace(".", ","))
                                                 if o.get(c) is not None else sin)
            fila = [o["clave"], p6("vg"), p6("id")]
            if g == "ingesta":
                fila.append(p6("cp"))
            if con_cp05:
                fila.append(cp05_txt(o.get("cp05")))
            fila.append(", ".join(o.get("regresiones") or []) or "ninguna")
            filas.append(fila)
        anchos6 = ([3000, 1100, 1100] + ([1100] if g == "ingesta" else []) + [2400, 1100]) if con_cp05 else \
                  ([4200, 1300, 1300] + ([1300] if g == "ingesta" else []) + [1700])
        D.add(tabla(cab, filas, anchos6, monos={0}))
        cnt = {}
        for o in OB[g]:
            for fam, ct in (o.get("controles") or {}).items():
                c_ = cnt.setdefault(fam, {})
                c_["cumple"] = c_.get("cumple", 0) + ct.get("solo_ok", 0)
                c_["justificado"] = c_.get("justificado", 0) + len(ct.get("justificados") or [])
                c_["no evaluado"] = c_.get("no evaluado", 0) + len(ct.get("otros") or [])
        if cnt:
            D.grafica(GA.controles({f"{fam}": cnt[fam] for fam in ("VG", "ID", "CP") if fam in cnt and (g == "ingesta" or fam != "CP")},
                                   f"{D.dir}/g_controles_{g}.png", f"Controles que deciden · {t.lower()}",
                                   f"suma sobre las {len(OB[g])} tablas: cada tramo es un control evaluado en una tabla"),
                      f"Controles que deciden en {t.lower()}, por familia: cuántos cumplen, cuántos se justificaron con causa medida "
                      "y cuántos quedaron sin evaluar.")

    # 7 · diferencias
    D.add(h1("7. Diferencias y su justificación"))
    D.add(parrafo(run("Por cada flujo con diferencias: qué difiere, un ejemplo sacado de la comparación de las dos tablas y por "
                      "qué se aprueba.", 20)))
    k = 0
    SEC7 = {}
    for f in L["flujos"]:
        # reportes v4 (formato 2): una tabla con diferencias registradas en su cotejo entra aunque tenga las mismas filas
        dif = [o for o in f["objetos"] if o["filas_s"] is not None
               and (o["filas_s"] != o["filas_f"] or o.get("diferencias") or (L.get("detalle_aunque_igual") and o.get("detalle_diferencias")))]
        if not dif:
            continue
        k += 1
        SEC7[f["fabric"]] = f"7.{k}"
        D.add(h2(f"7.{k}  {f['fabric']}"))
        filas = []
        if L.get("sec7_compacta", True) and all(o.get("detalle_diferencias") for o in dif):
            # compacto (por defecto desde 2026-10-22): una fila por causa —las diferencias que comparten la causa con la que
            # se aprobaron van juntas—, la cifra en una frase, un ejemplo real Stratio | Fabric y la causa final resumida
            D.add(_tabla_dif_compacta(filas_por_tabla(dif) if L.get("sec7_modo", "tabla") == "tabla" else filas_compactas(dif)))
            if f.get("justificacion"):
                D.add(parrafo(run("Por qué se aprueba: ", 18, AZUL, b=True) + run(resumir(f["justificacion"].replace("`", ""), 300), 18)))
            continue
        for o in dif:
            if o.get("detalle_diferencias"):
                # reportes v4: una fila por diferencia del cotejo, cada una con su cifra, su ejemplo y su justificación
                filas.append([o["clave"], f"filas {n(o['filas_s'])} → {n(o['filas_f'])} ({pct(o['pct'])})",
                              ("1 diferencia en el cotejo, en la fila siguiente" if L.get("concordancia") and len(o["detalle_diferencias"]) == 1
                               else f"{len(o['detalle_diferencias'])} diferencias en el cotejo, una por fila a continuación"),
                              o.get("justificacion") or "Diferencias con causa medida."])
                for x in o["detalle_diferencias"]:
                    filas.append([f"{o['clave']}\n{x['id']} · {x['control']}", x["diferencia"], x["ejemplo"], x["justificacion"]])
                continue
            d0 = o.get("diferencia_txt") or f"filas {n(o['filas_s'])} → {n(o['filas_f'])} ({pct(o['pct'])})"
            ej = o.get("ejemplo_txt") or "; ".join(f"{x['columna']}: {x['ejemplo']}" for x in (o.get("diferencias") or [])[:2]) or "mismo perfil en todas las columnas"
            js = o.get("acotacion") or o.get("justificacion") or o.get("justificacion_tabla") or "Diferencia dentro del criterio del grupo."
            # (lote 7 v2.2) hasta la v2.1 la justificación se cortaba a 327 caracteres + «…» (56 de 69 filas del lote 7);
            # con L["justificacion_completa"] sale entera
            filas.append([o["clave"], d0, ej, js if (L.get("justificacion_completa") or len(js) <= 330) else js[:327] + "…"])
        D.add(tabla(["Tabla", "Diferencia", "Ejemplo de la comparación", "Justificación"], filas, [2100, 1800, 3000, 2900], monos={0}))
        if f.get("justificacion"):
            # el motivo por el que se aprueba el flujo, una sola vez, debajo de su tabla
            D.add(parrafo(run("Por qué se aprueba: ", 18, AZUL, b=True) + run(f["justificacion"].replace("`", ""), 18)))
    for tb in L.get("seccion7_extra") or []:      # (lote 12 v1.0) subsecciones propias al final del punto 7 (salvedades)
        k += 1
        D.add(h2(f"7.{k}  {tb['titulo']}"))
        for t in tb.get("antes") or []:
            D.add(parrafo(run(t, 20)))
        D.add(tabla(tb["cab"], [list(r) for r in tb["filas"]], tb["anchos"], negritas={i: {0} for i in range(len(tb["filas"]))}))
        for t in tb.get("despues") or []:
            D.add(parrafo(run(t, 20)))

    # 8 · pendientes (solo si el lote los trae)
    if L.get("pendientes"):
        PN = L["pendientes"]
        D.add(h1("8. Pendientes"))
        D.add(parrafo(run(PN["intro"], 20)))
        for titulo, filas in PN["bloques"]:
            D.add(h2(titulo))
            D.add(tabla(["N.º", "Flujo · tabla", "Qué queda pendiente", "Estado en los datos", "Siguiente paso"],
                        [list(r) for r in filas], [500, 2100, 3700, 1700, 1800], negritas={i: {0} for i in range(len(filas))}))

    # 8 · atención de observaciones del cliente (solo si el lote las trae)
    if L.get("observaciones"):
        OB8 = L["observaciones"]
        D.add(h1(f"8. {OB8['titulo']}"))
        for t in OB8.get("antes") or []:
            D.add(parrafo(run(t, 20)))
        for tb in OB8.get("tablas") or []:
            if tb.get("titulo"):
                D.add(h2(tb["titulo"]))
            D.add(tabla(tb["cab"], [list(r) for r in tb["filas"]], tb["anchos"], negritas={i: {0} for i in range(len(tb["filas"]))}))
        for t in OB8.get("despues") or []:
            D.add(parrafo(run(t, 20)))

    # declaracion y firmas
    # (2026-10-22, pedido de QA) la aprobación de Comfandi llega por correo electrónico: el acta ya no lleva firmas
    D.add(h1(f"{P_DECL}. Declaración y aprobación"))
    D.add(parrafo(run(
        "El equipo de pruebas VMQA declara que los flujos listados fueron ejecutados y cotejados contra Stratio con el criterio "
        "de su grupo, y que cada diferencia lleva su causa medida o su verificación. Asimismo el equipo de ingesta CDS y "
        "analítica DIA realizó su validación y aprobación correspondiente en el proceso de desarrollo.", 20)))
    D.add(parrafo(run(
        "Para la aprobación de la actual acta, el equipo de COMFANDI debe realizar las aprobaciones correspondientes de los "
        "anexos, las justificaciones y enviar su aprobado mediante correo electrónico.", 20)))
    if L.get("declaracion_extra"):
        D.add(parrafo(run(L["declaracion_extra"], 20)))
    if L.get("con_firmas"):                 # solo para regenerar un acta antigua que ya se firmó así
        D.add(firmas(bloques_firma))

    # anexo de hallazgos atendidos (lote 10 v1.2): uno por hallazgo del revisor, con su evidencia
    SEC11 = {g: f"{P_ANEXO}.{i + 1}" for i, g in enumerate(g for g, _ in GRUPOS
                                                           if F[g] and any(f.get("cotejo_flujo") or f.get("objetos") for f in F[g]))}
    if P_HALL:
        AH = L["anexo_hallazgos"]
        GF = {f["fabric"]: f["grupo"] for f in L["flujos"]}
        nom_h = {"metrica_stratio": "Métrica Stratio", "metrica_fabric": "Métrica Fabric", "cotejo_stratio_fabric": "Cotejo Stratio ↔ Fabric",
                 "cotejo_valor": "Cotejo de valor", "cotejo_fila": "Cotejo fila a fila", "cotejo_flujo": "Cotejo del flujo"}
        D.add(salto())
        D.add(h1(f"{P_HALL}. {AH['titulo']}"))
        for t in AH.get("intro") or []:
            D.add(parrafo(run(t, 20)))
        for x in AH["items"]:
            D.add(h2(f"{P_HALL}.{x['num']}  Hallazgo #{x['num']} · {x['flujo']} · {', '.join(x['tablas'])}"))
            g = GF.get(x["flujo"])
            if g:
                tg = "5.1" if g == "ingesta" else "5.2"
                donde = (f"Punto {SEC3[g]} (flujo), {tg} y 6.{tg[-1]} (tabla)"
                         + (f", {SEC7[x['flujo']]} (diferencias y su justificación)" if x["flujo"] in SEC7 else "")
                         + f", 8.1 (resumen) y {SEC11[g]} (enlaces)")
            else:
                donde = f"Punto {SEC3.get('retirados', '3')} (flujo retirado del lote) y 8 (motivo de la devolución)"
            if x.get("donde"):                  # (lote 9 v2.2) el dato fija dónde está la evidencia: flujo fuera del lote sin punto 3
                donde = x["donde"]
            if x.get("donde_extra"):
                donde += ". " + x["donde_extra"]
            filas = [["Lo que reportó el revisor", x["revisor"]], ["Lo que se encontró", x["encontrado"]],
                     ["Justificación medida", x["justificacion"]], ["Estado final", x["estado"]], ["Dónde está la evidencia en el acta", donde]]
            if x.get("campos"):                 # (lote 9 v2.2) filas propias: revisor, medido, causa, decisión, justificación…
                filas = [list(c) for c in x["campos"]] + [["Dónde está la evidencia en el acta", donde]]
            D.add(tabla(["Campo", "Contenido"], filas, [2300, 7500], negritas={i: {0} for i in range(len(filas))}))
            ln = [(a, nom_h[b], os.path.basename(r), r) for a, b, r in x.get("enlaces") or []]
            if ln:
                D.add(tabla_links(D, ["Flujo · tabla", "Documento", "Archivo en el lakehouse"], ln, [2900, 1700, 5200]))
            if x.get("locales"):
                D.add(tabla(["Evidencia local (no publicada)", "Ruta"], [list(r) for r in x["locales"]], [2900, 6900], monos={1}))

    # 9 · anexo de evidencia
    D.add(salto())
    D.add(h1(f"{P_ANEXO}. Anexo de evidencia"))
    D.add(parrafo(run(L.get("nota_anexo") or
                      "Todos los enlaces abren el archivo en el lakehouse lh_transversal del workspace datalake-qa. Cada uno se "
                      f"comprobó contra OneLake el {L['verificado_utc'][:16].replace('T', ' ')} UTC.", 20)))
    solo = L.get("anexo_solo_enlaces_acta")      # el anexo lleva solo los enlaces del registro del lote
    nom = {"metrica_stratio": "Métrica Stratio", "metrica_fabric": "Métrica Fabric", "cotejo_stratio_fabric": "Cotejo Stratio ↔ Fabric",
           "cotejo_valor": "Cotejo de valor", "cotejo_fila": "Cotejo fila a fila"}
    publicado = []
    k = 0
    # los orquestadores no tienen tablas, pero si tienen cotejo del flujo:
    # dejarlos fuera del anexo era omitir su unica evidencia enlazable
    for g, t in GRUPOS:
        if not F[g] or not any(f.get("cotejo_flujo") or f.get("objetos") for f in F[g]):
            continue
        k += 1
        D.add(h2(f"{P_ANEXO}.{k}  {t}"))
        filas = []
        for f in F[g]:
            if f.get("cotejo_flujo"):
                filas.append([f["fabric"], "Cotejo del flujo", os.path.basename(f["cotejo_flujo"]), f["cotejo_flujo"]])
                publicado.append(f["cotejo_flujo"])
            for extra in ([] if solo else f.get("cotejos_flujo_extra") or []):     # otros reportes del flujo (p. ej. del validador)
                col1 = f["fabric"]
                if isinstance(extra, (list, tuple)) and len(extra) == 3:        # (flujo · tabla, documento, ruta)
                    col1, lab, extra = extra
                else:
                    lab, extra = (extra if isinstance(extra, (list, tuple)) else ("Reporte del validador", extra))
                filas.append([col1, lab, os.path.basename(extra), extra])
                publicado.append(extra)
            for o in f["objetos"]:
                for c, r in (o["enlaces_acta"] if solo else o["enlaces"]).items():
                    if r:
                        filas.append([o["clave"], nom[c], os.path.basename(r), r])
                        publicado.append(r)
        D.add(tabla_links(D, ["Flujo · tabla", "Documento", "Archivo en el lakehouse"], filas, [2900, 1700, 5200]))
    if L.get("documentos"):
        D.add(h2(f"{P_ANEXO}.{k + 1}  Documentos del lote"))
        D.add(tabla_links(D, ["Lote", "Documento", "Archivo en el lakehouse"],
                          [[f"Lote {lote}", "Registro del lote", os.path.basename(r), r] for r in L["documentos"]], [2900, 1700, 5200]))
        publicado += L["documentos"]
        k += 1
    if L.get("evidencia_local"):
        D.add(h2(f"{P_ANEXO}.{k + 1}  Evidencia local (no publicada en el lakehouse)"))
        D.add(parrafo(run(L.get("nota_evidencia_local") or "Archivos de medición que quedan en el equipo de QA y no se publicaron.", 20)))
        D.add(tabla(["Flujo · tabla", "Documento", "Ruta local"], [list(r) for r in L["evidencia_local"]], [2500, 2600, 4700], monos={2}))
        k += 1
    for tb in L.get("anexo_extra") or []:          # (lote 7 v2.2) tablas propias al final del anexo (p. ej. registro Delta)
        D.add(h2(f"{P_ANEXO}.{k + 1}  {tb['titulo']}"))
        for t in tb.get("antes") or []:
            D.add(parrafo(run(t, 20)))
        D.add(tabla(tb["cab"], [list(r) for r in tb["filas"]], tb["anchos"], monos=set(tb.get("monos") or [])))
        k += 1

    sal = f"{REP}/Acta_Entrega_Flujos_Lote{lote}_{fecha}_v{ver}.docx"
    guardar("".join(D.d), sal, titulo=f"Acta de entrega de flujos · Lote {lote}",
            cabecera=f"Acta de entrega de flujos · Lote {lote}", imagenes=D.img, enlaces=D.rels)
    json.dump({"lote": lote, "publicado": publicado}, open(os.path.splitext(sal)[0] + ".evidencia.json", "w"), indent=1)
    return sal, len(publicado), D.pie


def comprobar(L):
    """Lo que impide emitir el acta y hay que PREGUNTAR o medir antes (no se rellena ni se supone)."""
    CAPAS.aplicar_decisiones(L)
    out = []
    for q in CAPAS.preguntas(L):
        out.append(("capa", f"{q['flujo']}" + (f" · {q['tabla']}" if q["tabla"] else " (flujo)") +
                    f": capa «{q['capa_actual'] or 'sin capa'}» · {q['motivo']} → preguntar Bronze, Silver o Gold "
                    "(con «· Postgres» o «· SFTP» si es copia) y guardarlo en capas_decididas"))
    for f in L["flujos"]:
        dm = f["ejecucion"].get("dependencias_medidas")
        if dm is not None and dm.get("estado") != "MEDIDO" and f["grupo"] != "orquestadores":
            out.append(("dependencias", f"{f['fabric']}: {dm.get('resumen')}"))
        for o in f["objetos"]:
            for x in o.get("detalle_diferencias") or []:
                real = x.get("ejemplo_real")
                if real is False or (real is None and not (" · Stratio: " in str(x.get("ejemplo")) and " · Fabric: " in str(x.get("ejemplo")))):
                    out.append(("ejemplo", f"{f['fabric']} · {o['clave']} · {x['id']} {x['control']}: sin ejemplo real Stratio | Fabric "
                                           "→ tomarlo de la comparación (`python -m pc comparar --clave …`) y registrarlo en la diferencia"))
    return out


def main():
    lote = int(sys.argv[1])
    L = json.load(open(f"{REP}/datos_acta_lote{lote}.json"))
    if L.get("enlaces_no_resueltos"):
        print("ENLACES NO RESUELTOS: no se emite un acta con enlaces rotos")
        for x in L["enlaces_no_resueltos"]:
            print("  ", x)
        sys.exit(1)
    pend = comprobar(L)
    if pend:
        print(f"ACTA NO EMITIDA · {len(pend)} punto(s) para preguntar o medir antes (no se suponen):")
        for tipo, t in pend:
            print(f"  [{tipo}] {t}")
        sys.exit(2)
    sal, nl, ng = acta(L)
    print(sal, "·", nl, "enlaces ·", ng, "gráficas")


if __name__ == "__main__":
    main()
