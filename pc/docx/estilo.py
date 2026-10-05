"""Copia de actas/estilo.py (generador de actas entregadas): helpers del .docx. Se usa tal cual."""
"""Construccion del .docx de las actas.

El formato replica el del «Acta de Decision Tecnica»: Calibri, azul Comfandi
para titulos, filete ambar a la izquierda de cada titulo, logo de Quind en la
cabecera y portada sin cabecera. Sin dependencias externas: se arma el OOXML.
"""
import os
import zipfile
from xml.sax.saxutils import escape

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(AQUI, "recursos", "quind.png")

TINTA = "1A2332"      # texto normal
AZUL = "1A3A5C"       # titulos
GRIS = "546E7A"       # texto secundario
VERDE = "1E7A46"      # resultado favorable
AMBAR = "8A6100"      # texto sobre fondo ambar
ACENTO = "F5A623"     # el ambar del acta de referencia
FONDO_CAB = "EEF2F6"  # encabezado de tabla
FONDO_OK = "E8F3EC"
FONDO_AV = "FFF6DC"
FONDO_QD = "FFFBEF"

F = ('<w:rFonts w:ascii="Calibri" w:eastAsia="Calibri" w:hAnsi="Calibri" '
     'w:cs="Calibri"/>')
MONO = ('<w:rFonts w:ascii="Consolas" w:eastAsia="Consolas" w:hAnsi="Consolas" '
        'w:cs="Consolas"/>')


def run(t, sz=20, color=TINTA, b=False, i=False, mono=False):
    return (f'<w:r><w:rPr>{MONO if mono else F}'
            f'{"<w:b/><w:bCs/>" if b else ""}{"<w:i/><w:iCs/>" if i else ""}'
            f'<w:color w:val="{color}"/><w:sz w:val="{sz}"/>'
            f'<w:szCs w:val="{sz}"/></w:rPr>'
            # un salto de linea en el texto es un salto de linea de Word, no un caracter que Word ignora
            + '<w:br/>'.join(f'<w:t xml:space="preserve">{escape(x)}</w:t>' for x in str(t).split("\n"))
            + '</w:r>')


def parrafo(runs, antes=0, despues=140, linea=276, alin=None, borde=None,
            fondo=None, sangria=0):
    # Un str puede ser texto suelto o un run ya construido. Si ya viene como
    # XML no se vuelve a envolver: hacerlo escaparia las etiquetas y el parrafo
    # mostraria el marcado en vez del texto.
    if isinstance(runs, str) and not runs.lstrip().startswith("<w:"):
        runs = run(runs)
    pr = (f'<w:spacing w:before="{antes}" w:after="{despues}" w:line="{linea}" '
          'w:lineRule="auto"/>')
    if alin:
        pr += f'<w:jc w:val="{alin}"/>'
    if sangria:
        pr += f'<w:ind w:left="{sangria}"/>'
    if borde:
        pr += (f'<w:pBdr><w:left w:val="single" w:sz="24" w:space="8" '
               f'w:color="{borde}"/></w:pBdr>')
    if fondo:
        pr += f'<w:shd w:val="clear" w:color="auto" w:fill="{fondo}"/>'
    return f"<w:p><w:pPr>{pr}</w:pPr>{runs}</w:p>"


def h1(t):
    """Titulo de seccion con el filete ambar del acta de referencia."""
    return parrafo(run(t, 34, AZUL, b=True), antes=440, despues=160, linea=240,
                   borde=ACENTO)


def h2(t):
    return parrafo(run(t, 24, AZUL, b=True), antes=280, despues=120, linea=240)


def celda(txt, ancho, fondo="FFFFFF", b=False, color=TINTA, sz=18, alin=None,
          mono=False):
    pr = f'<w:jc w:val="{alin}"/>' if alin else ""
    return (f'<w:tc><w:tcPr><w:tcW w:w="{ancho}" w:type="dxa"/>'
            f'<w:shd w:val="clear" w:color="auto" w:fill="{fondo}"/>'
            '<w:tcMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
            '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/>'
            '</w:tcMar><w:vAlign w:val="center"/></w:tcPr>'
            '<w:p><w:pPr><w:spacing w:before="20" w:after="20" w:line="240" '
            f'w:lineRule="auto"/>{pr}</w:pPr>'
            f'{run(txt, sz, color, b=b, mono=mono)}</w:p></w:tc>')


