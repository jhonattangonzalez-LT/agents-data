"""Lector de los reportes v4 en FORMATO 2 (pc/reportes/formato2.py, mejora M-005 del 2026-10-06) para el acta normalizada.

No mide nada ni usa la red: LEE los JSON locales de un trabajo del pipeline QA v2 y devuelve tablas y flujos con el
esquema que consume generar_acta_normalizada.py (el mismo de datos_normalizados.py y datos_lote11_v1_1.py).

  cotejo de tabla  (pc.v4/cotejo@2):  encabezado · controles.resumen · controles.detalle · justificaciones · metricas
  cotejo de flujo  (pc.v4/cotejo_flujo@2): encabezado · ejecucion · analitica | ingesta · orquestacion · comprobaciones
                                           · tablas · semaforo

El lector de datos_lote11_v1_1.py lee el formato 1 (nivel_0/1/2, estado_controles, diferencias): no sirve para estos.
Uso: lote 6 v2.2 (datos_lote6_v2_2.py).
"""
import json
import os
import re

import capas as CAPAS

ESTADO_TXT = {"APROBADO": "Aprobado", "APROBADO_CON_JUSTIFICACION": "Aprobado con justificación",
              "APROBADO_CON_VERIFICACION": "Aprobado con verificación de QA",
              "REVISAR": "Revisar", "PENDIENTE": "Pendiente"}


def J(p):
    with open(p, encoding="utf8") as f:
        return json.load(f)


def n(v):
    return f"{int(v):,}".replace(",", ".")


# ── datos personales: se enmascaran en lo que el acta muestra ────────────────────
# · BP de persona (serie 001xxxxxxx) → «0010…»
# · extractos de texto libre de registros de estudiantes (observaciones, descripciones) entre «…»
TEXTO_LIBRE_PERSONAL = ("novar_saenlinea_comfandi_reporte_468_observador", "novar_siga_comfandi_reporte_432_estudiantes_retiro_registrado")


def enmascarar(s, clave=None):
    if s is None:
        return s
    s = re.sub(r"\b(001\d)\d{6}\b", r"\1…", str(s))
    if clave in TEXTO_LIBRE_PERSONAL:
        s = re.sub(r"«[^»]*»", "«texto del registro omitido: dato personal»", s)
    return s


def capa_de(ruta_fabric, capa_flujo=None):
    """Capa medallón medida (capas.py): por la ruta de destino o, en Postgres/SFTP, por la copia que la escribe.
    Ya no se toma la del flujo por defecto: si no se puede fijar, None (el generador lo pregunta). Devuelve (capa, motivo)."""
    return CAPAS.capa_tabla(ruta_fabric)


