"""Acta de entrega v4: JSON del acta -> .docx. Se genera SOLO desde un lote armado (lotes/<N>/) con las tres
compuertas aprobadas y por el responsable del acta. Queda LOCAL (no se publica).

Estructura: la de las actas 6-10 (portada, control de versiones, participantes, 9 puntos, firmas, anexo) con la
presentacion de las actas 2-3 en las diferencias (valor de cada lado lado a lado, cifras de cierre).
Estilo y graficas: los modulos estilo.py y graficas.py del generador de actas existente (no se duplican).

  python -m pc acta generar --lote N [--version 1.0]
"""
import datetime
import json
import os
import sys

from . import lote as T
from . import lote_final as LF
from .acceso import fabric, onelake as ol
from .config import RAIZ

ACTAS = os.path.join(RAIZ, "pc", "docx")   # estilo.py y graficas.py de las actas entregadas (copia en el repo)
CFG = json.load(open(os.path.join(RAIZ, "config", "acta.json"), encoding="utf8"))
GRUPOS = (("ingesta", "Ingesta"), ("analitica", "Analítica"), ("orquestador", "Orquestadores"))


def _es():
    if ACTAS not in sys.path:
        sys.path.insert(0, ACTAS)
    import estilo
    import graficas
    return estilo, graficas


def _n(v):
    return f"{v:,}".replace(",", ".") if isinstance(v, int) else ("—" if v is None else str(v))


def _dur(s):
    if not s:
        return "—"
    s = int(s)
    return f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def datos(lote):
    """El acta como datos: todo sale de los expedientes del lote y de los JSON v4 de cada flujo y tabla."""
    d = LF.leer(lote, "lote.json")
    comp = LF.leer(lote, "revision/compuertas.json", {}) or {}
    res = LF.leer(lote, "revision/resumen.json", {}) or {}
    flujos = []
    for e in d["expedientes"]:
        t, n = e["trabajo"], e["flujo"]
        cf = T.leer(t, f"v4/flujos/{n}.json") or {}
        f = T.flujo(t, n) or {}
        pr = bool((T.leer(t, "lote.json") or {}).get("pruebas"))
        from .reportes import v4
        v = cf["encabezado"]["version"]
        tablas = []
        for o in f.get("objetos", []):
            co = T.leer(t, f"v4/cotejos/{o['clave']}.json") or {}
            n2 = co.get("nivel_2") or {}
            ec = co.get("estado_controles") or {}

            def fam(p):
                xs = [x for c, x in ec.items() if c.startswith(p) and x["rol"] == "decide"]
                ok = sum(1 for x in xs if x["resultado"] in ("CUMPLE", "JUSTIFICADO"))
                return f"{ok}/{len(xs)}" if xs else "—"
            tablas.append({
                "clave": o["clave"], "fabric": (o.get("fabric") or {}).get("ruta"), "stratio": (o.get("stratio") or {}).get("ruta"),
                "capa": (cf.get("roles") or {}).get("capa") or ((o.get("fabric") or {}).get("ruta") or "").split(".")[0],
                "estado": co.get("encabezado", {}).get("estado"),
                "filas_stratio": (n2.get("filas") or {}).get("stratio"), "filas_fabric": (n2.get("filas") or {}).get("fabric"),
                "pct": (n2.get("filas") or {}).get("pct"),
                "columnas": len((n2.get("esquema") or {}).get("solo_en_stratio") or []) == 0 and
                            f"{(n2.get('hash') or {}).get('columnas_hash_igual', 0)} de {(n2.get('hash') or {}).get('columnas_hash_igual', 0) + len((n2.get('hash') or {}).get('columnas_hash_distinto') or [])}",
                "huella": "idéntica" if (n2.get("hash") or {}).get("igual") else "distinta",
                "VG": fam("VG"), "ID": fam("ID"), "CP": fam("CP"),
                "diferencias": [x for x in co.get("diferencias") or [] if x["decision"] in ("JUSTIFICADA", "INFORMATIVA", "A_VERIFICAR")],
                "anexo": [("Medición Stratio", v4.ruta_ol("medicion", o["clave"], v, "STRATIO", pr)),
                          ("Medición Fabric", v4.ruta_ol("medicion", o["clave"], v, "FABRIC", pr)),
                          ("Cotejo Stratio ↔ Fabric", v4.ruta_ol("cotejo", o["clave"], v, pruebas=pr))]})
        ej = cf.get("ejecucion") or {}
        flujos.append({"flujo": n, "stratio": f.get("nombre_stratio"), "fl": f.get("fl"), "grupo": f.get("grupo"),
                       "version": v, "estado": cf["encabezado"]["estado"], "verificacion": cf.get("verificacion"),
                       "ejecucion": {"estado": ej.get("estado"), "inicio": ej.get("inicio_utc"), "duracion_s": ej.get("duracion_s"),
                                     "dependencias": (cf.get("dependencias") or {}).get("declaradas") or []},
                       "tablas": tablas, "anexo_flujo": ("Cotejo de flujo", v4.ruta_ol("cotejo_flujo", n, v, pruebas=pr))})
    grupos = {g for f in flujos for g in [("analitica" if f["grupo"] == "orquestador" else f["grupo"])]}
    firm = [CFG["firmantes"][g] for g in ("ingesta", "analitica") if g in grupos] + [CFG["firmantes"]["qa"]]
    return {"formato": "pc.v4/acta@1", "lote": str(lote), "generado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "huella_resumen": res.get("huella"), "compuertas": comp, "responsable": d.get("responsable_acta"),
            "flujos": flujos, "firmantes": firm}