_BORDES = ('<w:tblBorders>' + "".join(
    f'<w:{x} w:val="single" w:sz="4" w:space="0" w:color="CFD8DC"/>'
    for x in ("top", "left", "bottom", "right", "insideH", "insideV")) +
    '</w:tblBorders>')


def _abrir_tabla(anchos):
    return (f'<w:tbl><w:tblPr><w:tblStyle w:val="TableNormal"/>'
            f'<w:tblW w:w="{sum(anchos)}" w:type="dxa"/>'
            f'<w:tblInd w:w="0" w:type="dxa"/>{_BORDES}'
            '<w:tblLayout w:type="fixed"/>'
            '<w:tblLook w:val="0000" w:firstRow="0" w:lastRow="0" '
            'w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="0"/>'
            '</w:tblPr>')


def tabla(cab, filas, anchos, fondos=None, negritas=None, monos=None):
    xml = [_abrir_tabla(anchos)]
    xml.append("<w:tr><w:trPr><w:tblHeader/></w:trPr>" + "".join(
        celda(c, anchos[i], FONDO_CAB, b=True, color=AZUL)
        for i, c in enumerate(cab)) + "</w:tr>")
    for k, fila in enumerate(filas):
        f = (fondos or {}).get(k, "FFFFFF")
        nb = (negritas or {}).get(k, set())
        mo = monos or set()
        xml.append("<w:tr>" + "".join(
            celda(v, anchos[i], f, b=(i in nb),
                  color=AZUL if i in nb else TINTA, mono=(i in mo))
            for i, v in enumerate(fila)) + "</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + parrafo(run("", 8), despues=0)


def enlace(texto, rid, sz=17):
    """Hipervinculo. El destino viaja en las relaciones, no en el cuerpo."""
    return (f'<w:hyperlink r:id="{rid}"><w:r><w:rPr>{F}'
            f'<w:color w:val="{AZUL}"/><w:u w:val="single"/>'
            f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(texto)}</w:t>'
            '</w:r></w:hyperlink>')


def tabla_enlaces(cab, filas, anchos, rid0=1):
    """filas: (col1, col2, texto del enlace, url). Devuelve (xml, relaciones)."""
    xml = [_abrir_tabla(anchos)]
    xml.append("<w:tr><w:trPr><w:tblHeader/></w:trPr>" + "".join(
        celda(c, anchos[i], FONDO_CAB, b=True, color=AZUL)
        for i, c in enumerate(cab)) + "</w:tr>")
    rels = {}
    for k, (a, b, txt, url) in enumerate(filas):
        rid = f"rIdU{rid0 + k}"
        rels[rid] = url
        cel = (f'<w:tc><w:tcPr><w:tcW w:w="{anchos[2]}" w:type="dxa"/>'
               '<w:shd w:val="clear" w:color="auto" w:fill="FFFFFF"/>'
               '<w:tcMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
               '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/>'
               '</w:tcMar><w:vAlign w:val="center"/></w:tcPr>'
               '<w:p><w:pPr><w:spacing w:before="20" w:after="20" w:line="240" '
               'w:lineRule="auto"/></w:pPr>' + enlace(txt, rid) + '</w:p></w:tc>')
        xml.append("<w:tr>" + celda(a, anchos[0], "FFFFFF", b=True, color=AZUL)
                   + celda(b, anchos[1], mono=True) + cel + "</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + parrafo(run("", 8), despues=0), rels


def imagen(rid, an_px, al_px, alt=""):
    """Inserta una imagen. Word mide en EMU: 914400 por pulgada, a 96 ppp."""
    cx, cy = int(an_px * 914400 / 96), int(al_px * 914400 / 96)
    n = rid[3:] if rid.startswith("rId") else "1"
    return (
        '<w:p><w:pPr><w:spacing w:before="60" w:after="160"/>'
        '<w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{n}" name="Grafica {rid}" descr="{escape(alt)}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/>'
        '</wp:cNvGraphicFramePr><a:graphic><a:graphicData '
        'uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="{rid}.png"/>'
        '<pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
        f'<a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch>'
        '</pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline>'
        '</w:drawing></w:r></w:p>')


def pie_grafica(t):
    return parrafo(run(t, 16, GRIS, i=True), despues=200, alin="center")


def firmas(bloques):
    """Espacios de firma: linea, nombre, rol, organizacion y fecha."""
    x = []
    for fila in bloques:
        fila = [f for f in fila if f[0]]     # una fila impar no deja hueco
        if not fila:
            continue
        ancho = 9800 // len(fila)
        celdas = []
        for nombre, rol, org in fila:
            celdas.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{ancho}" w:type="dxa"/>'
                '<w:tcMar><w:top w:w="300" w:type="dxa"/>'
                '<w:left w:w="120" w:type="dxa"/>'
                '<w:bottom w:w="120" w:type="dxa"/>'
                '<w:right w:w="120" w:type="dxa"/></w:tcMar></w:tcPr>'
                '<w:p><w:pPr><w:spacing w:before="700" w:after="0"/><w:pBdr>'
                f'<w:bottom w:val="single" w:sz="6" w:space="2" w:color="{TINTA}"/>'
                '</w:pBdr></w:pPr></w:p>'
                + parrafo(run(nombre, 19, TINTA, b=True), antes=80, despues=20)
                + parrafo(run(rol, 17, GRIS), despues=10)
                + parrafo(run(org, 17, GRIS), despues=0)
                + parrafo(run("Fecha: ____________________", 16, GRIS),
                          antes=100, despues=0)
                + '</w:tc>')
        x.append("<w:tr>" + "".join(celdas) + "</w:tr>")
    return (_abrir_tabla([9800]).replace(_BORDES, "") + "".join(x) + "</w:tbl>"
            + parrafo(run("", 8), despues=0))


