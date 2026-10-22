"""Gráficas del acta normalizada (desde el 2026-10-22): completas, sin cortes y legibles en cualquier escala.

Reglas (pedido de QA 2026-10-22):
  · Nada se corta: si una gráfica no cabe en una hoja se parte en varias («1 de 3»), con todas las tablas.
  · Escala que deja ver la diferencia: si la tabla más grande es > 50 veces la más pequeña, escala logarítmica con su
    rejilla marcada; las diferencias se muestran además en su propia gráfica (Fabric − Stratio en %), centrada en 0.
  · Cada barra lleva su cifra; dos series siempre con leyenda; etiquetas largas en dos líneas, no recortadas a ciegas.
  · Se guardan a doble resolución (nítidas al imprimir); el generador escala por el ancho real del PNG.
Stratio azul #3D5A98, Fabric ámbar #A86A00 (par validado para daltonismo), verde = coincide.
"""
import datetime as dt
import math

import graficas as G

ST, FB = (61, 90, 152), (168, 106, 0)
VERDE, GRIS, GRIS_CL, TINTA, AZUL = G.VERDE, G.GRIS, G.GRIS_CL, G.TINTA, G.AZUL
ROJO_SUAVE = (176, 58, 46)
AN = 640                 # ancho lógico (px a 96 ppp: 6,67")
ALTO_MAX = 820           # alto lógico máximo por imagen: cabe en una hoja carta con su pie
E = 2                    # se guarda a doble resolución


def _f(t, b=False):
    return G.fuente(t, b)


def _lienzo(al):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (AN * E, int(al) * E), (255, 255, 255))
    return im, ImageDraw.Draw(im)


def _t(d, xy, s, f, c=TINTA, a="la"):
    d.text((xy[0] * E, xy[1] * E), s, font=f, fill=c, anchor=a)


def _r(d, x0, y0, x1, y1, c, radio=True):
    if x1 < x0:
        x0, x1 = x1, x0
    if radio and (x1 - x0) > 5:
        d.rounded_rectangle([x0 * E, y0 * E, x1 * E, y1 * E], radius=2 * E, fill=c)
    else:
        d.rectangle([x0 * E, y0 * E, max(x1, x0 + 1) * E, y1 * E], fill=c)


def _guardar(im, ruta):
    import os
    os.makedirs(os.path.dirname(os.path.abspath(ruta)) or ".", exist_ok=True)
    im.save(ruta, "PNG", optimize=True)
    return ruta


def mil(v):
    if v is None:
        return "sin dato"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(v):,}".replace(",", ".")


def corto(v):
    """1.234.567 → 1,2 M; 12.300 → 12,3 mil."""
    v = float(v)
    for lim, suf in ((1e9, " mil M"), (1e6, " M"), (1e3, " mil")):
        if abs(v) >= lim:
            return f"{v / lim:.1f}".replace(".", ",").replace(",0", "") + suf
    return mil(int(v))


def _dos_lineas(s, n=34):
    s = str(s)
    if len(s) <= n:
        return [s]
    corte = max(s.rfind(c, 0, n) for c in "_-. ·")
    corte = corte if corte > n // 2 else n
    a, b = s[:corte + (1 if s[corte:corte + 1] in "_-. " else 0)], s[corte + (1 if s[corte:corte + 1] in "_-. " else 0):]
    return [a, b if len(b) <= n else b[:n - 1] + "…"]


def paginar(items, por_hoja):
    """[(items_hoja, k, n)] para partir una gráfica larga en varias imágenes completas."""
    if not items:
        return []
    n = math.ceil(len(items) / por_hoja)
    tam = math.ceil(len(items) / n)            # hojas parejas: 23 + 22 en vez de 30 + 15
    return [(items[i:i + tam], k + 1, n) for k, i in enumerate(range(0, len(items), tam))]


def _cabecera(d, titulo, sub, k, n):
    _t(d, (0, 4), titulo + (f"  ·  {k} de {n}" if n > 1 else ""), _f(13, True), AZUL)
    _t(d, (0, 26), sub, _f(10), GRIS)


def _leyenda(d, y, series):
    x = 0
    for t, c in series:
        _r(d, x, y, x + 10, y + 10, c)
        _t(d, (x + 14, y + 5), t, _f(9), TINTA, "lm")
        x += 24 + int(_f(9).getlength(t) / E) + 10