def verificar_enlaces(A):
    """Cada documento del anexo debe existir en OneLake (HEAD). Si falta uno, el acta no se emite."""
    rotos = []
    for f in A["flujos"]:
        for _t, ruta in [f["anexo_flujo"]] + [x for t in f["tablas"] for x in t["anexo"]]:
            if not ol.head(ruta):
                rotos.append(ruta)
    return rotos


def generar(lote, version="1.0", destino=None, autorizado=False):
    from .compuerta import revision as R
    if not autorizado:
        R.autorizar_acta(lote)
    A = datos(lote)
    rotos = verificar_enlaces(A)
    if rotos:
        raise RuntimeError(f"{len(rotos)} enlace(s) del anexo no existen en OneLake; el acta no se emite: {rotos[:5]}")
    E, G = _es()
    d_img = os.path.join(LF.dir_lote(lote), "acta", "graficas")
    os.makedirs(d_img, exist_ok=True)
    cuerpo, imgs, rels, pie, rid = [], {}, {}, [0], [0]

    def add(x):
        cuerpo.append(x)

    def grafica(ruta, texto):
        if not ruta:
            return
        pie[0] += 1
        k = f"rIdG{pie[0]}"
        imgs[k] = ruta
        add(E.imagen(k, 640, G.alto(ruta), texto))
        add(E.pie_grafica(f"Gráfica {pie[0]}. {texto}"))

    hoy = datetime.date.today()
    nombre_lote = f"Lote {lote}"
    # portada
    add(E.parrafo(E.run(CFG["titulo"], 22, E.GRIS), despues=200))
    add(E.parrafo(E.run("ACTA DE ENTREGA DE FLUJOS", 40, E.AZUL, b=True), despues=100))
    tot_t = sum(len(f["tablas"]) for f in A["flujos"])
    add(E.parrafo(E.run(f"{nombre_lote} · {len(A['flujos'])} flujo(s) · {tot_t} tabla(s) cotejada(s) · {hoy.isoformat()}", 22, E.TINTA), despues=300))
    add(E.h2("Control de versiones"))
    add(E.tabla(["Versión", "Fecha", "Descripción"], [[version, hoy.isoformat(), f"Acta del {nombre_lote} · resumen aprobado con huella {A['huella_resumen']}"]], [1600, 1800, 6400]))
    add(E.h2("Participantes"))
    part = [list(p) for p in CFG["participantes_fijos"]] + [[x["nombre"], x["org"], x["rol"]] for x in A["firmantes"] if x["nombre"] != "Equipo VMQA"]
    add(E.tabla(["Nombre", "Organización", "Rol"], part, [3600, 2600, 3600]))
    # 1 objeto
    add(E.h1("1. Objeto del acta"))
    add(E.parrafo(E.run("Se entregan para su aprobación los flujos listados, validados en QA contra Stratio como fuente de verdad, con el criterio de cada grupo:", 20)))
    filas = []
    for g, t in GRUPOS:
        fs = [f for f in A["flujos"] if f["grupo"] == g]
        if fs:
            filas.append([t, str(len(fs)), str(sum(len(f["tablas"]) for f in fs)), CFG["criterio"][g]])
    add(E.tabla(["Grupo", "Flujos", "Tablas", "Criterio de aprobación"], filas, [1700, 1000, 1000, 6100]))
    # 2 resumen
    add(E.h1("2. Resumen de resultados"))
    est = {}
    for f in A["flujos"]:
        est[f["estado"]] = est.get(f["estado"], 0) + 1
    add(E.tabla(["Indicador", "Resultado"], [["Flujos entregados", str(len(A["flujos"]))], ["Tablas cotejadas", str(tot_t)]] +
                [[k.replace("_", " ").capitalize(), str(v)] for k, v in sorted(est.items())] +
                [["Ejecución en QA", f"{sum(1 for f in A['flujos'] if f['ejecucion']['estado'] == 'Completed')} de {len(A['flujos'])} en Completed"]],
                [4900, 4900]))
    # 3 flujos
    add(E.h1("3. Flujos entregados"))
    for i, (g, t) in enumerate(GRUPOS, 1):
        fs = [f for f in A["flujos"] if f["grupo"] == g]
        if not fs:
            continue
        add(E.h2(f"3.{i}  {t} · {len(fs)} flujo(s)"))
        add(E.tabla(["Flujo en Fabric", "Flujo en Stratio", "Código", "Capa", "Tablas", "Estado"],
                    [[f["flujo"], f["stratio"] or "por definir", f["fl"] or "sin código FL asignado",
                      ", ".join(sorted({x["capa"] for x in f["tablas"] if x["capa"]})) or "—",
                      ", ".join(x["fabric"] or x["clave"] for x in f["tablas"]) or "—",
                      f["estado"].replace("_", " ").lower()] for f in fs], [2000, 2000, 1200, 900, 2400, 1300]))
    # 4 ejecucion
    add(E.h1("4. Ejecución de los flujos"))
    add(E.tabla(["Flujo", "Estado", "Inicio (UTC)", "Duración", "Dependencias"],
                [[f["flujo"], f["ejecucion"]["estado"] or "—", (f["ejecucion"]["inicio"] or "—")[:19], _dur(f["ejecucion"]["duracion_s"]),
                  ", ".join(f["ejecucion"]["dependencias"]) or "sin dependencias"] for f in A["flujos"]], [2600, 1300, 2000, 1400, 2500]))
    grafica(G.duracion([{"flujo": f["flujo"], "segundos": f["ejecucion"]["duracion_s"]} for f in A["flujos"]], os.path.join(d_img, "duracion.png")),
            "Duración de la corrida de cada flujo. La barra más larga es la corrida que más tardó.")
    # 5 cotejo
    add(E.h1("5. Cotejo de tablas completas por flujo"))
    tb = [(f, x) for f in A["flujos"] for x in f["tablas"]]
    add(E.tabla(["Flujo · tabla", "Capa", "Filas Stratio", "Filas Fabric", "Fabric / Stratio", "Columnas idénticas", "Huella"],
                [[f"{f['flujo']} · {x['clave']}", x["capa"] or "—", _n(x["filas_stratio"]), _n(x["filas_fabric"]),
                  f"{x['pct']:.4f} %".replace(".", ",") if x["pct"] is not None else "—", str(x["columnas"]), x["huella"]] for f, x in tb],
                [2700, 800, 1200, 1200, 1300, 1400, 1200]))
    pares = [(x["clave"][:30], x["filas_stratio"] or 0, x["filas_fabric"] or 0) for _f, x in tb if x["filas_stratio"] is not None]
    if pares:
        grafica(G.cotejo_conteo(pares, os.path.join(d_img, "conteo.png"), titulo="Filas en Stratio y en Fabric por tabla"),
                "Filas de cada tabla en Stratio (azul) y en Fabric (ámbar). Dos barras iguales son la misma cantidad de filas.")
    # 6 controles
    add(E.h1("6. Controles de calidad"))
    add(E.parrafo(E.run("Cumple sobre evaluados, solo de los controles que deciden en el grupo de cada flujo (los informativos se miden y se reportan en los cotejos).", 18, E.GRIS)))
    add(E.tabla(["Tabla", "Grupo", "VG", "ID", "CP"], [[x["clave"], f["grupo"], x["VG"], x["ID"], x["CP"]] for f, x in tb], [3800, 1500, 1500, 1500, 1500]))
    # 7 diferencias
    add(E.h1("7. Diferencias y su justificación"))
    k = 0
    for f, x in tb:
        if not x["diferencias"]:
            continue
        k += 1
        add(E.h2(f"7.{k}  {f['flujo']} · {x['clave']}"))
        for dd in x["diferencias"]:
            add(E.parrafo([E.run(f"{dd['id']} · {dd['control']} · ", 18, E.AZUL, b=True), E.run(dd["descripcion"], 18)], despues=80))
            ej = (dd.get("ejemplos") or [None])[0]
            if ej and ("stratio" in ej or "fabric" in ej):
                add(E.cara_a_cara((str(ej.get("stratio")), json.dumps(ej.get("fila"), ensure_ascii=False)[:80] if ej.get("fila") else ""),
                                  (str(ej.get("fabric")), "")))
            add(E.hechos([("Filas afectadas", _n(dd.get("filas_afectadas")), E.TINTA),
                          ("Decisión", dd["decision"].replace("_", " ").lower(), E.AZUL),
                          ("Causa medida", "sí" if dd.get("causa_medida") else "no", E.TINTA)]))
            if dd.get("causa"):
                add(E.parrafo([E.run("Justificación: ", 18, E.AZUL, b=True), E.run(dd["causa"], 18)], despues=160))
    if not k:
        add(E.parrafo(E.run("Las tablas entregadas no presentan diferencias contra Stratio.", 20)))
    # 8 declaracion
    add(E.h1("8. Declaración y aprobación"))
    add(E.parrafo(E.run("El equipo de pruebas declara que los flujos listados fueron ejecutados y cotejados contra Stratio con el criterio de su grupo, y que cada diferencia lleva su causa medida o su verificación.", 20)))
    filas_c = [[c.replace("_", " ").capitalize(), (A["compuertas"].get(c) or {}).get("decision", "—"), (A["compuertas"].get(c) or {}).get("persona", "—"),
                ((A["compuertas"].get(c) or {}).get("utc") or "—")[:16]] for c in ("revision_qa", "revision_comfandi", "aprobacion")]
    add(E.tabla(["Compuerta", "Decisión", "Persona", "Fecha (UTC)"], filas_c, [2600, 2000, 3000, 2200]))
    fir = [(x["nombre"], x["rol"], x["org"]) for x in A["firmantes"]]
    add(E.firmas([fir[i:i + 2] for i in range(0, len(fir), 2)]))
    # 9 anexo
    add(E.h1("9. Anexo de evidencia"))
    fil = []
    for f in A["flujos"]:
        fil.append([f["flujo"], f["anexo_flujo"][0], f["anexo_flujo"][1].rsplit("/", 1)[-1], fabric.portal_archivo(f["anexo_flujo"][1])])
        for x in f["tablas"]:
            for t, ruta in x["anexo"]:
                fil.append([f"{f['flujo']} · {x['clave']}", t, ruta.rsplit("/", 1)[-1], fabric.portal_archivo(ruta)])
    xml, r2 = E.tabla_enlaces(["Flujo · tabla", "Documento", "Archivo en el lakehouse"], [(a, b, c, u) for a, b, c, u in fil], [3000, 2400, 4400])
    add(xml)
    rels.update(r2)
    destino = destino or os.path.join(LF.dir_lote(lote), "acta", f"Acta_Entrega_Flujos_Lote{lote}_{hoy.isoformat()}_v{version}.docx")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    E.guardar("".join(cuerpo), destino, imagenes=imgs, enlaces=rels)
    A["anexo_enlaces"] = len(fil)
    json.dump(A, open(os.path.join(os.path.dirname(destino), f"acta_{lote}_v{version}.json"), "w"), indent=1, ensure_ascii=False, default=str)
    return destino, A