def salto():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')

SECCION = ('<w:sectPr>'
           '<w:headerReference w:type="default" r:id="rIdHdr"/>'
           '<w:headerReference w:type="first" r:id="rIdHdr1"/>'
           '<w:footerReference w:type="first" r:id="rIdFtr"/>'
           '<w:pgSz w:w="12240" w:h="15840"/>'
           '<w:pgMar w:top="901" w:right="1077" w:bottom="901" w:left="1077" '
           'w:header="708" w:footer="708" w:gutter="0"/>'
           '<w:pgNumType w:start="1"/><w:cols w:space="720"/>'
           '<w:titlePg/></w:sectPr>')


def _encabezado(texto):
    """Cabecera con el logo de Quind y el rotulo a la derecha.

    El logo va a 495300 x 314325 EMU, la misma medida del acta de referencia.
    """
    logo = (f'<w:r><w:rPr>{F}<w:noProof/></w:rPr><w:drawing>'
            '<wp:inline distT="0" distB="0" distL="0" distR="0">'
            '<wp:extent cx="495300" cy="314325"/>'
            '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            '<wp:docPr id="90" name="Logo Quind"/><wp:cNvGraphicFramePr/>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/'
            'drawingml/2006/picture"><pic:pic><pic:nvPicPr>'
            '<pic:cNvPr id="0" name="quind.png"/>'
            '<pic:cNvPicPr preferRelativeResize="0"/></pic:nvPicPr>'
            '<pic:blipFill><a:blip r:embed="rIdLogo"/><a:srcRect/>'
            '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
            '<a:ext cx="495300" cy="314325"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:ln/></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline>'
            '</w:drawing></w:r>')
    rot = (f'<w:r><w:rPr>{F}<w:color w:val="{GRIS}"/><w:sz w:val="17"/>'
           f'<w:szCs w:val="17"/></w:rPr><w:tab/>'
           f'<w:t xml:space="preserve">{escape(texto)}</w:t></w:r>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:hdr {NS}><w:p><w:pPr>'
            '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" '
            'w:color="CFD8DC"/></w:pBdr>'
            '<w:tabs><w:tab w:val="right" w:pos="9360"/></w:tabs>'
            '<w:spacing w:after="0"/></w:pPr>' + logo + rot + '</w:p></w:hdr>')