# ── filas enfrentadas, con escala que deja ver tablas chicas junto a grandes ─────
def pares(items, ruta_base, titulo, sub):
    """items = [(tabla, filas_stratio, filas_fabric)]. Devuelve [rutas], una por hoja."""
    if not items:
        return []
    vals = [v for _, a, b in items for v in (a, b) if v]
    log = bool(vals) and max(vals) / max(1, min(vals)) > 50
    fil = 30
    por_hoja = max(1, (ALTO_MAX - 110) // fil)
    rutas = []
    mx = max(vals) if vals else 1
    for hoja, k, n in paginar(items, por_hoja):
        al = 104 + fil * len(hoja) + 26
        im, d = _lienzo(al)
        _cabecera(d, titulo, sub + (" · escala logarítmica: cada línea es 10 veces la anterior" if log else ""), k, n)
        _leyenda(d, 46, (("Stratio", ST), ("Fabric", FB)))
        ml, mr, y0 = 250, 120, 76
        ancho = AN - ml - mr - 62          # deja sitio a la cifra de la barra más larga antes de la columna de diferencia
        _t(d, (AN - mr + 8, y0 - 12), "Fabric − Stratio", _f(8, True), GRIS)

        def x(v):
            if not v:
                return ml
            if log:
                return ml + ancho * math.log10(max(v, 1)) / math.log10(max(mx, 10))
            return ml + ancho * v / mx
        if log:      # rejilla en potencias de 10
            p = 0
            while 10 ** p <= mx * 1.0001:
                xx = x(10 ** p)
                d.line([xx * E, (y0 - 4) * E, xx * E, (y0 + fil * len(hoja)) * E], fill=GRIS_CL, width=E)
                _t(d, (xx, y0 + fil * len(hoja) + 4), corto(10 ** p), _f(7), GRIS, "ma")
                p += 1
        y = y0
        for et, a, b in hoja:
            for j, (v, c) in enumerate(((a, ST), (b, FB))):
                yy = y + j * 11
                _r(d, ml, yy, x(v), yy + 9, c)
                _t(d, (x(v) + 4, yy + 4), mil(v) if v is not None else "sin dato", _f(7), GRIS, "lm")
            ls = _dos_lineas(et)
            for i, l in enumerate(ls):
                _t(d, (ml - 6, y + 10 + (i - (len(ls) - 1) / 2) * 11), l, _f(8), TINTA, "rm")
            if a is not None and b is not None:
                dl = b - a
                pc = (100 * dl / a) if a else None
                col = VERDE if dl == 0 else FB
                _t(d, (AN - mr + 8, y + 5), ("=" if dl == 0 else f"{'+' if dl > 0 else '−'}{mil(abs(dl))}"), _f(8, True), col, "lm")
                if dl and pc is not None:
                    _t(d, (AN - mr + 8, y + 16), f"{pc:+.2f} %".replace(".", ",").replace("+", "+ ").replace("-", "− "), _f(7), GRIS, "lm")
            y += fil
        rutas.append(_guardar(im, f"{ruta_base}_{k}.png" if n > 1 else f"{ruta_base}.png"))
    return rutas


# ── diferencia relativa, centrada en 0 ──────────────────────────────────────────
def diferencias(items, ruta_base, titulo, sub):
    """items = [(tabla, filas_stratio, filas_fabric)] con las dos cifras. Barras divergentes de (F − S) / S en %.
    El eje se ajusta a la mayor diferencia (mínimo ±1 %) para que una diferencia chica se vea."""
    its = [(t, a, b, (100 * (b - a) / a) if a else (100.0 if b else 0.0)) for t, a, b in items if a is not None and b is not None]
    if not its:
        return []
    its.sort(key=lambda x: -abs(x[3]))
    lim = max(1.0, max(abs(p) for *_, p in its))
    lim = min(lim, 100.0) if lim > 100 else lim
    fil = 18
    por_hoja = max(1, (ALTO_MAX - 100) // fil)
    rutas = []
    for hoja, k, n in paginar(its, por_hoja):
        al = 84 + fil * len(hoja) + 30
        im, d = _lienzo(al)
        _cabecera(d, titulo, sub, k, n)
        ml, mr, y0 = 250, 110, 60
        c0 = ml + (AN - ml - mr) / 2
        mitad = (AN - ml - mr) / 2
        d.line([c0 * E, (y0 - 6) * E, c0 * E, (y0 + fil * len(hoja)) * E], fill=GRIS, width=E)
        for v in (-lim, -lim / 2, lim / 2, lim):
            xx = c0 + mitad * v / lim
            d.line([xx * E, (y0 - 2) * E, xx * E, (y0 + fil * len(hoja)) * E], fill=GRIS_CL, width=E)
            _t(d, (xx, y0 + fil * len(hoja) + 4), f"{v:+.1f} %".replace(".", ",").replace("-", "−"), _f(7), GRIS, "ma")
        _t(d, (c0, y0 + fil * len(hoja) + 16), "0 = mismas filas", _f(7), GRIS, "ma")
        y = y0
        for et, a, b, p in hoja:
            pv = max(-lim, min(lim, p))
            col = VERDE if b == a else (FB if b > a else ST)
            _r(d, c0, y + 3, c0 + mitad * pv / lim, y + 12, col, radio=False)
            if b == a:
                d.ellipse([(c0 - 3) * E, (y + 4) * E, (c0 + 3) * E, (y + 10) * E], fill=VERDE)
            ls = _dos_lineas(et, 40)
            _t(d, (ml - 6, y + 8), ls[0] if len(ls) == 1 else ls[0] + "…", _f(8), TINTA, "rm")
            pt = f"{p:+.2f}".replace(".", ",").replace("-", "−")
            _t(d, (AN - mr + 8, y + 8), ("=" if b == a else f"{'+' if b > a else '−'}{mil(abs(b - a))} ({pt} %)"),
               _f(7, b != a), col if b != a else VERDE, "lm")
            y += fil
        rutas.append(_guardar(im, f"{ruta_base}_{k}.png" if n > 1 else f"{ruta_base}.png"))
    return rutas


# ── barras de una serie (duraciones, columnas idénticas), paginadas ─────────────
def barras(items, ruta_base, titulo, sub, valor_txt, maximo=None, ref=None, cierre=None):
    """items = [(etiqueta, valor, color)]."""
    if not items:
        return []
    fil = 16
    por_hoja = max(1, (ALTO_MAX - 110) // fil)
    mx = maximo or max(v for _, v, _ in items) or 1
    rutas = []
    for hoja, k, n in paginar(items, por_hoja):
        al = 66 + fil * len(hoja) + (44 if cierre and k == n else 14)
        im, d = _lienzo(al)
        _cabecera(d, titulo, sub, k, n)
        ml, mr, y = 250, 80, 56
        ancho = AN - ml - mr
        if ref is not None:
            xr = ml + ancho * ref / mx
            d.line([xr * E, (y - 4) * E, xr * E, (y + fil * len(hoja)) * E], fill=GRIS_CL, width=2 * E)
        for et, v, col in hoja:
            _r(d, ml, y, ml + ancho * min(v, mx) / mx, y + 10, col)
            ls = _dos_lineas(et, 44)
            _t(d, (ml - 6, y + 5), ls[0] if len(ls) == 1 else ls[0] + "…", _f(8), TINTA, "rm")
            _t(d, (ml + ancho * min(v, mx) / mx + 6, y + 5), valor_txt(v), _f(8), GRIS, "lm")
            y += fil
        if cierre and k == n:
            y += 8
            d.rectangle([0, y * E, AN * E, (y + 26) * E], fill=G.SUAVE)
            d.rectangle([0, y * E, 3 * E, (y + 26) * E], fill=AZUL)
            _t(d, (10, y + 7), cierre, _f(10, True), TINTA)
        rutas.append(_guardar(im, f"{ruta_base}_{k}.png" if n > 1 else f"{ruta_base}.png"))
    return rutas


# ── línea de tiempo de las corridas ─────────────────────────────────────────────
def _dt(s):
    return dt.datetime.fromisoformat(str(s)[:19])


def linea_tiempo(items, ruta_base, titulo, sub):
    """items = [(flujo, inicio_iso, fin_iso, color)]. Cada corrida en su hora real: se ve qué corrió a la vez, en qué orden
    y cuánto tardó. Si las corridas abarcan varios días, cada hoja cubre su propia ventana."""
    its = sorted([(f, _dt(a), _dt(b), c) for f, a, b, c in items if a and b], key=lambda x: x[1])
    if not its:
        return []
    fil = 16
    por_hoja = max(1, (ALTO_MAX - 120) // fil)
    # una hoja por día de corridas: en una ventana de varios días una corrida de minutos sería una raya sin lectura
    hojas, dias = [], {}
    for x in its:
        dias.setdefault(x[1].date(), []).append(x)
    for dia in sorted(dias):
        hojas += [h for h, _, _ in paginar(dias[dia], por_hoja)]
    rutas = []
    for k, hoja in enumerate(hojas, 1):
        n = len(hojas)
        t0, t1 = min(x[1] for x in hoja), max(x[2] for x in hoja)
        span = max((t1 - t0).total_seconds(), 60)
        al = 96 + fil * len(hoja) + 34
        im, d = _lienzo(al)
        _cabecera(d, titulo, sub, k, n)
        _t(d, (0, 42), f"{t0:%Y-%m-%d} · de {t0:%H:%M} a {t1:%H:%M} UTC · {len(hoja)} corrida(s)", _f(9, True), TINTA)
        ml, mr, y0 = 210, 70, 66
        ancho = AN - ml - mr
        X = lambda t: ml + ancho * (t - t0).total_seconds() / span
        paso = next(p for p in (60, 300, 600, 1800, 3600, 7200, 21600, 43200, 86400, 172800, 604800) if span / p <= 8)
        t = t0.replace(second=0, microsecond=0)
        t = t - dt.timedelta(seconds=(t.hour * 3600 + t.minute * 60) % paso) if paso < 86400 else t.replace(hour=0, minute=0)
        while t <= t1:
            if t >= t0:
                xx = X(t)
                d.line([xx * E, (y0 - 4) * E, xx * E, (y0 + fil * len(hoja)) * E], fill=GRIS_CL, width=E)
                _t(d, (xx, y0 + fil * len(hoja) + 4), t.strftime("%H:%M" if paso < 86400 else "%d-%m"), _f(7), GRIS, "ma")
            t += dt.timedelta(seconds=paso)
        y = y0
        for f, a, b, c in hoja:
            _r(d, X(a), y + 2, max(X(b), X(a) + 2), y + 11, c, radio=False)
            s = int((b - a).total_seconds())
            _t(d, (max(X(b), X(a) + 2) + 4, y + 7), f"{s // 60} min {s % 60:02d} s", _f(7), GRIS, "lm")
            ls = _dos_lineas(f, 36)
            _t(d, (ml - 6, y + 7), ls[0] if len(ls) == 1 else ls[0] + "…", _f(8), TINTA, "rm")
            y += fil
        rutas.append(_guardar(im, f"{ruta_base}_{k}.png" if n > 1 else f"{ruta_base}.png"))
    return rutas


# ── controles por familia: cumple · justificado · no aplica · no evaluado ──────
ESTADOS = (("cumple", VERDE), ("justificado", (120, 160, 120)), ("no aplica", GRIS_CL), ("no evaluado", ROJO_SUAVE))


def controles(conteos, ruta, titulo, sub):
    """conteos = {familia o etiqueta: {estado: n}} → barras apiladas al 100 %, con la cifra dentro de cada tramo."""
    if not conteos:
        return None
    fil = 30
    al = 84 + fil * len(conteos) + 16
    im, d = _lienzo(al)
    _cabecera(d, titulo, sub, 1, 1)
    _leyenda(d, 46, [(e, c) for e, c in ESTADOS if any(x.get(e) for x in conteos.values())])
    ml, mr, y = 120, 20, 70
    ancho = AN - ml - mr
    for et, c in conteos.items():
        tot = sum(c.values()) or 1
        x = ml
        for est, col in ESTADOS:
            v = c.get(est, 0)
            if not v:
                continue
            w = ancho * v / tot
            _r(d, x, y, x + w, y + 18, col, radio=False)
            if w > 18:
                _t(d, (x + w / 2, y + 9), str(v), _f(8, True), (255, 255, 255) if est != "no aplica" else TINTA, "mm")
            x += w
        _t(d, (ml - 6, y + 9), f"{et} ({tot})", _f(9, True), TINTA, "rm")
        y += fil
    return _guardar(im, ruta)