def resumir(t, n=240):
    """La causa final en una o dos frases (punto 7 compacto): sin la cola «Decisión …», sin rutas ni horas largas."""
    t = re.sub(r"\s*Decisi[oó]n (JUSTIFICADA|INFORMATIVA)[^.]*\.?\s*$", "", str(t or "")).strip()
    t = re.sub(r"\s*\((?:[^()]*\d{4}-\d{2}-\d{2}[^()]*)\)", "", t)          # paréntesis con fechas/horas
    frases, out = re.split(r"(?<=[.;])\s+", t), ""
    for f in frases:
        if len(out) + len(f) > n and out:
            break
        out = (out + " " + f).strip()
    if len(out) > n:
        out = out[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return out


def controles(c):
    """Por familia, los controles que deciden y se evaluaron (controles.resumen): ok, justificados y total."""
    out = {}
    for fam, d in c["controles"]["resumen"].items():
        dec = {k: v["resultado"] for k, v in d.items() if v["decide"] and v["resultado"] not in ("no_aplica", "no_evaluado")}
        ok = sorted(k for k, r in dec.items() if r in ("ok", "justificado"))
        just = sorted(k for k, r in dec.items() if r == "justificado")
        otros = sorted(k for k, r in dec.items() if r not in ("ok", "justificado"))
        out[fam] = {"ok": len(ok), "total": len(dec), "justificados": just, "otros": otros,
                    "solo_ok": sum(1 for r in dec.values() if r == "ok")}
    return out


def txt_control(ct):
    t = f"{ct['ok']} de {ct['total']}"
    return t + (f" · justificados: {', '.join(ct['justificados'])}" if ct["justificados"] else "")


def pct_control(ct):
    """100 si todos los que deciden cumplen sin justificación; si no, el % que cumple sin justificación."""
    return 100.0 if ct["total"] and ct["solo_ok"] == ct["total"] else (round(100 * ct["solo_ok"] / ct["total"], 4) if ct["total"] else None)


def mejor_ejemplo(ejs):
    """El ejemplo más concreto: con valor de los dos lados y no un conteo genérico."""
    def nota(e):
        s_, f_ = str(e.get("stratio")), str(e.get("fabric"))
        return ((e.get("stratio") is not None) + (e.get("fabric") is not None)
                + (not re.search(r"\bfilas?\b|\bnulos de\b", s_ + f_)) + (s_ != f_))
    ejs = [e for e in ejs or [] if isinstance(e, dict)]
    return max(ejs, key=nota) if ejs else None


def ejemplo_real(ej):
    return bool(ej) and ej.get("stratio") is not None and ej.get("fabric") is not None


def ejemplo_txt(ej, clave=None):
    if not ej:
        return "El cotejo no trae ejemplo para esta diferencia."
    f = ej.get("fila")
    if isinstance(f, dict):
        fila = ", ".join(f"{k} {', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in f.items() if v is not None)
    else:
        fila = str(f)
    return enmascarar(f"{fila} · Stratio: {ej.get('stratio')} · Fabric: {ej.get('fabric')}", clave)


PRE_HUELLA = "Huella SHA-256 distinta por la misma causa: "


def detalle(c, clave):
    """Una fila por justificación del cotejo: cifra (que_se_encontro + filas afectadas), ejemplo, causa y quién decidió."""
    out, causas, qse = [], {}, {}
    # orden natural de los id (D1, D2, …, D10): el JSON los trae en orden de texto (D1, D10, D2)
    for j in sorted(c["justificaciones"], key=lambda j: (int(re.sub(r"\D", "", j["id"]) or 0), j["id"])):
        q = j["que_se_encontro"]
        ref = next((i for i, t in qse.items() if q == PRE_HUELLA + t), None)
        dif = f"Huella SHA-256 distinta por la misma causa que {ref}." if ref else q
        qse.setdefault(j["id"], q)
        prev = next((i for i, t in causas.items() if t == j["causa"]), None)
        cau = f"Misma causa que {prev}." if prev else j["causa"]
        causas.setdefault(j["id"], j["causa"])
        dp = j["decidido_por"]
        ej = mejor_ejemplo(j.get("ejemplos"))
        out.append({
            "id": j["id"], "control": j["control"], "nombre_control": j.get("nombre_control"), "tipo": j.get("tipo"),
            "columna": j.get("columna"), "filas_afectadas": j["filas_afectadas"], "decision": j["decision"],
            "causa_medida": j.get("causa_medida"), "decidido_por": dp["quien"], "decidido_utc": dp["utc"],
            "misma_causa_que": prev, "misma_cifra_que": ref,
            "diferencia": enmascarar(f"{dif} Filas afectadas: {n(j['filas_afectadas'])}.", clave),
            "ejemplo": ejemplo_txt(ej, clave), "ejemplo_real": ejemplo_real(ej),
            "ejemplos_json": len(j.get("ejemplos") or []),
            # la causa con la que quedó aprobada (la vigente del cotejo), resumida; el detalle queda en el cotejo enlazado
            "causa_final": j["causa"], "justificacion_corta_auto": enmascarar(resumir(j["causa"]), clave),
            "decision_txt": f"{j['decision'].capitalize()} · {dp['quien']} · {dp['utc'][:10]}",
            "justificacion": enmascarar(f"{cau} Decisión {j['decision']}: {dp['quien']}, "
                                        f"{dp['utc'][:16].replace('T', ' ')} UTC.", clave),
        })
    return out


def tabla(ruta_cotejo, enlaces, capa_flujo=None, referencia=None):
    """Una tabla del acta desde su cotejo en formato 2."""
    c = J(ruta_cotejo)
    e, m = c["encabezado"], c["metricas"]
    assert e["formato"] == "pc.v4/cotejo@2", ruta_cotejo
    clave = ruta_cotejo.rsplit("/", 1)[1][:-5]
    # un objeto con un solo lado (M-036: stratio nulo con salvedad_stratio decidida por una persona) trae stratio = None
    cs, cf = e["como_se_leyo"]["stratio"] or {}, e["como_se_leyo"]["fabric"] or {}
    mf = m.get("filas") or {"stratio": None, "fabric": cf.get("filas"), "delta": None, "pct": None}
    assert (cs.get("filas"), cf.get("filas")) == (mf["stratio"], mf["fabric"]) or not cs, clave
    ct = controles(c)
    cp3 = c["controles"]["detalle"].get("CP", {}).get("CP-03", {}).get("medicion") or {}
    hs, hf = (cp3.get("stratio") or {}).get("sha256_dataset"), (cp3.get("fabric") or {}).get("sha256_dataset")
    fab = e["objeto"]["fabric"]
    capa, capa_motivo = capa_de(fab, capa_flujo)
    c5 = c["controles"]["detalle"].get("CP", {}).get("CP-05", {})
    tipo_f = "files" if fab.startswith("Files/") else ("delta" if fab.split(".")[0] in ("silver", "gold", "bronze") else "pgfab")
    tipo_s = "pg" if cs.get("fuente") == "POSTGRES" else "hdfs"
    det = detalle(c, clave)
    quien = sorted({x["decidido_por"] for x in det})
    dec = {}
    for x in det:
        dec[x["decision"]] = dec.get(x["decision"], 0) + 1
    o = {
        "clave": clave, "capa": capa, "capa_motivo": capa_motivo,
        "cp05": {"resultado": c5.get("resultado"), "detalle": (c5.get("fabric") or {}).get("detalle"),
                 **(c5.get("aplicacion") or {})},
        "stratio_ruta": f"{tipo_s}:{e['objeto']['stratio']}",
        "fabric_ruta": f"{tipo_f}:{fab[len('Files/'):] if tipo_f == 'files' else fab}",
        "filas_s": mf["stratio"], "filas_f": mf["fabric"], "delta_filas": mf["delta"],
        "pct": mf["pct"],
        "cols": m["columnas_comparadas"], "cols_iguales": m["columnas_comparadas"] - (m["columnas_con_alguna_diferencia"] or 0),
        "cols_perfil_distinto": sorted(k for k, v in (m["por_columna"] or {}).items() if (v or {}).get("difiere_en")),
        "vg": pct_control(ct["VG"]), "id": pct_control(ct["ID"]), "cp": pct_control(ct["CP"]),
        "vg_txt": txt_control(ct["VG"]), "id_txt": txt_control(ct["ID"]), "cp_txt": txt_control(ct["CP"]),
        "controles": ct,
        "regresiones": list(m.get("regresiones") or []),
        "hash_igual": (hs == hf) if hs and hf else None, "hash_s": hs, "hash_f": hf,
        "resultado": e["estado"], "resumen_cotejo": e["resumen"], "nivel_alcanzado": e["nivel_alcanzado"],
        "diferencias": [], "detalle_diferencias": det,
        "enlaces": dict(enlaces),
        "justificacion": (f"{len(det)} diferencia" + ("s" if len(det) != 1 else "") + " registrada" + ("s" if len(det) != 1 else "")
                          + " en el cotejo, decidida" + ("s" if len(det) != 1 else "") + f" por {' y '.join(quien)}: "
                          + ", ".join(f"{v} {k}" for k, v in sorted(dec.items())) + ".") if det else
                         "Sin diferencias registradas en el cotejo.",
        "medido_s_utc": cs.get("medido_utc"), "medido_f_utc": cf.get("medido_utc"),
        "salvedad_stratio": e.get("salvedad_stratio"),
        "delta_fabric": ({"version": cf["version_delta"], "commit_utc": cf["commit_utc"]} if cf.get("version_delta") is not None else None),
        "fuente": {"formato": e["formato"], "ciclo": e["version"], "trabajo": e["trazabilidad"]["trabajo"],
                   "cotejo": ruta_cotejo.replace(os.path.expanduser("~"), "~")},
    }
    if referencia:
        o["stratio_referencia"] = referencia
    return o


def corto(run):
    return run.split("-")[0]


def ejecucion(d):
    """Bloque de ejecución desde la corrida validada del cotejo de flujo."""
    x = d["ejecucion"]["corrida_validada"]
    partes = []
    orq = d["encabezado"].get("orquestador")
    lp = x.get("lanzada_por") or "no registrada"
    m = re.match(r"orquestador (\S+) \(corrida ([0-9a-f]+)", lp)
    partes.append(f"invocado por {m[1]} (corrida {m[2]})" if m else f"corrida {corto(x['run_id'])}, lanzada por el {lp}")
    a = d.get("analitica")
    if a:
        for s in a["salidas"]:
            cm = s.get("commits_en_la_corrida_validada") or []
            if cm:
                partes.append(f"{s['tabla']} v{cm[-1]['version']}, commit {cm[-1]['utc'][11:19]} UTC")
            for w in s.get("escrita_por") or []:
                partes.append(f"Copy a Postgres {n(w['filas_copiadas'])} filas ({w['estado']})" if w.get("filas_copiadas") is not None
                              else f"Copy a Postgres ({w.get('estado')})")
    fd = (a or d.get("ingesta") or {}).get("flujos_dependientes") or {}
    dep = {"estado": fd.get("estado") or "NO_MEDIDO", "resumen": fd.get("resumen"),
           "directas": sorted({x["flujo"] for x in fd.get("directas") or []}),
           "indirectas": sorted({x["flujo"] for x in fd.get("indirectas") or []}),
           "sin_productor": fd.get("entradas_sin_productor") or [],
           "cascada": sorted({x.get("orquestador") for x in fd.get("directas") or [] if x.get("orquestador")})}
    if dep["estado"] != "MEDIDO":
        # «sin dependencias» solo cuando se midio: antes salia en 229 de 241 flujos solo porque no se habia buscado
        dep["resumen"] = "dependencias no medidas: correr `python -m pc dependencias` y volver a publicar el cotejo de flujo"
    partes.append(dep["resumen"])
    return {"estado": x["estado"], "inicio": x["inicio_utc"], "fin": x["fin_utc"], "run": corto(x["run_id"]),
            "run_id": x["run_id"], "duracion_s_json": x["duracion_s"], "lanzada_por": lp, "orquestador": orq,
            "dependencias": [], "dependencias_txt": " · ".join(partes), "falla": x.get("falla"),
            "dependencias_medidas": dep,
            "validador": d["ejecucion"]["validador"].get("resultado")}


def flujo(v4, nombre, links_flujo, lote_flujo, capa_defecto=None):
    """Un flujo del acta desde su cotejo de flujo en formato 2 y los cotejos de sus tablas."""
    d = J(f"{v4}/flujos/{nombre}.json")
    e = d["encabezado"]
    assert e["formato"] == "pc.v4/cotejo_flujo@2", nombre
    orden = [t["clave"] for t in d["tablas"]]
    assert set(orden) == set(links_flujo["tablas"]), (nombre, orden, list(links_flujo["tablas"]))
    roles = (d.get("analitica") or {}).get("roles") or {}
    ref = {o["clave"]: (o.get("stratio") or {}).get("referencia") for o in lote_flujo.get("objetos") or []}
    objs = [tabla(f"{v4}/cotejos/{k}.json", links_flujo["tablas"][k], None, ref.get(k)) for k in orden]
    for t, o in zip(d["tablas"], objs):
        assert t["estado"] == o["resultado"], (nombre, t["clave"])
    # capa del flujo = capas de las tablas que escribe (y la carpeta del zip si no las contradice); ambigua → se pregunta
    capa_f, capa_fm = CAPAS.capa_flujo([o["capa"] for o in objs], roles.get("zip"))
    if not capa_f and capa_defecto and CAPAS.valida(capa_defecto):
        capa_f, capa_fm = capa_defecto, "capa decidida en el acta anterior"
    return {
        "grupo": e["grupo"], "fabric": e["flujo"]["fabric"], "stratio": e["flujo"]["stratio"], "fl": e["flujo"]["fl"],
        "capa": capa_f, "capa_motivo": capa_fm, "ejecucion": ejecucion(d), "objetos": objs, "veredicto": e["estado"],
        "cotejo_flujo": links_flujo["flujo"],
        "comprobaciones": [{"comprobacion": c["comprobacion"], "resultado": c["resultado"],
                            "decision": (c.get("decision") or {}).get("decision"),
                            "decidido_por": ((c.get("decision") or {}).get("decidido_por") or {}).get("quien")}
                           for c in d["comprobaciones"]],
        "ciclo": {"version": e["version"], "version_anterior": e.get("version_anterior")},
        "fuente": {"formato": e["formato"], "trabajo": e["trazabilidad"]["trabajo"],
                   "flujo": f"{v4}/flujos/{nombre}.json".replace(os.path.expanduser("~"), "~")},
    }