_VACIO = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          f'<w:hdr {NS}><w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p></w:hdr>')
_PIE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:ftr {NS}><w:p><w:pPr><w:spacing w:after="0"/></w:pPr></w:p></w:ftr>')

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Calibri" w:eastAsia="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
<w:sz w:val="20"/><w:szCs w:val="20"/><w:lang w:val="es-CO"/>
</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>
<w:spacing w:after="140" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
<w:name w:val="Normal"/><w:qFormat/></w:style>
<w:style w:type="table" w:default="1" w:styleId="TableNormal">
<w:name w:val="Normal Table"/><w:uiPriority w:val="99"/><w:semiHidden/>
<w:unhideWhenUsed/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar>
<w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>
<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/>
</w:tblCellMar></w:tblPr></w:style>
</w:styles>"""


def guardar(cuerpo, destino, titulo="Acta de entrega de flujos", cabecera=None,
            imagenes=None, enlaces=None):
    """Escribe un .docx minimo y valido, con cabecera, logo, graficas y enlaces."""
    imagenes = imagenes or {}
    enlaces = enlaces or {}
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           f'<w:document {NS}><w:body>{cuerpo}{SECCION}</w:body></w:document>')

    rel = "".join(
        f'<Relationship Id="{k}" Type="http://schemas.openxmlformats.org/'
        f'officeDocument/2006/relationships/image" Target="media/{k}.png"/>'
        for k in imagenes)
    rel += "".join(
        f'<Relationship Id="{k}" Type="http://schemas.openxmlformats.org/'
        f'officeDocument/2006/relationships/hyperlink" '
        f'Target="{escape(v, {chr(34): "&quot;"})}" TargetMode="External"/>'
        for k, v in enlaces.items())
    rel += ('<Relationship Id="rIdHdr" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/header" Target="header1.xml"/>'
            '<Relationship Id="rIdHdr1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/header" Target="header2.xml"/>'
            '<Relationship Id="rIdFtr" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/footer" Target="footer1.xml"/>')

    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="png" ContentType="image/png"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
          '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
          '<Override PartName="/word/header2.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
          '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
          '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
          '</Types>')
    raiz = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/'
            '2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '</Relationships>')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/'
            '2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f'<dc:title>{escape(titulo)}</dc:title>'
            '<dc:creator>Equipo VMQA - Quind S.A.S.</dc:creator></cp:coreProperties>')

    partes = {
        "[Content_Types].xml": ct,
        "_rels/.rels": raiz,
        "word/document.xml": doc,
        "word/_rels/document.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdSty" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            + rel + '</Relationships>',
        "word/styles.xml": _STYLES,
        "word/header1.xml": _encabezado(cabecera or titulo),
        "word/header2.xml": _VACIO,
        "word/footer1.xml": _PIE,
        "word/_rels/header1.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rIdLogo" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/image" Target="media/quind.png"/>'
            '</Relationships>',
        "docProps/core.xml": core,
    }
    os.makedirs(os.path.dirname(os.path.abspath(destino)) or ".", exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for n, c in partes.items():
            z.writestr(n, c)
        for rid, ruta in imagenes.items():
            z.write(ruta, f"word/media/{rid}.png")
        z.write(LOGO, "word/media/quind.png")
    return destino


# ── comparacion cara a cara ──────────────────────────────────────────────────
# Los bloques que enfrentan el valor de una plataforma con el de la otra. El
# mismo lenguaje del reporte grafico: Stratio en azul, Fabric en ambar, y las
# comillas resaltadas para que se vea de un vistazo donde esta la diferencia.

ORIGEN = "3D5A98"     # Stratio
DESTINO = "A86A00"    # Fabric
FONDO_VAL = "F7F9FB"


MARCAS = '"\ufffd'          # comillas y el caracter de reemplazo


def resaltar(valor, color=TINTA, sz=18):
    """El valor en monoespaciado, con lo que hace la diferencia resaltado.

    Se marcan las comillas y el caracter de reemplazo U+FFFD, que son las dos
    huellas que dejan los dos defectos de lectura vistos en el origen.
    """
    partes, buf = [], ""
    for ch in str(valor):
        if ch in MARCAS:
            if buf:
                partes.append((buf, False))
                buf = ""
            if partes and partes[-1][1]:
                partes[-1] = (partes[-1][0] + ch, True)
            else:
                partes.append((ch, True))
        else:
            buf += ch
    if buf:
        partes.append((buf, False))
    out = []
    for txt, marca in partes:
        shd = ('<w:shd w:val="clear" w:color="auto" w:fill="FFE0A3"/>'
               if marca else "")
        out.append(
            f'<w:r><w:rPr>{MONO}{"<w:b/><w:bCs/>" if marca else ""}{shd}'
            f'<w:color w:val="{AMBAR if marca else color}"/>'
            f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(txt)}</w:t></w:r>')
    return "".join(out)


def _celda_xml(parrafos, ancho, fondo="FFFFFF", barra=None):
    """Celda con parrafos ya construidos; barra pinta el filete izquierdo."""
    bd = ('<w:tcBorders><w:left w:val="single" w:sz="18" w:space="0" '
          f'w:color="{barra}"/></w:tcBorders>') if barra else ""
    return (f'<w:tc><w:tcPr><w:tcW w:w="{ancho}" w:type="dxa"/>{bd}'
            f'<w:shd w:val="clear" w:color="auto" w:fill="{fondo}"/>'
            '<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/>'
            '</w:tcMar></w:tcPr>' + "".join(parrafos) + "</w:tc>")


def cara_a_cara(izq, der, ancho=4900):
    """Enfrenta el valor de Stratio con el de Fabric. izq/der: (valor, pie)."""
    def lado(quien, color, valor, pie):
        ps = [parrafo(run(quien, 17, color, b=True), despues=60, linea=240),
              parrafo(resaltar(valor), despues=60, linea=260)]
        if pie:
            ps.append(parrafo(run(pie, 16, GRIS), despues=0, linea=240))
        return _celda_xml(ps, ancho, FONDO_VAL, barra=color)
    return (_abrir_tabla([ancho, ancho]) + "<w:tr>"
            + lado("STRATIO · origen", ORIGEN, izq[0], izq[1])
            + lado("FABRIC · destino", DESTINO, der[0], der[1])
            + "</w:tr></w:tbl>" + parrafo(run("", 8), despues=0))


def pasos(titulo, items, ancho=9800):
    """La comprobacion, paso a paso. items: (afirmacion, detalle)."""
    num = 560
    txt = ancho - num
    cab = (f'<w:tc><w:tcPr><w:tcW w:w="{ancho}" w:type="dxa"/>'
           '<w:gridSpan w:val="2"/>'
           f'<w:shd w:val="clear" w:color="auto" w:fill="{FONDO_CAB}"/>'
           '<w:tcMar><w:top w:w="60" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
           '<w:bottom w:w="60" w:type="dxa"/><w:right w:w="120" w:type="dxa"/>'
           '</w:tcMar></w:tcPr>'
           + parrafo(run(titulo, 18, AZUL, b=True), despues=0, linea=240)
           + '</w:tc>')
    xml = [_abrir_tabla([num, txt]), "<w:tr>" + cab + "</w:tr>"]
    for k, (afirma, detalle) in enumerate(items, 1):
        fin = k == len(items)
        xml.append("<w:tr>" + _celda_xml(
            [parrafo(run(k, 20, "FFFFFF" if fin else AZUL, b=True),
                     despues=0, linea=240, alin="center")],
            num, VERDE if fin else FONDO_CAB)
            + _celda_xml(
            [parrafo(run(afirma, 18, VERDE if fin else TINTA, b=fin),
                     despues=40, linea=240),
             parrafo(run(detalle, 16, GRIS), despues=0, linea=240)],
            txt) + "</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + parrafo(run("", 8), despues=0)


def hechos(items, ancho=9800):
    """Cifras de cierre, una junto a otra. items: (rotulo, valor, color)."""
    an = ancho // len(items)
    anchos = [an] * len(items)
    anchos[-1] = ancho - an * (len(items) - 1)
    return (_abrir_tabla(anchos) + "<w:tr>" + "".join(
        _celda_xml([parrafo(run(r, 15, GRIS), despues=40, linea=240),
                    parrafo(run(v, 20, c, b=True), despues=0, linea=240)],
                   anchos[i])
        for i, (r, v, c) in enumerate(items))
        + "</w:tr></w:tbl>" + parrafo(run("", 8), despues=0))


def tabla_valores(ejemplos, ancho=9800):
    """Los demas valores, enfrentados en tabla. Las comillas van resaltadas."""
    anchos = [1500, (ancho - 2400) // 2, ancho - 2400 - (ancho - 2400) // 2, 900]
    xml = [_abrir_tabla(anchos)]
    xml.append("<w:tr><w:trPr><w:tblHeader/></w:trPr>" + "".join(
        celda(c, anchos[i], FONDO_CAB, b=True, color=AZUL, sz=17)
        for i, c in enumerate(
            ["Columna", "Valor en Stratio", "Valor en Fabric", "Celdas"]))
        + "</w:tr>")
    for e in ejemplos:
        xml.append(
            "<w:tr>"
            + celda(e["columna"], anchos[0], b=True, color=AZUL, sz=17)
            + _celda_xml([parrafo(resaltar(e["origen"], sz=17), despues=0,
                                  linea=240)], anchos[1])
            + _celda_xml([parrafo(resaltar(e["destino"], sz=17), despues=0,
                                  linea=240)], anchos[2])
            + celda(e["celdas"], anchos[3], sz=17, alin="center")
            + "</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + parrafo(run("", 8), despues=0)
