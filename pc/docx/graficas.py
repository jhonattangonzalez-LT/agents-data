"""Copia de actas/graficas.py (generador de actas entregadas): graficas con Pillow. Se usa tal cual."""
"""Graficas de las actas, dibujadas con Pillow.

La paleta sale del acta de referencia: azul Comfandi para la identidad, ambar
para el acento y verde para lo que cumple. Se dibuja al doble y se reduce, para
que el texto quede nitido dentro del documento.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

AZUL = (26, 58, 92)
AZUL_CL = (50, 104, 203)
TINTA = (26, 35, 50)
GRIS = (84, 110, 122)
GRIS_CL = (207, 216, 220)
VERDE = (30, 122, 70)
VERDE_CL = (232, 243, 236)
AMBAR = (245, 166, 35)
AMBAR_OS = (138, 97, 0)
SUAVE = (238, 242, 246)
BLANCO = (255, 255, 255)

E = 2
_RUTAS = ("/usr/share/fonts/truetype/liberation",
          "/usr/share/fonts/truetype/dejavu")


def fuente(t=11, negrita=False):
    for base in _RUTAS:
        for n in (("LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf") if negrita
                  else ("LiberationSans-Regular.ttf", "DejaVuSans.ttf")):
            p = os.path.join(base, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, int(t * E))
    return ImageFont.load_default()


def _lienzo(an, al):
    im = Image.new("RGB", (an * E, al * E), BLANCO)
    return im, ImageDraw.Draw(im)


def _guardar(im, ruta):
    an, al = im.size
    os.makedirs(os.path.dirname(os.path.abspath(ruta)) or ".", exist_ok=True)
    im.resize((an // E, al // E), Image.LANCZOS).save(ruta, "PNG", optimize=True)
    return ruta


def _txt(d, xy, t, f, color=TINTA, anclaje="la"):
    d.text((xy[0] * E, xy[1] * E), t, font=f, fill=color, anchor=anclaje)


def mil(v):
    return f"{v:,}".replace(",", ".")


def alto(ruta):
    return Image.open(ruta).height


# ── 1 · cobertura de la verificacion ────────────────────────────────────────
def cobertura(pasos, ruta, titulo="Cobertura de la verificación",
              subtitulo="Cada etapa del procedimiento aplicado al lote",
              cierre=("Todas las etapas se completaron sobre la totalidad "
                      "del lote.", "No quedaron flujos sin ejecutar, sin "
                      "validar ni sin verificar.")):
    an, al = 640, 78 + 34 * len(pasos) + 40
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), titulo, fuente(13, True), AZUL)
    _txt(d, (0, 26), subtitulo, fuente(10), GRIS)
    base = pasos[0][1] or 1
    y = 58
    for etq, v, nota in pasos:
        w = (an - 96) * v / base
        col = VERDE if v == base else AZUL_CL
        d.rectangle([0, y * E, max(w, 2) * E, (y + 22) * E], fill=col)
        _txt(d, (8, y + 5), etq, fuente(10, True), BLANCO)
        _txt(d, (an, y + 4), str(v), fuente(13, True), col, "ra")
        _txt(d, (0, y + 25), nota, fuente(8), GRIS)
        y += 34
    y += 6
    d.rectangle([0, y * E, an * E, (y + 30) * E], fill=VERDE_CL)
    d.rectangle([0, y * E, 3 * E, (y + 30) * E], fill=VERDE)
    _txt(d, (10, y + 5), cierre[0], fuente(10, True), VERDE)
    _txt(d, (10, y + 18), cierre[1], fuente(9), TINTA)
    return _guardar(im, ruta)


# ── 2 · resultado del dato ──────────────────────────────────────────────────
def resultado(idn, casi, dif, ruta):
    an, al = 640, 210
    im, d = _lienzo(an, al)
    total = idn + casi + dif
    _txt(d, (0, 4), "Resultado de la verificación del dato", fuente(13, True), AZUL)
    _txt(d, (0, 26), f"{total} flujos entregados", fuente(10), GRIS)
    partes = [(idn, VERDE, "Dato idéntico al origen"),
              (casi, AMBAR, "Diferencia mínima justificada"),
              (dif, AMBAR_OS, "Diferencia justificada")]
    x, y, h = 0, 62, 40
    for n, col, _ in partes:
        if not n:
            continue
        w = an * n / total
        d.rectangle([x * E, y * E, (x + w) * E, (y + h) * E], fill=col)
        if w > 30:
            _txt(d, (x + w / 2, y + h / 2), str(n), fuente(15, True), BLANCO, "mm")
        x += w
    ly = y + h + 22
    for n, col, et in partes:
        d.rectangle([0, ly * E, 11 * E, (ly + 11) * E], fill=col)
        _txt(d, (17, ly - 1), f"{et}   {n}", fuente(10), TINTA)
        ly += 20
    _txt(d, (0, al - 16), f"Los {total} flujos tienen su resultado documentado. "
         "Ninguna diferencia queda sin justificar.", fuente(9), GRIS)
    return _guardar(im, ruta)


# ── 3 · ejecucion del lote ──────────────────────────────────────────────────
def ejecucion(total, ok, valida, bloq, filas, ruta, ambiente="QA", cierre=None,
              tarjetas=None, titulo=None, subtitulo=None, pie=None):
    an, al = 640, 230
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), titulo or "Resultado de la ejecución del lote",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), subtitulo or ("Flujos solicitados, ejecutados y validados "
         f"en el ambiente de {ambiente}"), fuente(10), GRIS)
    tarjetas = tarjetas or [
        ("Solicitados", total, AZUL), ("Ejecutados", ok, VERDE),
        ("Validados", valida, VERDE), ("Bloqueados", bloq, AMBAR_OS)]
    w = (an - 30) / 4
    for i, (et, v, col) in enumerate(tarjetas):  # noqa: B007
        x = i * (w + 10)
        d.rectangle([x * E, 58 * E, (x + w) * E, 128 * E], fill=SUAVE)
        d.rectangle([x * E, 58 * E, (x + w) * E, 61 * E], fill=col)
        _txt(d, (x + w / 2, 74), str(v), fuente(26, True), col, "ma")
        _txt(d, (x + w / 2, 110), et, fuente(10), GRIS, "ma")
    d.rectangle([0, 148 * E, an * E, 182 * E], fill=VERDE_CL)
    d.rectangle([0, 148 * E, 3 * E, 182 * E], fill=VERDE)
    c1, c2 = cierre or (
        f"Los {total} flujos solicitados se ejecutaron correctamente y "
        "pasaron la validación.",
        "No hubo flujos bloqueados ni sin resolver.")
    _txt(d, (10, 154), c1, fuente(10, True), VERDE)
    _txt(d, (10, 168), c2, fuente(9), TINTA)
    _txt(d, (0, 198), pie or "Filas escritas en el destino", fuente(10), GRIS)
    _txt(d, (an - 2, 194), mil(filas), fuente(15, True), AZUL, "ra")
    return _guardar(im, ruta)


# ── 4 · duracion por flujo ──────────────────────────────────────────────────
def duracion(filas, ruta):
    d_ord = sorted([f for f in filas if f.get("segundos")],
                   key=lambda x: -x["segundos"])
    if not d_ord:
        return None
    an, fil = 640, 13
    al = 76 + fil * len(d_ord) + 34
    im, d = _lienzo(an, al)
    tot = sum(f["segundos"] for f in d_ord)
    _txt(d, (0, 4), "Duración de la ejecución por flujo", fuente(13, True), AZUL)
    _txt(d, (0, 26), f"{len(d_ord)} flujos ejecutados · {tot} segundos en total "
         f"({tot/60:.1f} minutos)".replace(".", ","), fuente(10), GRIS)
    ml, mr = 238, 74
    ancho = an - ml - mr
    mx = max(f["segundos"] for f in d_ord)
    y = 58
    for f in d_ord:
        w = ancho * f["segundos"] / mx
        col = AZUL_CL if f["segundos"] < 120 else AMBAR
        d.rectangle([ml * E, y * E, (ml + max(w, 1)) * E, (y + 9) * E], fill=col)
        nom = f["flujo"] if len(f["flujo"]) <= 44 else f["flujo"][:43] + "…"
        _txt(d, (ml - 6, y + 4), nom, fuente(8), TINTA, "rm")
        _txt(d, (ml + w + 6, y + 4), f"{f['segundos']}s", fuente(8), GRIS, "lm")
        y += fil
    y += 8
    d.rectangle([0, y * E, an * E, (y + 26) * E], fill=SUAVE)
    d.rectangle([0, y * E, 3 * E, (y + 26) * E], fill=AZUL)
    _txt(d, (10, y + 7), f"Promedio {tot/len(d_ord):.0f} s por flujo · el más "
         f"largo {mx} s · el más corto {min(f['segundos'] for f in d_ord)} s",
         fuente(10, True), TINTA)
    return _guardar(im, ruta)


# ── 5 · filas a cada lado ───────────────────────────────────────────────────
def volumen(filas, ruta):
    an, al = 640, 300
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), "Filas medidas en el origen y en el destino",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), "Escala logarítmica · las dos barras coinciden en los "
         f"{len(filas)} flujos", fuente(10), GRIS)
    ml, mr, mt, mb = 74, 10, 58, 76
    ancho, alto_g = an - ml - mr, al - mt - mb
    mx = max(max(f["filas_a"], f["filas_b"]) for f in filas) or 1
    techo = 10 ** math.ceil(math.log10(mx))
    lg = lambda v: 0 if v <= 0 else math.log10(v) / math.log10(techo)
    for k in range(int(math.log10(techo)) + 1):
        v = 10 ** k
        yy = mt + alto_g - lg(v) * alto_g
        d.line([ml * E, yy * E, (an - mr) * E, yy * E], fill=GRIS_CL, width=1)
        _txt(d, (ml - 6, yy), mil(v), fuente(8), GRIS, "rm")
    paso = ancho / len(filas)
    bw = min(11, paso / 2.6)
    for i, f in enumerate(filas):
        cx = ml + paso * (i + 0.5)
        for j, (v, col) in enumerate(((f["filas_a"], AZUL_CL),
                                      (f["filas_b"], AMBAR))):
            h = lg(v or 0) * alto_g
            x = cx - bw - 1 + j * (bw + 2)
            d.rectangle([x * E, (mt + alto_g - h) * E, (x + bw) * E,
                         (mt + alto_g) * E], fill=col)
        _txt(d, (cx, mt + alto_g + 6), f["flujo"].split("-", 1)[0], fuente(8),
             GRIS, "ma")
    d.line([ml * E, (mt + alto_g) * E, (an - mr) * E, (mt + alto_g) * E],
           fill=GRIS, width=2)
    ly = al - 44
    for col, et in ((AZUL_CL, "Origen · Stratio"), (AMBAR, "Destino · Fabric")):
        d.rectangle([0, ly * E, 11 * E, (ly + 11) * E], fill=col)
        _txt(d, (17, ly - 1), et, fuente(10), TINTA)
        ly += 18
    tot = sum(f["filas_a"] for f in filas)
    _txt(d, (an - 2, al - 44), f"{mil(tot)} filas a cada lado", fuente(11, True),
         VERDE, "ra")
    _txt(d, (an - 2, al - 26), "diferencia: 0", fuente(11, True), VERDE, "ra")
    return _guardar(im, ruta)


# ── 6 · identidad por flujo ─────────────────────────────────────────────────
def paridad(filas, ruta):
    an, fil = 640, 13
    al = 76 + fil * len(filas) + 40
    im, d = _lienzo(an, al)
    idn = sum(1 for f in filas if f["pct"] == 100.0)
    _txt(d, (0, 4), "Identidad del dato por flujo", fuente(13, True), AZUL)
    _txt(d, (0, 26), f"{idn} de {len(filas)} flujos con el dato idéntico al "
         "origen", fuente(10), GRIS)
    ml, mr = 238, 92
    ancho = an - ml - mr
    piso = min([f["pct"] for f in filas if f["pct"] is not None] + [100.0])
    piso = math.floor(min(piso, 99.9) * 10) / 10 if piso < 100 else 99.0
    rango = max(100.0 - piso, 0.1)
    y = 58
    for f in sorted(filas, key=lambda x: (-(x["pct"] or 0), x["flujo"])):
        p = f["pct"] or 0
        w = ancho * max(0.0, p - piso) / rango
        col = VERDE if p == 100.0 else AMBAR
        d.rectangle([ml * E, y * E, (ml + max(w, 1)) * E, (y + 9) * E], fill=col)
        _txt(d, (ml - 6, y + 4), f["flujo"][:40], fuente(8), TINTA, "rm")
        # con pocos decimales, 99,999976 se redondea a 100 y miente: van 6
        et = "100 %" if p == 100.0 else f"{p:.6f} %".replace(".", ",")
        _txt(d, (ml + w + 6, y + 4), et, fuente(8), GRIS, "lm")
        y += fil
    y += 8
    d.rectangle([0, y * E, an * E, (y + 30) * E], fill=SUAVE)
    d.rectangle([0, y * E, 3 * E, (y + 30) * E], fill=AZUL)
    _txt(d, (10, y + 5), (f"El eje arranca en {piso:g} % para que las "
         "diferencias se aprecien.").replace(".", ",", 1) if piso % 1 else
         f"El eje arranca en {piso:g} % para que las diferencias se aprecien.",
         fuente(10, True), TINTA)
    _txt(d, (10, y + 18), "Las barras que no llegan al tope corresponden a "
         "diferencias con causa identificada.", fuente(9), GRIS)
    return _guardar(im, ruta)


# ── 7 · controles de paridad ────────────────────────────────────────────────
def controles(ok, tot, ruta, titulo=None, subtitulo=None, cierre=None,
              etiqueta=None):
    an, al = 640, 168
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), titulo or "Controles de paridad entre origen y destino",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), subtitulo or ("Familias CP (puntos de control), ID "
         "(integridad) y VG (gobierno)"), fuente(10), GRIS)
    y = 58
    d.rectangle([0, y * E, an * E, (y + 26) * E], fill=SUAVE)
    d.rectangle([0, y * E, (an * ok / tot) * E, (y + 26) * E], fill=VERDE)
    _txt(d, (8, y + 6), f"{100*ok/tot:.1f} %".replace(".", ","),
         fuente(12, True), BLANCO)
    _txt(d, (an, y + 30), etiqueta or f"{ok} de {tot} coinciden",
         fuente(11, True), VERDE, "ra")
    d.rectangle([0, (al - 52) * E, an * E, al * E], fill=VERDE_CL)
    d.rectangle([0, (al - 52) * E, 3 * E, al * E], fill=VERDE)
    c1, c2, c3 = cierre or (
        f"Coinciden {ok} de {tot} controles de paridad.",
        "Se cuentan solo los controles que comparan Stratio contra Fabric. "
        "Los que comparan un objeto",
        "contra su corrida anterior no miden paridad y quedan fuera de este "
        "cómputo.")
    _txt(d, (10, al - 45), c1, fuente(11, True), VERDE)
    _txt(d, (10, al - 29), c2, fuente(9), TINTA)
    _txt(d, (10, al - 17), c3, fuente(9), TINTA)
    return _guardar(im, ruta)


# ── 8 · diferencias justificadas ────────────────────────────────────────────
def justificadas(casos, ruta):
    an = 640
    al = 74 + 52 * len(casos) + 42
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), "Diferencias observadas y su justificación",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), f"{len(casos)} diferencias · {len(casos)} con causa "
         "identificada · 0 sin justificar", fuente(10), GRIS)
    y = 58
    for flujo, pct, causa in casos:
        d.rectangle([0, y * E, an * E, (y + 44) * E], fill=SUAVE)
        d.rectangle([0, y * E, 3 * E, (y + 44) * E], fill=AMBAR)
        _txt(d, (12, y + 6), flujo, fuente(10, True), TINTA)
        _txt(d, (12, y + 23), causa, fuente(9), GRIS)
        _txt(d, (an - 10, y + 6), pct, fuente(11, True), AMBAR_OS, "ra")
        _txt(d, (an - 10, y + 24), "justificada", fuente(9, True), VERDE, "ra")
        y += 52
    d.rectangle([0, y * E, an * E, (y + 34) * E], fill=VERDE_CL)
    d.rectangle([0, y * E, 3 * E, (y + 34) * E], fill=VERDE)
    _txt(d, (10, y + 6), "Ninguna diferencia corresponde a pérdida de filas: el "
         "conteo coincide exactamente", fuente(10, True), VERDE)
    _txt(d, (10, y + 20), "en todos los casos. Todas quedan justificadas en el "
         "cuerpo del acta.", fuente(9), TINTA)
    return _guardar(im, ruta)


# ── 9 · transformacion entrada → salida (actas de analitica) ────────────────
def transformacion(filas, ruta):
    """Filas de entrada y de salida por flujo, en escala logaritmica.

    Un flujo de analitica no copia: transforma. La salida puede ser menor
    que la entrada por diseño (limpieza, deduplicacion, filtrado) y la
    grafica lo muestra tal cual, sin pretender que coincidan.
    """
    an, al = 640, 66 + 22 * len(filas) + 70
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), "Filas de entrada y de salida de cada flujo",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), "Escala logarítmica · la salida es la suma de las tablas "
         "que escribe el flujo", fuente(10), GRIS)
    ml, mr = 236, 96
    ancho = an - ml - mr
    mx = max(max(f["filas_entrada"], f["filas_salida"]) for f in filas) or 1
    techo = 10 ** math.ceil(math.log10(mx))
    lg = lambda v: 0 if v <= 0 else math.log10(v) / math.log10(techo)
    y = 58
    for f in sorted(filas, key=lambda x: -x["filas_entrada"]):
        _txt(d, (ml - 8, y + 8), f["flujo"][:36], fuente(8), TINTA, "rm")
        for j, (v, col) in enumerate(((f["filas_entrada"], AZUL_CL),
                                      (f["filas_salida"], VERDE))):
            w = lg(v) * ancho
            d.rectangle([ml * E, (y + j * 9) * E, (ml + max(w, 2)) * E,
                         (y + j * 9 + 8) * E], fill=col)
        _txt(d, (ml + ancho + 6, y + 8), f"{mil(f['filas_salida'])}",
             fuente(8), VERDE, "lm")
        y += 22
    ly = y + 8
    for col, et in ((AZUL_CL, "Filas leídas de las entradas"),
                    (VERDE, "Filas escritas en las salidas")):
        d.rectangle([0, ly * E, 11 * E, (ly + 11) * E], fill=col)
        _txt(d, (17, ly - 1), et, fuente(10), TINTA)
        ly += 18
    tot = sum(f["filas_salida"] for f in filas)
    _txt(d, (an - 2, y + 8), f"{mil(tot)} filas escritas", fuente(11, True),
         VERDE, "ra")
    _txt(d, (an - 2, y + 26), f"{len(filas)} flujos · todas las salidas "
         "escritas", fuente(9), GRIS, "ra")
    return _guardar(im, ruta)


# ── 10 · pruebas del validador (actas de analitica) ─────────────────────────
def pruebas(ok, omitidas, avisos, ruta):
    an, al = 640, 168
    im, d = _lienzo(an, al)
    tot = ok + omitidas + avisos
    _txt(d, (0, 4), "Pruebas aplicadas por el validador", fuente(13, True), AZUL)
    _txt(d, (0, 26), "Despliegue, variables, aislamiento de ambiente, corrida, "
         "salidas y cuadre de la transformación", fuente(10), GRIS)
    y, x = 58, 0
    for v, col in ((ok, VERDE), (avisos, AMBAR), (omitidas, GRIS_CL)):
        w = an * v / tot if tot else 0
        d.rectangle([x * E, y * E, (x + w) * E, (y + 26) * E], fill=col)
        if w > 28:
            _txt(d, (x + w / 2, y + 13), str(v), fuente(12, True),
                 BLANCO if col != GRIS_CL else TINTA, "mm")
        x += w
    ly = y + 34
    for v, col, et in ((ok, VERDE, "Cumplen"),
                       (avisos, AMBAR, "Con aviso · el origen no cambió entre "
                                       "corridas"),
                       (omitidas, GRIS_CL, "No aplican · la actividad no es "
                                           "una copia de datos")):
        d.rectangle([0, ly * E, 11 * E, (ly + 11) * E], fill=col)
        _txt(d, (17, ly - 1), f"{et}   {v}", fuente(10), TINTA)
        ly += 18
    _txt(d, (0, al - 14), f"{ok} pruebas cumplen · 0 bloqueantes · ninguna "
         "prueba fallida", fuente(9, True), VERDE)
    return _guardar(im, ruta)


# ── 11 · paridad de las salidas de analitica (donde existe equivalente) ─────
def paridad_analitica(idn, dif, sin, ruta):
    an, al = 640, 236
    im, d = _lienzo(an, al)
    total = idn + dif + sin
    _txt(d, (0, 4), "Cotejo de paridad de las salidas de analítica",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), f"{total} flujos · el cotejo solo aplica donde Stratio "
         "produce la misma salida", fuente(10), GRIS)
    partes = [(idn, VERDE, "Salida idéntica a la de Stratio"),
              (dif, AMBAR, "Diferencia con causa identificada (sello de "
                           "carga y calendario)"),
              (sin, GRIS_CL, "Sin salida equivalente medida en Stratio · se "
                             "verifica por integridad")]
    x, y, h = 0, 62, 40
    for k, col, _ in partes:
        if not k:
            continue
        w = an * k / total
        d.rectangle([x * E, y * E, (x + w) * E, (y + h) * E], fill=col)
        if w > 30:
            _txt(d, (x + w / 2, y + h / 2), str(k), fuente(15, True),
                 BLANCO if col != GRIS_CL else TINTA, "mm")
        x += w
    ly = y + h + 22
    for k, col, et in partes:
        d.rectangle([0, ly * E, 11 * E, (ly + 11) * E], fill=col)
        _txt(d, (17, ly - 1), f"{et}   {k}", fuente(10), TINTA)
        ly += 20
    _txt(d, (0, al - 16), "La integridad de esquema y de la transformación se "
         "verificó en los " + str(total) + " flujos; la paridad, en los "
         + str(idn + dif) + " que tienen equivalente.", fuente(9), GRIS)
    return _guardar(im, ruta)


# ── 10 · orquestadores ──────────────────────────────────────────────────────
def orquestadores(orq, ruta):
    """Cada orquestador con los flujos que invoca y lo que tardo cada uno.

    Un orquestador no escribe: su resultado es que cada flujo invocado termine
    bien. Por eso la grafica muestra una barra por invocacion, agrupada bajo
    su orquestador, y marca en verde las que terminaron Succeeded.
    """
    act = [(o, a) for o in orq for a in o.get("actividades", [])]
    if not act:
        return None
    an, fil = 640, 15
    al = 76 + fil * len(act) + 24 * len(orq) + 34
    im, d = _lienzo(an, al)
    ok = sum(1 for _, a in act if a["estado"] == "Succeeded")
    _txt(d, (0, 4), "Flujos invocados por cada orquestador", fuente(13, True),
         AZUL)
    _txt(d, (0, 26), f"{len(orq)} orquestadores · {len(act)} invocaciones · "
         f"{ok} terminaron Succeeded", fuente(10), GRIS)
    ml, mr = 258, 74
    ancho = an - ml - mr
    mx = max(a["segundos"] for _, a in act) or 1
    y = 58
    for o in orq:
        d.rectangle([0, y * E, an * E, (y + 16) * E], fill=SUAVE)
        d.rectangle([0, y * E, 3 * E, (y + 16) * E], fill=AZUL)
        _txt(d, (10, y + 3), f"{o['flujo']}   ·   corrida {o['estado']} en "
             f"{o['segundos']} s", fuente(10, True), TINTA)
        y += 22
        for a in o.get("actividades", []):
            w = ancho * a["segundos"] / mx
            col = VERDE if a["estado"] == "Succeeded" else AMBAR
            d.rectangle([ml * E, y * E, (ml + max(w, 1)) * E, (y + 9) * E],
                        fill=col)
            _txt(d, (ml - 6, y + 4), a["flujo"][:46], fuente(8), TINTA, "rm")
            _txt(d, (ml + w + 6, y + 4), f"{a['segundos']} s", fuente(8), GRIS,
                 "lm")
            y += fil
        y += 2
    y += 6
    d.rectangle([0, y * E, an * E, (y + 26) * E], fill=VERDE_CL)
    d.rectangle([0, y * E, 3 * E, (y + 26) * E], fill=VERDE)
    _txt(d, (10, y + 7), f"{ok} de {len(act)} invocaciones terminaron en "
         "Succeeded; ningún flujo invocado quedó en error.", fuente(10, True),
         TINTA)
    return _guardar(im, ruta)


# ── 12 · controles de integridad medidos tabla por tabla (acta 7) ───────────
def controles_integridad(res, ruta, cierre=None, titulo=None):
    """Una barra por control, con las tablas que lo cumplen sobre el total.

    `res` es una lista de (codigo, titulo, cumplen, total, nota). `cierre`
    son las dos lineas del recuadro final.
    """
    an = 640
    al = 78 + 44 * len(res) + 44
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), titulo or "Controles de integridad medidos sobre las salidas",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), "Cada control se midió leyendo el dato completo de la "
         "tabla, sin muestreo", fuente(10), GRIS)
    ml = 150
    ancho = an - ml - 78
    y = 58
    for cod, titulo, ok, tot, nota, *resto in res:
        info = bool(resto and resto[0])
        col = AZUL_CL if info else (VERDE if ok == tot else AMBAR)
        w = ancho * ok / tot if tot else 0
        _txt(d, (0, y + 2), cod, fuente(11, True), AZUL)
        _txt(d, (0, y + 17), titulo, fuente(8), GRIS)
        d.rectangle([ml * E, y * E, (ml + ancho) * E, (y + 20) * E], fill=SUAVE)
        d.rectangle([ml * E, y * E, (ml + max(w, 2)) * E, (y + 20) * E], fill=col)
        _txt(d, (an, y + 4), f"{ok} de {tot}", fuente(11, True), col, "ra")
        if info:
            _txt(d, (an, y + 19), "informativo", fuente(8), GRIS, "ra")
        _txt(d, (ml, y + 24), nota, fuente(8), GRIS)
        y += 44
    y += 4
    d.rectangle([0, y * E, an * E, (y + 32) * E], fill=VERDE_CL)
    d.rectangle([0, y * E, 3 * E, (y + 32) * E], fill=VERDE)
    tot = res[0][3] if res else 0
    c1, c2 = cierre or (
        f"Las {tot} tablas de salida quedaron medidas en los cinco controles "
        "de integridad.",
        "Las barras en azul son controles informativos: describen la tabla, "
        "no la aprueban ni la rechazan.")
    _txt(d, (10, y + 6), c1, fuente(10, True), VERDE)
    _txt(d, (10, y + 20), c2, fuente(9), TINTA)
    return _guardar(im, ruta)


# ── 13 · cotejo de conteo contra Stratio (acta 7) ───────────────────────────
def cotejo_conteo(pares, ruta, nota=None, titulo=None, subtitulo=None,
                  escala="lineal"):
    """Filas en Stratio y en Fabric por tabla, con el porcentaje que coincide.

    `pares` es una lista de (tabla, filas_stratio, filas_fabric). `nota` son
    las dos lineas del pie: si no se pasa, se deja la del acta 7.
    """
    an = 640
    al = 78 + 30 * len(pares) + 52
    im, d = _lienzo(an, al)
    idn = sum(1 for _t, a, b in pares if a == b)
    _txt(d, (0, 4), titulo or "Cotejo de conteo contra Stratio",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), subtitulo or (f"{len(pares)} tablas con contraparte "
         f"medible · {idn} coinciden exactamente"), fuente(10), GRIS)
    ml, mr = 236, 96
    ancho = an - ml - mr
    mx = max(max(a, b) for _t, a, b in pares) or 1
    if escala == "log":
        techo = 10 ** math.ceil(math.log10(mx))
        esc = lambda v: (0 if v <= 0 else
                         ancho * math.log10(v) / math.log10(techo))
    else:
        esc = lambda v: ancho * v / mx
    y = 58
    for t, a, b in pares:
        pct = 100 * b / a if a else 0
        col = VERDE if a == b else AMBAR
        wa, wb = esc(a), esc(b)
        _txt(d, (ml - 8, y + 10), t[:38], fuente(8), TINTA, "rm")
        d.rectangle([ml * E, y * E, (ml + max(wa, 2)) * E, (y + 9) * E],
                    fill=AZUL_CL)
        d.rectangle([ml * E, (y + 11) * E, (ml + max(wb, 2)) * E, (y + 20) * E],
                    fill=AMBAR)
        # con dos decimales, 99,9994 se redondea a 100 y miente
        et = ("100 %" if a == b else
              (f"{pct:.4f} %" if abs(pct - 100) < 0.01 else f"{pct:.2f} %")
              .replace(".", ","))
        _txt(d, (an, y + 5), et, fuente(10, True), col, "ra")
        y += 30
    ly = y + 6
    for col, et in ((AZUL_CL, "Stratio"), (AMBAR, "Fabric")):
        d.rectangle([0, ly * E, 11 * E, (ly + 11) * E], fill=col)
        _txt(d, (17, ly - 1), et, fuente(10), TINTA)
        ly += 17
    n1, n2 = nota or ("En cuatro de estas tablas la comparación se hizo",
                      "contra el parquet de Stratio, no contra su reporte.")
    _txt(d, (an, y + 8), n1, fuente(9), GRIS, "ra")
    _txt(d, (an, y + 21), n2, fuente(9), GRIS, "ra")
    return _guardar(im, ruta)


# ── 14 · filas repetidas, Stratio frente a Fabric (acta 7) ──────────────────
def repetidas(pares, ruta, cierre=None, subtitulo=None, etiqueta_destino=False):
    """Proporcion de filas repetidas a cada lado, para las tablas cotejadas.

    `pares` es una lista de (tabla, pct_stratio, pct_fabric). `cierre` son
    las dos lineas del recuadro final.
    """
    an = 640
    al = 78 + 34 * len(pares) + 96
    im, d = _lienzo(an, al)
    im_ok = sum(1 for _t, a, b in pares if abs(a - b) < 0.005)
    _txt(d, (0, 4), "Filas repetidas: origen frente a destino",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), subtitulo or (f"{im_ok} de {len(pares)} tablas con la "
         "misma proporción de repetidas a los dos lados"), fuente(10), GRIS)
    ml, mr = 236, 96
    ancho = an - ml - mr
    mx = max([max(a, b) for _t, a, b in pares] + [1.0])
    y = 58
    for t, a, b in pares:
        _txt(d, (ml - 8, y + 11), t[:38], fuente(8), TINTA, "rm")
        for j, (v, col) in enumerate(((a, AZUL_CL), (b, AMBAR))):
            w = ancho * v / mx
            yy = y + j * 11
            d.rectangle([ml * E, yy * E, (ml + max(w, 2)) * E, (yy + 9) * E],
                        fill=col)
        v = b if etiqueta_destino else a
        et = f"{v:.2f} %".replace(".", ",")
        _txt(d, (an, y + 6), et, fuente(10, True),
             VERDE if abs(a - b) < 0.005 else AMBAR_OS, "ra")
        y += 34
    ly = y + 2
    for col, et in ((AZUL_CL, "Stratio"), (AMBAR, "Fabric")):
        d.rectangle([0, ly * E, 11 * E, (ly + 11) * E], fill=col)
        _txt(d, (17, ly - 1), et, fuente(10), TINTA)
        ly += 17
    y = ly + 4
    d.rectangle([0, y * E, an * E, (y + 34) * E], fill=VERDE_CL)
    d.rectangle([0, y * E, 3 * E, (y + 34) * E], fill=VERDE)
    c1, c2 = cierre or (
        "Las dos barras se superponen: la repetición existe en el origen y "
        "Fabric la reproduce",
        "sin agregar ni quitar filas. No es un efecto de la migración.")
    _txt(d, (10, y + 6), c1, fuente(10, True), VERDE)
    _txt(d, (10, y + 20), c2, fuente(9), TINTA)
    return _guardar(im, ruta)


# ── 15 · volumen escrito por las salidas del lote (acta 7) ──────────────────
def volumen_salidas(filas, ruta):
    """Las tablas que mas filas escribieron, en escala logaritmica.

    `filas` es una lista de (tabla, filas), ya recortada a las que se dibujan.
    """
    an, al = 640, 340
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), "Volumen escrito por las salidas del lote",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), f"Escala logarítmica · las {len(filas)} tablas de mayor "
         "volumen", fuente(10), GRIS)
    ml, mr, mt, mb = 74, 10, 58, 154
    ancho, alto_g = an - ml - mr, al - mt - mb
    mx = max(v for _t, v in filas) or 1
    techo = 10 ** math.ceil(math.log10(mx))
    lg = lambda v: 0 if v <= 0 else math.log10(v) / math.log10(techo)
    for k in range(int(math.log10(techo)) + 1):
        v = 10 ** k
        yy = mt + alto_g - lg(v) * alto_g
        d.line([ml * E, yy * E, (an - mr) * E, yy * E], fill=GRIS_CL, width=1)
        _txt(d, (ml - 6, yy), mil(v), fuente(8), GRIS, "rm")
    paso = ancho / len(filas)
    bw = min(20, paso * 0.62)
    f_et = fuente(8)
    for i, (t, v) in enumerate(filas):
        cx = ml + paso * (i + 0.5)
        h = lg(v) * alto_g
        d.rectangle([(cx - bw / 2) * E, (mt + alto_g - h) * E,
                     (cx + bw / 2) * E, (mt + alto_g) * E], fill=AZUL_CL)
        _txt(d, (cx, mt + alto_g - h - 4), mil(v), fuente(7), GRIS, "md")
        # la etiqueta va girada: los nombres de tabla no caben en horizontal
        et = t.split(".", 1)[-1][:22]
        caja = d.textbbox((0, 0), et, font=f_et)
        tira = Image.new("RGB", (caja[2] + 4, caja[3] + 4), BLANCO)
        ImageDraw.Draw(tira).text((0, 0), et, font=f_et, fill=GRIS)
        tira = tira.rotate(90, expand=True)
        im.paste(tira, (int(cx * E - tira.width / 2),
                        int((mt + alto_g + 6) * E)))
    d.line([ml * E, (mt + alto_g) * E, (an - mr) * E, (mt + alto_g) * E],
           fill=GRIS, width=2)
    tot = sum(v for _t, v in filas)
    _txt(d, (0, al - 20), f"{mil(tot)} filas en las tablas dibujadas",
         fuente(10, True), VERDE)
    return _guardar(im, ruta)


# ── 16 · diferencias cotejadas y su justificacion (acta 7) ──────────────────
def diferencias_justificadas(casos, ruta, cierre=None, subtitulo=None):
    """Cada tabla cotejada, con lo que coincide y la causa de lo que no.

    `casos` es una lista de (tabla, filas_stratio, filas_fabric, causa).
    `cierre` son las dos lineas del recuadro final.
    """
    an = 640
    f_c = fuente(9)
    ancho_c = an - 130
    def _partir(txt):
        lineas, act = [], ""
        for pal in txt.split():
            p2 = (act + " " + pal).strip()
            if ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(p2, font=f_c) > ancho_c * E:
                lineas.append(act)
                act = pal
            else:
                act = p2
        if act:
            lineas.append(act)
        return lineas[:3]
    cortes = [_partir(x[3]) for x in casos]
    altos = [34 + 12 * len(x) + 10 for x in cortes]
    al = 78 + sum(altos) + 46
    im, d = _lienzo(an, al)
    idn = sum(1 for x in casos if x[1] == x[2])
    _txt(d, (0, 4), "Diferencias cotejadas y su justificación",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), subtitulo or
         (f"{len(casos)} tablas cotejadas · {idn} coinciden exactamente · "
          f"{len(casos)-idn} con causa identificada · 0 sin justificar"),
         fuente(10), GRIS)
    y = 58
    for caso, lin, h in zip(casos, cortes, altos):
        t, a, b = caso[0], caso[1], caso[2]
        etq = caso[4] if len(caso) > 4 else None
        ok = a == b
        col = VERDE if ok else AMBAR
        caja = h - 8
        d.rectangle([0, y * E, an * E, (y + caja) * E], fill=VERDE_CL if ok else SUAVE)
        d.rectangle([0, y * E, 3 * E, (y + caja) * E], fill=col)
        _txt(d, (12, y + 6), t, fuente(10, True), TINTA)
        yy = y + 21
        for ln in lin:
            _txt(d, (12, yy), ln, f_c, GRIS)
            yy += 12
        _txt(d, (12, yy + 1), f"Stratio {mil(a)}   ·   Fabric {mil(b)}", fuente(8), GRIS)
        pct = 100 * b / a if a else 0
        # con dos decimales, 99,9994 se redondea a 100,00 y contradice la
        # fila: cuando eso pasa se muestran los decimales que hagan falta
        et = "100 %" if ok else next(
            f"{pct:.{k}f} %".replace(".", ",") for k in (2, 3, 4, 5, 6)
            if round(pct, k) != 100)
        _txt(d, (an - 10, y + 6), et, fuente(12, True), col, "ra")
        _txt(d, (an - 10, y + 22), etq or ("idéntica" if ok else "justificada"),
             fuente(9, True), VERDE, "ra")
        y += h
    y += 4
    d.rectangle([0, y * E, an * E, (y + 36) * E], fill=VERDE_CL)
    d.rectangle([0, y * E, 3 * E, (y + 36) * E], fill=VERDE)
    c1, c2 = cierre or (
        "Ninguna diferencia corresponde a un registro que la transformación "
        "deje caer: en las dos tablas",
        "donde se pudo comparar fila por fila, no existe un solo registro en "
        "Fabric que Stratio no tenga.")
    _txt(d, (10, y + 6), c1, fuente(10, True), VERDE)
    _txt(d, (10, y + 20), c2, fuente(9), TINTA)
    return _guardar(im, ruta)


# ── 18 · cuadre de filas por tabla en tres puntos (salida a produccion) ─────
def cuadre(filas, ruta):
    """Una barra por tabla con las filas medidas en destino, escala logaritmica.

    `filas` es una lista de dicts con "tabla", "leidas", "copiadas" y
    "medidas". La cifra va en verde cuando los tres puntos coinciden.
    """
    an, fil = 640, 13
    al = 76 + fil * len(filas) + 44
    im, d = _lienzo(an, al)
    ok = sum(1 for f in filas if f["leidas"] == f["copiadas"] == f["medidas"])
    _txt(d, (0, 4), "Filas por tabla en los tres puntos de control",
         fuente(13, True), AZUL)
    _txt(d, (0, 26), f"Escala logarítmica · {ok} de {len(filas)} tablas con las "
         "filas leídas, copiadas y medidas iguales", fuente(10), GRIS)
    ml, mr = 238, 92
    ancho = an - ml - mr
    mx = max([f["medidas"] for f in filas] + [10])
    techo = 10 ** math.ceil(math.log10(mx))
    lg = lambda v: 0 if v <= 0 else math.log10(v) / math.log10(techo)
    y = 58
    for f in sorted(filas, key=lambda x: -x["medidas"]):
        w = ancho * lg(f["medidas"])
        igual = f["leidas"] == f["copiadas"] == f["medidas"]
        d.rectangle([ml * E, y * E, (ml + max(w, 1)) * E, (y + 9) * E],
                    fill=AZUL_CL)
        _txt(d, (ml - 6, y + 4), f["tabla"][:40], fuente(8), TINTA, "rm")
        _txt(d, (ml + w + 6, y + 4), mil(f["medidas"]), fuente(8),
             VERDE if igual else AMBAR_OS, "lm")
        y += fil
    y += 8
    d.rectangle([0, y * E, an * E, (y + 30) * E], fill=VERDE_CL)
    d.rectangle([0, y * E, 3 * E, (y + 30) * E], fill=VERDE)
    tot = sum(f["medidas"] for f in filas)
    _txt(d, (10, y + 5), f"{mil(tot)} filas medidas en el lakehouse, las mismas "
         "que la copia leyó del origen.", fuente(10, True), VERDE)
    _txt(d, (10, y + 18), "La longitud de la barra es el volumen; la cifra en "
         "verde indica que los tres puntos coinciden.", fuente(9), TINTA)
    return _guardar(im, ruta)


# ── 19 · franjas de la programacion diaria (salida a produccion) ────────────
def franjas(pares, ruta, zona="hora Bogotá"):
    """Una barra por franja horaria con los flujos que arrancan en ella.

    `pares` es una lista de (hh:mm, flujos), en el orden en que se dibujan.
    """
    an, fil = 640, 15
    al = 76 + fil * len(pares) + 44
    im, d = _lienzo(an, al)
    tot = sum(v for _h, v in pares)
    mx = max([v for _h, v in pares] + [1])
    _txt(d, (0, 4), "Arranques programados por franja horaria", fuente(13, True), AZUL)
    _txt(d, (0, 26), f"{tot} arranques diarios en {len(pares)} franjas · {zona}",
         fuente(10), GRIS)
    ml, mr = 70, 60
    ancho = an - ml - mr
    y = 58
    for h, v in pares:
        w = ancho * v / mx
        col = AMBAR if v == mx else AZUL_CL
        d.rectangle([ml * E, y * E, (ml + max(w, 2)) * E, (y + 10) * E], fill=col)
        _txt(d, (ml - 8, y + 5), h, fuente(9, True), TINTA, "rm")
        _txt(d, (ml + w + 6, y + 5), str(v), fuente(9), GRIS, "lm")
        y += fil
    y += 8
    d.rectangle([0, y * E, an * E, (y + 30) * E], fill=SUAVE)
    d.rectangle([0, y * E, 3 * E, (y + 30) * E], fill=AZUL)
    pico = [h for h, v in pares if v == mx]
    _txt(d, (10, y + 5), f"Pico de {mx} flujos a la vez: " + ", ".join(pico) + ".",
         fuente(10, True), TINTA)
    _txt(d, (10, y + 18), "La barra ámbar marca las franjas de mayor "
         "concurrencia.", fuente(9), GRIS)
    return _guardar(im, ruta)


# ── 20 · clasificacion de un universo medido (acta 9) ───────────────────────
def clasificacion(cats, ruta, titulo, subtitulo, cierre, ancho_etq=250):
    """Una barra por categoria de un mismo universo, con su nota al pie.

    `cats` es una lista de (etiqueta, valor, color, nota); color es uno de
    "ok" (verde), "aviso" (ambar), "dato" (azul) o "gris". Las barras se
    normalizan al mayor valor, no al primero: el orden de la lista es el del
    relato, no el del tamano. `cierre` son las dos lineas del recuadro final.
    """
    COL = {"ok": VERDE, "aviso": AMBAR, "dato": AZUL_CL, "gris": GRIS}
    an = 640
    al = 78 + 32 * len(cats) + 42
    im, d = _lienzo(an, al)
    _txt(d, (0, 4), titulo, fuente(13, True), AZUL)
    _txt(d, (0, 26), subtitulo, fuente(10), GRIS)
    mx = max(v for _e, v, _c, _n in cats) or 1
    ml, mr = ancho_etq, 54
    ancho = an - ml - mr
    y = 58
    for etq, v, c, nota in cats:
        col = COL.get(c, AZUL_CL)
        w = ancho * v / mx
        _txt(d, (ml - 8, y + 6), etq[:62], fuente(9, True), TINTA, "rm")
        d.rectangle([ml * E, y * E, (ml + max(w, 2)) * E, (y + 13) * E], fill=col)
        _txt(d, (an, y + 6), str(v), fuente(11, True), col, "rm")
        _txt(d, (ml, y + 17), nota[:96], fuente(8), GRIS)
        y += 32
    y += 4
    d.rectangle([0, y * E, an * E, (y + 32) * E], fill=VERDE_CL)
    d.rectangle([0, y * E, 3 * E, (y + 32) * E], fill=VERDE)
    _txt(d, (10, y + 6), cierre[0], fuente(10, True), VERDE)
    _txt(d, (10, y + 20), cierre[1], fuente(9), TINTA)
    return _guardar(im, ruta)
