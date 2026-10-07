"""Formato 2 de los reportes v4 (acordado con QA el 2026-10-06): cotejo de tabla y cotejo de flujo.

Cotejo de tabla:  encabezado · controles {resumen, detalle} · justificaciones · metricas
Cotejo de flujo:  encabezado · ejecucion · analitica|ingesta · orquestacion · comprobaciones · tablas · semaforo

Reglas que este formato hace cumplir:
  · cada control muestra QUE se midio en Stratio y en Fabric, como se comparo y que se decidio;
  · un control que «cumple» con una alerta en los dos lados, o con una medicion distinta entre lados, NO pasa en
    silencio: exige una diferencia registrada (con ejemplo y explicacion) y decidida por una persona;
  · solo van los datos de la version vigente; de la anterior queda una linea en el encabezado;
  · `faltantes_*` lista lo que impide publicar: sin la informacion completa no se continua.
Aqui no se lee red ni disco: todo llega medido.
"""
from ..config import CONTROLES, criterio

RETIRADOS = {"VG-07", "VG-08", "ID-07", "ID-08"}
CAT = [c for c in CONTROLES["controles"] if c["codigo"] not in RETIRADOS]
FAMILIAS = ("VG", "ID", "CP")
PEOR = {"OK": 0, "INFORMATIVO": 0, "NO_EVALUADO": 0, "NO_APLICA": 0, "ALERTA": 1, "ERROR": 2}
# palabra del resumen -> que significa
PALABRAS = {"ok": "cumple, sin diferencias entre lados",
            "justificado": "hay diferencia, registrada y aceptada por una persona con causa medida",
            "por_verificar": "aprobable, pero QA o Comfandi debe confirmarlo",
            "pendiente": "hay diferencia registrada sin decidir",
            "advertencia": "la medicion muestra una alerta o una diferencia que nadie registro todavia",
            "falla": "no cumple (devuelto, o sin analizar)",
            "no_evaluado": "no se midio en esta version: no cuenta como cumplido",
            "no_aplica": "no se evalua en este grupo"}
BLOQUEAN = ("pendiente", "advertencia", "falla", "no_evaluado")


def _n(x):
    return f"{x:,}".replace(",", ".") if isinstance(x, int) else str(x)


def _rol(cod, grupo):
    c = criterio(cod, grupo)
    return "no_aplica" if c == "no_aplica" else ("informa" if c == "informativo" else "decide")


def _lado(m, cod):
    """Lo que ESE lado midio para el control: estado, valor, detalle, evidencia."""
    if not m:
        return {"estado": "NO_MEDIDO", "detalle": "no hay medicion de este lado"}
    for n in ("nivel_0", "nivel_1", "nivel_2"):
        x = ((m.get(n) or {}).get("pruebas") or {}).get(cod)
        if x:
            return {k: x[k] for k in ("estado", "valor", "detalle", "evidencia", "medido_en", "algoritmo") if x.get(k) is not None}
    e = ((m.get("estado_controles") or {}).get(cod) or {}).get("estado")
    return {"estado": e or "NO_EVALUADO"}


def _como_se_leyo(m, ruta, referencia=None):
    """`referencia`: el lado no se leyo hoy de la plataforma sino de una copia local anterior (se declara cual y por que)."""
    if not m:
        return {"ruta": ruta, "referencia": referencia} if referencia else None
    e, n0, n1, n2 = m.get("encabezado") or {}, m.get("nivel_0") or {}, m.get("nivel_1") or {}, m.get("nivel_2") or {}
    d = n2.get("descarga") or {}
    uc = n0.get("ultimo_commit") or {}
    out = {"ruta": ruta, "fuente": e.get("fuente"), "medido_utc": e.get("medido_utc"), "nivel_alcanzado": e.get("nivel_alcanzado"),
           "motor_nivel_2": n2.get("motor"), "archivos": d.get("archivos") or n1.get("archivos"),
           "bytes": d.get("bytes") or n1.get("bytes"), "filas": n2.get("filas") if n2.get("filas") is not None else n1.get("filas")}
    if n0.get("version_delta") is not None:
        out.update(version_delta=n0["version_delta"], commit_utc=uc.get("utc") if isinstance(uc, dict) else uc,
                   operacion_del_commit=uc.get("operacion") if isinstance(uc, dict) else None)
    if e.get("ventana_fechas"):
        out["ventana_fechas"] = e["ventana_fechas"]
    h = n2.get("hash") or {}
    if h:
        out["huella"] = {"algoritmo": h.get("algoritmo"), "alcance": h.get("alcance"), "filas_hasheadas": h.get("filas_hasheadas"),
                         "columnas_excluidas": h.get("columnas_excluidas") or []}
    if referencia:
        out["referencia"] = referencia
    return out


def _medido(cod, s, f, ms, mf, cr, cc, vg09):
    """Comparacion especifica del control (cifras de los dos lados). Devuelve (dict, lista de diferencias de medicion)."""
    v = (cc or {}).get("veredictos") or {}
    cr = cr or {}
    dist = []
    m = {}
    if cod == "CP-01":
        fl = v.get("filas") or cr.get("filas") or {}
        m = {"filas_stratio": fl.get("stratio"), "filas_fabric": fl.get("fabric"), "delta_fabric_menos_stratio": fl.get("delta"),
             "pct_fabric_sobre_stratio": fl.get("pct")}
        if fl.get("delta"):
            dist.append(f"Stratio {_n(fl.get('stratio'))} filas, Fabric {_n(fl.get('fabric'))} ({fl.get('delta'):+d})")
    elif cod == "CP-02":
        e = v.get("esquema") or cr.get("esquema") or {}
        m = {"columnas_stratio": (ms or {}).get("nivel_0", {}).get("num_columnas"), "columnas_fabric": (mf or {}).get("nivel_0", {}).get("num_columnas"),
             "solo_en_stratio": e.get("solo_en_stratio") or [], "solo_en_fabric": e.get("solo_en_fabric") or [],
             "tipos_distintos": e.get("tipos_distintos") or {}, "renombradas": e.get("renombradas_forma") or {},
             "orden_igual": e.get("orden_igual")}
        if m["solo_en_stratio"] or m["solo_en_fabric"] or m["tipos_distintos"]:
            dist.append(f"columnas solo en Stratio {m['solo_en_stratio']}, solo en Fabric {m['solo_en_fabric']}, tipos distintos {list(m['tipos_distintos'])}")
    elif cod == "CP-03":
        h = v.get("hash") or {}
        m = {"sha256_stratio": h.get("hash_dataset_stratio") or s.get("valor"), "sha256_fabric": h.get("hash_dataset_fabric") or f.get("valor"),
             "igual": h.get("igual"), "columnas_con_huella_igual": h.get("columnas_hash_igual"),
             "columnas_con_huella_distinta": h.get("columnas_hash_distinto") or [],
             "columnas_excluidas": h.get("columnas_excluidas_hash") or []}
        if h and not h.get("igual"):
            dist.append(f"huella SHA-256 distinta; {len(m['columnas_con_huella_distinta'])} columna(s) con huella distinta")
    elif cod == "CP-04":
        m = {"muestra_stratio": s.get("valor"), "muestra_fabric": f.get("valor"),
             "nota": "las 10 filas de cada lado estan en su medicion; sin orden, no se comparan fila a fila"}
    elif cod == "CP-05":
        n0 = (mf or {}).get("nivel_0") or {}
        uc = n0.get("ultimo_commit") or {}
        m = {"version_delta_fabric": n0.get("version_delta"), "ultimo_commit_fabric_utc": uc.get("utc") if isinstance(uc, dict) else uc,
             "resultado_fabric": f.get("detalle"), "stratio": "no aplica: la corrida citada es la de Fabric"}
    elif cod == "ID-01":
        m = {"filas_stratio": (s.get("evidencia") or {}).get("row_count"), "filas_fabric": (f.get("evidencia") or {}).get("row_count")}
    elif cod == "ID-02":
        m = {"duplicados_stratio": (s.get("evidencia") or {}).get("duplicados"), "duplicados_fabric": (f.get("evidencia") or {}).get("duplicados"),
             "metodo": (f.get("evidencia") or {}).get("metodo")}
        if m["duplicados_stratio"] != m["duplicados_fabric"]:
            dist.append(f"filas duplicadas: Stratio {m['duplicados_stratio']}, Fabric {m['duplicados_fabric']}")
    elif cod == "ID-03":
        a, b = (s.get("evidencia") or {}).get("columnas") or [], (f.get("evidencia") or {}).get("columnas") or []
        m = {"columnas_vacias_stratio": a, "columnas_vacias_fabric": b, "vacias_solo_en_fabric": cr.get("vacias_solo_en_fabric") or sorted(set(b) - set(a))}
        if set(a) != set(b):
            dist.append(f"columnas 100 % nulas: Stratio {a}, Fabric {b}")
    elif cod == "ID-04":
        nd = (v.get("nulos") or {}).get("columnas_con_nulos_distintos") or cr.get("nulos_distintos") or {}
        m = {"columnas_con_nulos_stratio": len((s.get("evidencia") or {}).get("pct_nulos_por_columna") or {}),
             "columnas_con_nulos_fabric": len((f.get("evidencia") or {}).get("pct_nulos_por_columna") or {}),
             "nulos_distintos_por_columna": {c: {"stratio": x.get("stratio"), "fabric": x.get("fabric")} for c, x in nd.items()}}
        if nd:
            dist.append(f"{len(nd)} columna(s) con distinto numero de nulos: " + ", ".join(
                f"{c} {_n(x.get('stratio'))}→{_n(x.get('fabric'))}" for c, x in list(nd.items())[:6]) + ("…" if len(nd) > 6 else ""))
    elif cod == "ID-05":
        a, b = (s.get("evidencia") or {}).get("candidatas") or [], (f.get("evidencia") or {}).get("candidatas") or []
        m = {"candidatas_a_llave_stratio": a, "candidatas_a_llave_fabric": b,
             "nota": "el control solo evalua llaves de UNA columna; una llave compuesta no se detecta"}
        if set(map(str, a)) != set(map(str, b)):
            dist.append(f"candidatas a llave: Stratio {a}, Fabric {b}")
    elif cod == "ID-06":
        a, b = (s.get("evidencia") or {}).get("columnas") or [], (f.get("evidencia") or {}).get("columnas") or []
        m = {"constantes_stratio": a, "constantes_fabric": b, "constantes_solo_en_fabric": cr.get("constantes_solo_en_fabric") or sorted(set(b) - set(a))}
        if set(a) != set(b):
            dist.append(f"columnas constantes: Stratio {a}, Fabric {b}")
    elif cod == "VG-09":
        r = (vg09 or {}).get("rupturas") or []
        m = {"contrato_completo": (vg09 or {}).get("completo"), "columnas_stratio": len((vg09 or {}).get("contrato_stratio") or []),
             "columnas_fabric": len((vg09 or {}).get("contrato_fabric") or []), "rupturas": r,
             "contrato_stratio": (vg09 or {}).get("contrato_stratio"), "contrato_fabric": (vg09 or {}).get("contrato_fabric")}
        if r:
            dist.append(f"{len(r)} ruptura(s) de contrato: " + ", ".join(f"{x['columna']} ({x['regla']})" for x in r[:6]))
    else:  # VG-01..06: la evidencia es la lista de columnas que incumplen en cada lado
        ev_s, ev_f = s.get("evidencia") or {}, f.get("evidencia") or {}
        a = next((x for x in ev_s.values() if isinstance(x, list)), [])
        b = next((x for x in ev_f.values() if isinstance(x, list)), [])
        m = {"columnas_que_incumplen_stratio": a, "columnas_que_incumplen_fabric": b}
        if a or b:
            dist.append(f"columnas que incumplen: Stratio {a}, Fabric {b}")
    return m, dist


def _cols(m):
    n0 = (m or {}).get("nivel_0") or {}
    return n0.get("columnas") or []


def _perfil(m):
    return ((m or {}).get("nivel_2") or {}).get("perfil") or {}


def _lado_medicion(cod, m):
    """Lo que ESE lado midio para el control, completo (no solo el estado): el insumo con el que se decide."""
    if not m:
        return None
    n1, n2 = (m.get("nivel_1") or {}), (m.get("nivel_2") or {})
    pf, cols, h = _perfil(m), _cols(m), (n2.get("hash") or {})
    filas = n2.get("filas") if n2.get("filas") is not None else n1.get("filas")
    if cod == "VG-01":
        return {"columnas": [c["nombre"] for c in cols], "en_minusculas": [c["nombre"].lower() for c in cols],
                "repetidos_sin_distinguir_mayusculas": sorted({c["nombre"].lower() for c in cols
                                                              if [x["nombre"].lower() for x in cols].count(c["nombre"].lower()) > 1})}
    if cod == "VG-02":
        mal = " ,;{}()\n\t="
        return {"columnas": [c["nombre"] for c in cols], "con_caracteres_no_validos": [c["nombre"] for c in cols if any(ch in c["nombre"] for ch in mal)]}
    if cod == "VG-03":
        return {"tipo_por_columna": {c["nombre"]: c["tipo"] for c in cols},
                "no_materializables": [c["nombre"] for c in cols if str(c["tipo"]).lower() in ("void", "interval", "null")]}
    if cod == "VG-04":
        dec = {c["nombre"]: c["tipo"] for c in cols if str(c["tipo"]).lower().startswith("decimal")}
        return {"columnas_decimales": dec, "fuera_de_rango_38": [k for k, t in dec.items() if _prec(t) > 38]}
    if cod == "VG-05":
        return {"tipo_por_columna": {c["nombre"]: c["tipo"] for c in cols},
                "anidadas": [c["nombre"] for c in cols if any(x in str(c["tipo"]).lower() for x in ("struct", "array", "map"))]}
    if cod == "VG-06":
        return {"longitud_del_nombre": {c["nombre"]: len(c["nombre"]) for c in cols}, "mayores_a_128": [c["nombre"] for c in cols if len(c["nombre"]) > 128]}
    if cod == "CP-02":
        return {"num_columnas": len(cols), "esquema": [{"posicion": c.get("orden"), "nombre": c["nombre"], "tipo": c["tipo"],
                                                      "nullable": c.get("nullable")} for c in cols],
                "huellas_esquema": (m.get("nivel_0") or {}).get("huellas_esquema")}
    if cod == "CP-01" or cod == "ID-01":
        return {"filas": filas, "fuente_del_conteo": "nivel 2, dato completo" if n2.get("filas") is not None else n1.get("fuente"),
                "archivos": (n2.get("descarga") or {}).get("archivos") or n1.get("archivos")}
    if cod == "CP-03":
        return {"sha256_dataset": h.get("hash_dataset"), "algoritmo": h.get("algoritmo"), "alcance": h.get("alcance"),
                "orden_canonico": h.get("orden_canonico"), "filas_hasheadas": h.get("filas_hasheadas"),
                "columnas_incluidas": h.get("columnas_incluidas"), "columnas_excluidas": h.get("columnas_excluidas"),
                "metodo_hash_columna": h.get("metodo_hash_columna"), "hash_por_columna": h.get("hash_por_columna"),
                "hash_conjunto_columnas": h.get("hash_conjunto_columnas")}
    if cod == "CP-04":
        mu = n2.get("muestra") or {}
        return {"limite": mu.get("limite"), "columnas": [c["nombre"] for c in cols], "filas": mu.get("filas")}
    if cod == "CP-05":
        n0 = m.get("nivel_0") or {}
        return {"version_delta": n0.get("version_delta"), "ultimo_commit": n0.get("ultimo_commit")}
    if cod == "ID-02":
        return {"filas": h.get("filas_hasheadas", filas), "filas_distintas": h.get("filas_distintas_por_hash"),
                "duplicados_exactos": h.get("filas_duplicadas_exactas"), "metodo": h.get("filas_distintas_metodo")}
    if cod in ("ID-03", "ID-04"):
        t = {k: {"nulos": v.get("nulos"), "pct_nulos": v.get("pct_nulos"), "registros": v.get("registros")} for k, v in pf.items()}
        out = {"nulos_por_columna": t}
        if cod == "ID-03":
            out["columnas_100_pct_nulas"] = [k for k, v in pf.items() if v.get("registros") and v.get("nulos") == v.get("registros")]
        else:
            out["columnas_con_nulos"] = [k for k, v in pf.items() if v.get("nulos")]
        return out
    if cod == "ID-05":
        return {"distintos_por_columna": {k: {"distintos": v.get("valores_distintos"), "registros": v.get("registros"),
                                               "pct_cardinalidad": v.get("pct_cardinalidad"), "candidata_a_llave": v.get("candidata_a_llave")}
                                           for k, v in pf.items()},
                "candidatas_a_llave": [k for k, v in pf.items() if v.get("candidata_a_llave")]}
    if cod == "ID-06":
        return {"distintos_por_columna": {k: v.get("valores_distintos") for k, v in pf.items()},
                "constantes": {k: v.get("valor_minimo_lexicografico", v.get("minimo")) for k, v in pf.items() if v.get("es_constante")}}
    return None


def _prec(t):
    import re
    x = re.search(r"decimal\((\d+)", str(t).lower())
    return int(x.group(1)) if x else 0


def _base(cod, cri, s, f, cr, cc, vg09, nivel_ctl, nivel_alc):
    """Resultado de la regla, sin mirar justificaciones: CUMPLE | NO_CUMPLE | IGUAL | DISTINTO | NO_EVALUADO | NO_APLICA."""
    v = (cc or {}).get("veredictos") or {}
    es, ef = s.get("estado"), f.get("estado")
    if cri == "no_aplica":
        return "NO_APLICA"
    if nivel_alc < nivel_ctl:
        return "NO_EVALUADO"
    if cod == "VG-09":
        return {"CUMPLE": "CUMPLE", "NO_CUMPLE": "NO_CUMPLE"}.get((vg09 or {}).get("estado"), "NO_EVALUADO")
    if cod == "CP-01":
        fl = v.get("filas") or (cr or {}).get("filas")
        return "NO_EVALUADO" if not fl else ("CUMPLE" if fl.get("delta") == 0 else "NO_CUMPLE")
    if cod == "CP-03":
        return "NO_EVALUADO" if not v.get("hash") else ("CUMPLE" if v["hash"].get("igual") else "NO_CUMPLE")
    if cod == "CP-02":
        e = v.get("esquema") or (cr or {}).get("esquema")
        return "NO_EVALUADO" if e is None else ("NO_CUMPLE" if (e.get("solo_en_stratio") or e.get("solo_en_fabric") or e.get("tipos_distintos")) else "CUMPLE")
    if cod == "CP-04":
        return "CUMPLE" if s.get("valor") and f.get("valor") else "NO_EVALUADO"
    if cod == "CP-05":
        return {"OK": "CUMPLE", "ERROR": "NO_CUMPLE", "NO_APLICA": "NO_APLICA"}.get(ef, "NO_EVALUADO")
    if es in (None, "NO_MEDIDO", "PENDIENTE") or ef in (None, "NO_MEDIDO", "PENDIENTE"):
        return "NO_EVALUADO"
    if ef == "NO_EVALUADO" or es == "NO_EVALUADO":
        return "NO_EVALUADO"
    if cod in ("ID-02", "ID-05") and v:
        return "NO_CUMPLE" if cod in ((v.get("controles") or {}).get("regresiones") or []) else "CUMPLE"
    if cri == "sin_fallas":
        return "NO_CUMPLE" if ef == "ERROR" and es != "ERROR" else "CUMPLE"
    if cod == "ID-03" and (cr or {}).get("vacias_solo_en_fabric"):
        return "NO_CUMPLE"
    return "NO_CUMPLE" if PEOR.get(ef, 0) > PEOR.get(es, 0) else "CUMPLE"


def _palabra(base, dd, avisos):
    ds = {d["decision"] for d in dd}
    if base == "NO_APLICA":
        return "no_aplica"
    if base == "NO_EVALUADO":
        return "no_evaluado"
    if "DEVUELTO" in ds:
        return "falla"
    if "PENDIENTE" in ds:
        return "pendiente"
    if "A_VERIFICAR" in ds:
        return "por_verificar"
    if dd:
        return "justificado"
    if base == "NO_CUMPLE":
        return "falla"
    return "advertencia" if avisos else "ok"


def cotejo(enc, f, o, ms, mf, cr, cc, difs, vg09, anterior=None, origen_decision=None, cp05=None):
    """Arma el cotejo de tabla (formato 2). `enc` trae lo tecnico (id, trabajo, generado_utc, mediciones)."""
    nivel = 2 if cc else (1 if cr else -1)
    grupo = f["grupo"]
    resumen = {fam: {} for fam in FAMILIAS}
    detalle = {fam: {} for fam in FAMILIAS}
    for c in CAT:
        cod, cri = c["codigo"], criterio(c["codigo"], grupo)
        s, fa = _lado(ms, cod), _lado(mf, cod)
        if cod == "CP-05":
            s = {"estado": "NO_APLICA", "detalle": "la corrida citada es la de Fabric; Stratio no se re-ejecuta en QA"}
            if cp05 and fa.get("estado") in (None, "NO_EVALUADO", "PENDIENTE", "NO_MEDIDO"):
                fa = cp05          # el rapido corrio sin ventana (flujo de orquestador): vale la evidencia medida de la corrida
        if cod == "VG-09":
            s = {"estado": "MEDIDO" if (vg09 or {}).get("contrato_stratio") else "NO_MEDIDO", "valor": f"contrato de {len((vg09 or {}).get('contrato_stratio') or [])} columnas"}
            fa = {"estado": "MEDIDO" if (vg09 or {}).get("contrato_fabric") else "NO_MEDIDO", "valor": f"contrato de {len((vg09 or {}).get('contrato_fabric') or [])} columnas"}
        medido, dist = _medido(cod, s, fa, ms, mf, cr, cc, vg09)
        base = _base(cod, cri, s, fa, cr, cc, vg09, c["nivel"], nivel)
        dd = [d for d in difs if d.get("control") == cod]
        avisos = []
        if base not in ("NO_APLICA", "NO_EVALUADO"):
            for lado, x in (("Stratio", s), ("Fabric", fa)):
                if x.get("estado") in ("ALERTA", "ERROR"):
                    avisos.append(f"{lado} queda en {x['estado']}: {x.get('detalle') or 'sin detalle'}")
            if dist and (base == "CUMPLE" or cod not in ("CP-01", "CP-03", "CP-02", "VG-09")):
                avisos += [f"medicion distinta entre lados: {t}" for t in dist]
        pal = _palabra(base, dd, avisos or (dist if base == "NO_CUMPLE" else []))
        rol = _rol(cod, grupo)
        if base == "CUMPLE" and not avisos:
            dec = "Cumple: " + {"sin_fallas": "Fabric no queda en ERROR.", "sin_regresion": "Fabric no queda peor que Stratio.",
                               "igual": "el valor es el mismo en los dos lados.", "commit_en_ventana": "la salida tiene commit dentro de la corrida citada.",
                               "igual_o_justificado": "el contrato de Stratio se conserva en Fabric.",
                               "informativo": "se midio en los dos lados y coincide."}.get(cri, "sin diferencias.")
        elif base == "NO_APLICA":
            dec = "No se evalua en este grupo."
        elif base == "NO_EVALUADO":
            dec = "No se evaluo en esta version: no cuenta como cumplido."
        elif dd:
            dec = (f"La regla {'no se cumple' if base == 'NO_CUMPLE' else 'se cumple con observaciones'}; "
                   + "; ".join(f"{d['id']} {d['decision']}" for d in dd) + ". Ver «justificaciones».")
        elif base == "NO_CUMPLE":
            dec = "No cumple y nadie ha registrado la diferencia: la tabla queda en revision."
        else:
            dec = ("La regla se cumple porque Fabric no empeora respecto a Stratio, pero la medicion muestra algo que debe quedar "
                   "registrado y decidido por una persona: la tabla queda en revision hasta entonces.")
        med = None if cod == "VG-09" else {"stratio": _lado_medicion(cod, ms), "fabric": _lado_medicion(cod, mf)}
        det = {"nombre": c["nombre"], "nivel": c["nivel"], "decide": rol == "decide", "rol": rol, "criterio": cri,
               "criterio_texto": CONTROLES["criterios"].get(cri), "stratio": s, "fabric": fa,
               **({"medicion": med} if med and (med["stratio"] is not None or med["fabric"] is not None) else {}),
               "comparacion": medido,
               "regla": base, "resultado": pal, "decision": dec}
        if avisos:
            det["advertencias"] = avisos
        if dd:
            det["diferencias"] = [d["id"] for d in dd]
        fam = cod[:2]
        resumen[fam][cod] = {"resultado": pal, "decide": rol == "decide"}
        detalle[fam][cod] = det

    todos = {cod: x for fam in FAMILIAS for cod, x in detalle[fam].items()}
    # ---- justificaciones: una por diferencia registrada, solo con lo vigente
    just = []
    for d in difs:
        dp = d.get("decidido_por") or {}
        just.append({"id": d["id"], "control": d["control"], "nombre_control": (todos.get(d["control"]) or {}).get("nombre"),
                     "decision": d["decision"], "tipo": d.get("tipo"), "columna": d.get("columna"),
                     "filas_afectadas": d.get("filas_afectadas"), "que_se_encontro": d.get("descripcion"),
                     "causa": d.get("causa"), "causa_medida": bool(d.get("causa_medida")),
                     "ejemplos": d.get("ejemplos") or [],
                     "analizado_por": "agente cotejador (IA), sobre las dos tablas completas en local",
                     "decidido_por": ({"quien": (origen_decision or {}).get(d["id"]) or d.get("decidido_como") or "QA",
                                       "usuario": dp.get("usuario"), "utc": dp.get("utc")} if dp else None)})
    # ---- metricas: lo que no pertenece a un control
    v = (cc or {}).get("veredictos") or {}
    ps, pf = ((ms or {}).get("nivel_2") or {}).get("perfil") or {}, ((mf or {}).get("nivel_2") or {}).get("perfil") or {}
    CAMPOS = ("nulos", "valores_distintos", "minimo", "maximo", "suma_exacta", "valor_minimo_lexicografico", "valor_maximo_lexicografico",
              "longitud_minima", "longitud_maxima", "cadenas_vacias")
    cols = {}
    lf = {k.lower(): k for k in pf}
    for n, a in ps.items():
        b = pf.get(n) or pf.get(lf.get(n.lower(), ""), {})
        fila = {"tipo_stratio": a.get("tipo_spark"), "tipo_fabric": b.get("tipo_spark")}
        difc = []
        for k in CAMPOS:
            if a.get(k) is not None or b.get(k) is not None:
                fila[k] = {"stratio": a.get(k), "fabric": b.get(k)}
                if a.get(k) != b.get(k):
                    difc.append(k)
        fila["difiere_en"] = difc
        cols[n] = fila
    metricas = {"filas": v.get("filas") or (cr or {}).get("filas"),
                "columnas_comparadas": len(cols), "columnas_con_alguna_diferencia": sum(1 for x in cols.values() if x["difiere_en"]),
                "por_columna": cols,
                "huella_por_columna": {"iguales": (v.get("hash") or {}).get("columnas_hash_igual"),
                                       "distintas": (v.get("hash") or {}).get("columnas_hash_distinto") or []} if v.get("hash") else None,
                "regresiones": (v.get("controles") or {}).get("regresiones"), "mejoras": (v.get("controles") or {}).get("mejoras")}

    # ---- estado
    pals = {cod: x["resultado"] for cod, x in todos.items()}
    sin_analizar = [cod for cod, p in pals.items() if p in ("advertencia",) or (p == "falla" and not todos[cod].get("diferencias"))]
    ds = {d["decision"] for d in difs}
    if nivel < 2:
        estado = "EN_CURSO"
    elif "DEVUELTO" in ds:
        estado = "DEVUELTO"
    elif any(p in BLOQUEAN for p in pals.values()):
        estado = "EN_REVISION"
    elif "por_verificar" in pals.values():
        estado = "APROBADO_CON_VERIFICACION"
    elif "justificado" in pals.values():
        estado = "APROBADO_CON_JUSTIFICACION"
    else:
        estado = "APROBADO"

    fl = metricas["filas"] or {}
    h = v.get("hash") or {}
    if h.get("igual"):
        res = f"100 % igual: {_n(fl.get('stratio'))} filas en los dos lados y la misma huella SHA-256 ({(h.get('hash_dataset_fabric') or '')[:12]}…)."
    elif nivel < 2:
        res = f"Sin veredicto: falta el nivel 2. Filas Stratio {_n(fl.get('stratio'))}, Fabric {_n(fl.get('fabric'))}."
    else:
        res = (f"Dato distinto. Stratio {_n(fl.get('stratio'))} filas, Fabric {_n(fl.get('fabric'))} "
               f"({fl.get('delta', 0):+d}; {fl.get('pct')} %). " +
               (f"{len(difs)} diferencia(s) registrada(s): " + " | ".join(
                   f"{d['id']} · {d['control']} · {d['decision']} · {_n(d.get('filas_afectadas'))} fila(s)" for d in difs) + ". "
                if difs else "Ninguna diferencia registrada. ") +
               (f"Sin analizar: {', '.join(sin_analizar)}." if sin_analizar else ""))
    cab = {"formato": "pc.v4/cotejo@2", "estado": estado, "resumen": res,
           "flujo": {"fl": f.get("fl"), "fabric": f["nombre_fabric"], "stratio": f.get("nombre_stratio")},
           "grupo": grupo, "version": enc["version"],
           "objeto": {"stratio": (o.get("stratio") or {}).get("ruta"), "fabric": (o.get("fabric") or {}).get("ruta")},
           "como_se_leyo": {"stratio": _como_se_leyo(ms, (o.get("stratio") or {}).get("ruta"), (o.get("stratio") or {}).get("referencia")),
                            "fabric": _como_se_leyo(mf, (o.get("fabric") or {}).get("ruta"), (o.get("fabric") or {}).get("referencia"))},
           "version_anterior": anterior, "verdad": "STRATIO", "nivel_alcanzado": nivel,
           "sin_analizar": sin_analizar,
           "trazabilidad": {k: enc.get(k) for k in ("id", "trabajo", "generado_utc", "mediciones", "esperando") if enc.get(k) is not None}}
    return {"encabezado": cab,
            "controles": {"leyenda": PALABRAS, "resumen": resumen, "detalle": detalle},
            "justificaciones": just, "metricas": metricas}


def faltantes_cotejo(doc):
    """Lo que impide publicar el cotejo de tabla. Vacio = completo."""
    f, e = [], doc.get("encabezado") or {}
    for k in ("estado", "resumen", "flujo", "grupo", "version", "objeto", "como_se_leyo"):
        if not e.get(k):
            f.append(f"encabezado.{k}")
    for lado in ("stratio", "fabric"):
        x = (e.get("como_se_leyo") or {}).get(lado) or {}
        for k in ("fuente", "medido_utc", "filas"):
            if x.get(k) is None:
                f.append(f"encabezado.como_se_leyo.{lado}.{k}")
    det = (doc.get("controles") or {}).get("detalle") or {}
    for fam in FAMILIAS:
        for cod, x in (det.get(fam) or {}).items():
            if x["resultado"] == "no_aplica":
                continue
            if x["resultado"] == "no_evaluado":
                f.append(f"{cod}: no evaluado")
            for lado in ("stratio", "fabric"):
                if (x.get(lado) or {}).get("estado") in (None, "NO_MEDIDO"):
                    f.append(f"{cod}: sin medicion de {lado}")
            if x["resultado"] in ("advertencia", "falla") and not x.get("diferencias"):
                f.append(f"{cod}: {x['resultado']} sin diferencia registrada")
    for j in doc.get("justificaciones") or []:
        if not j.get("ejemplos"):
            f.append(f"justificacion {j['id']} ({j['control']}): sin ejemplo")
        if not j.get("que_se_encontro"):
            f.append(f"justificacion {j['id']}: sin descripcion")
        if j["decision"] in ("JUSTIFICADA", "INFORMATIVA") and not j.get("causa"):
            f.append(f"justificacion {j['id']}: {j['decision']} sin causa")
        if j["decision"] == "JUSTIFICADA" and not j.get("causa_medida"):
            f.append(f"justificacion {j['id']}: causa no medida")
        if j["decision"] != "PENDIENTE" and not (j.get("decidido_por") or {}).get("usuario"):
            f.append(f"justificacion {j['id']}: sin quien decidio")
    if not (doc.get("metricas") or {}).get("por_columna"):
        f.append("metricas.por_columna")
    return f


# ============================================================================================ cotejo de flujo
def _tabla_corta(t):
    return (t or "").split(".")[-1].lower()


def flujo(enc, f, etl, ev, sem, tablas, ver, otros=None, decisiones=None):
    """Arma el cotejo de flujo (formato 2). ev = etl/evidencia/<flujo>.json (medido en Fabric)."""
    n = f["nombre_fabric"]
    ev, etl = ev or {}, etl or {}
    raw, r = etl.get("veredicto") or {}, etl.get("resumen") or {}
    inv = etl.get("inventario") or {}
    corr = inv.get("correccion") or {}
    cv = ev.get("corrida_validada") or {}
    orq = ev.get("orquestador") or {}
    acts_orq = orq.get("actividades") or []
    comp = []

    def chk(nombre, resultado, detalle):
        comp.append({"comprobacion": nombre, "resultado": resultado, "detalle": detalle})

    # ---- ejecucion
    dur = None
    if cv.get("inicio_utc") and cv.get("fin_utc"):
        from ..rapido.delta_remoto import a_utc
        dur = round((a_utc(cv["fin_utc"]) - a_utc(cv["inicio_utc"])).total_seconds())
    pad = orq.get("corrida_que_invoco_al_flujo")
    ejec = {"item": ev.get("item"),
            "corrida_validada": ({"run_id": cv.get("run_id"), "estado": cv.get("estado"), "inicio_utc": cv.get("inicio_utc"),
                                  "fin_utc": cv.get("fin_utc"), "duracion_s": dur,
                                  "lanzada_por": (f"orquestador {orq.get('nombre')} (corrida {pad['run_id']})" if pad else
                                                  "validador ETL de QA" if etl.get("lanzamiento") and not str(etl.get("lanzamiento")).startswith("orq") else
                                                  "directa (sin orquestador)"),
                                  "por_que_esta": cv.get("criterio"), "falla": cv.get("falla")} if cv else None),
            "actividades": ev.get("actividades"),
            "otras_corridas_del_dia": [c for c in ev.get("corridas") or [] if c.get("run_id") != cv.get("run_id")]}
    chk("Hay una corrida identificada para el flujo", "CUMPLE" if cv else "NO_CUMPLE",
        cv.get("criterio") or "no se encontro ninguna corrida del flujo en Fabric")
    chk("La corrida validada termino Completed", "CUMPLE" if cv.get("estado") == "Completed" else "NO_CUMPLE",
        f"estado {cv.get('estado')}" + (f" · {cv.get('falla')}" if cv.get("falla") else ""))
    acts = ev.get("actividades")
    if acts is not None:
        malas = [a["actividad"] for a in acts if a.get("estado") != "Succeeded"]
        chk("Todas las actividades de la corrida terminaron Succeeded", "CUMPLE" if acts and not malas else "NO_CUMPLE",
            f"{len(acts)} actividad(es)" + (f"; no exitosas: {malas}" if malas else ""))
    else:
        chk("Todas las actividades de la corrida terminaron Succeeded", "NO_EVALUADO", "no se obtuvieron las actividades de la corrida")

    # ---- validador ETL
    cita = ev.get("corrida_citada_por_el_validador") or {}
    gen = raw.get("generado_utc")
    # El validador prueba la corrida de dos formas (decision de QA 2026-10-07):
    #  · la ejecuto el mismo: pruebas antes/despues sobre ESA corrida;
    #  · la corrio un orquestador: el validador no re-ejecuta; vale su validacion estatica POSTERIOR a la corrida
    #    (despliegue, rutas, entradas legibles) junto con la evidencia de la corrida medida en Fabric.
    despues = bool(gen and cv.get("fin_utc") and gen >= cv["fin_utc"][:19])
    por_ejecucion = despues and bool(cita.get("coincide_con_la_validada")) and raw.get("se_ejecuto") is not False
    por_orquestador = (despues and raw.get("se_ejecuto") is False and bool(orq.get("corrida_que_invoco_al_flujo"))
                       and bool(raw.get("pasa_validacion")))
    probo = por_ejecucion or por_orquestador
    pruebas = []
    for p in raw.get("pruebas") or []:
        q = {"prueba": p.get("prueba") if p.get("prueba") != "(sin nombre)" else "actividad_o_objeto_sin_prueba",
             "resultado": p.get("nivel"), "objeto": p.get("objeto"), "esperado": p.get("esperado"), "obtenido": p.get("obtenido"),
             "detalle": p.get("detalle")}
        pruebas.append(q)
    val = {"resultado": r.get("resultado_validador"), "veredicto": r.get("veredicto_validador"), "corrio_utc": gen,
           "conteo": raw.get("resumen"), "valido_la_corrida_aprobada": probo,
           "modo": ("ejecuto y probo la corrida" if por_ejecucion else
                    "validacion estatica posterior a la corrida del orquestador + evidencia medida" if por_orquestador else
                    "no corresponde a la corrida validada"),
           "pruebas": pruebas, "omitidas": [p for p in pruebas if p["resultado"] == "OMITIDO"],
           "advertencias": r.get("advertencias") or [], "bloqueantes": r.get("bloqueantes") or []}
    if not probo:
        val["nota"] = ("Las pruebas del validador (antes/despues de ejecutar) NO corresponden a la corrida validada: " +
                       (f"el validador corrio a las {gen} y la corrida validada es la de {cv.get('inicio_utc')}." if gen else "no hay veredicto del validador."))
    ejec["validador"] = val
    chk("El validador ETL probo la corrida validada", "CUMPLE" if probo else "NO_CUMPLE",
        f"validador {gen} · corrida validada {cv.get('inicio_utc')}–{cv.get('fin_utc')} · " + val["modo"] +
        (" (el validador no re-ejecuta lo que corre un orquestador; la corrida se prueba con la evidencia de Fabric)" if por_orquestador else ""))
    chk("El validador no reporta bloqueantes", "CUMPLE" if not val["bloqueantes"] else "NO_CUMPLE",
        f"{len(val['bloqueantes'])} bloqueante(s), {len(val['advertencias'])} advertencia(s)")

    # ---- entradas y salidas
    band = {x["ruta"]: x for x in (corr.get("entradas") or []) + (corr.get("salidas") or [])}
    io = etl.get("io_medido") or {}
    cols_io = {x.get("tabla"): x for x in (io.get("entradas") or []) + (io.get("salidas") or [])}
    ent = []
    salidas_del_flujo = {((o.get("fabric") or {}).get("ruta") or "").lower() for o in f["objetos"]}
    for e in ev.get("entradas") or []:
        t = e.get("entrada")
        if (t or "").lower() in salidas_del_flujo:   # una salida registrada del flujo no es su entrada (rol invertido del validador)
            continue
        cl = e.get("commit_leido_por_la_corrida") or {}
        po = e.get("productor_segun_orquestador") or {}
        fila = {"entrada": t, "tipo": e.get("tipo"), "parametro_del_flujo": (band.get(t) or {}).get("bandera"),
                "columnas": (cols_io.get(t) or {}).get("columnas")}
        if e.get("tipo") == "tabla Delta":
            fila.update(version_leida=cl.get("version"), commit_utc=cl.get("utc"), operacion=cl.get("operacion"),
                        filas=cl.get("filas_escritas") if cl.get("filas_escritas") is not None else (cols_io.get(t) or {}).get("filas"),
                        antiguedad_al_leer_h=e.get("antiguedad_al_leer_h"),
                        producida_por=({"actividad_del_orquestador": po.get("actividad_del_orquestador"), "estado": po.get("estado"),
                                        "inicio_utc": po.get("inicio_utc"), "fin_utc": po.get("fin_utc")} if po else
                                       {"flujo": e.get("productor_segun_validador")} if e.get("productor_segun_validador") else
                                       "fuera de la cadena validada (commit anterior al orquestador)"),
                        cambio_despues_de_iniciar_la_corrida=e.get("cambio_despues_de_iniciar_la_corrida"),
                        commits_posteriores=e.get("commits_posteriores") or [])
        else:
            fila.update({k: e.get(k) for k in ("existe", "archivos", "bytes", "primera_escritura_utc", "ultima_escritura_utc",
                                               "archivos_escritos_despues_de_la_corrida", "nota") if e.get(k) is not None})
        ent.append(fila)
    sal = []
    for s in ev.get("salidas") or []:
        fila = {k: s.get(k) for k in ("tabla", "destino", "tipo", "version_vigente", "version_medida_nivel_2", "filas_medidas_nivel_2",
                                      "commit_de_la_version_medida", "la_version_medida_es_la_vigente", "commits_en_la_corrida_validada",
                                      "escrita_por_la_corrida_validada", "commits_posteriores_a_la_corrida", "existe", "archivos", "bytes",
                                      "primera_escritura_utc", "ultima_escritura_utc", "archivos_escritos_en_la_corrida",
                                      "bytes_escritos_en_la_corrida", "particiones_escritas_en_la_corrida", "particiones_escritas_muestra",
                                      "archivos_escritos_despues_de_la_corrida", "nota") if s.get(k) is not None}
        t = s.get("tabla")
        if t:
            fila["parametro_del_flujo"] = (band.get(t) or {}).get("bandera")
            fila["columnas"] = (cols_io.get(t) or {}).get("columnas")
        sal.append(fila)
    # ---- ingesta por Copy: la entrada (archivo de origen) la mide la propia actividad (filas y bytes leidos)
    fuera = []
    if f["grupo"] == "ingesta" and not ent:
        dest_obj = {((o.get("fabric") or {}).get("ruta") or "").replace("Files/", "").strip("/").lower() for o in f["objetos"]}
        sal_act = {x.get("actividad"): x for x in raw.get("salidas") or []}
        act = {a_["actividad"]: a_ for a_ in ev.get("actividades") or []}
        copias = [x for x in raw.get("entradas") or [] if (act.get(x.get("actividad")) or {}).get("tipo") == "Copy" or x.get("actividad") in sal_act]
        alcance = [x for x in copias if ((sal_act.get(x.get("actividad")) or {}).get("carpeta_real") or "").strip("/").lower() in dest_obj]
        if not alcance:                      # el destino final lo escribe otra actividad (p. ej. particionado): todas cuentan
            alcance = copias
        for x in alcance:
            a_ = act.get(x.get("actividad")) or {}
            so = sal_act.get(x.get("actividad")) or {}
            ent.append({"entrada": x.get("ruta_completa"), "tipo": "archivo de origen, medido por la actividad Copy",
                        "origen": x.get("tipo"), "actividad": x.get("actividad"), "estado": a_.get("estado"),
                        "inicio_utc": a_.get("inicio_utc"), "fin_utc": a_.get("fin_utc"),
                        "filas_leidas": a_.get("filas_leidas"), "filas_copiadas": a_.get("filas_copiadas"),
                        "filas_omitidas": a_.get("filas_omitidas"), "archivos_leidos": a_.get("archivos_leidos"),
                        "bytes_leidos": a_.get("bytes_leidos"), "bytes_escritos": a_.get("bytes_escritos"),
                        "escribe_en": so.get("ruta_completa")})
        en_alc = {x.get("actividad") for x in alcance}
        fuera = [a_ for a_ in ev.get("actividades") or [] if a_["actividad"] not in en_alc and a_.get("tipo") == "Copy"]
        if ent:
            malas = [e["actividad"] for e in ent if e.get("estado") != "Succeeded"]
            chk("Las actividades que cargan las tablas de este trabajo terminaron Succeeded", "CUMPLE" if not malas else "NO_CUMPLE",
                f"{len(ent)} actividad(es) en alcance" + (f"; no exitosas: {malas}" if malas else "") +
                (f"; fuera del alcance: {len(fuera)} ({[a_['actividad'] for a_ in fuera if a_.get('estado') != 'Succeeded']} no exitosas)" if fuera else ""))
            perd = [f"{e['actividad']} leyo {e.get('filas_leidas')} y copio {e.get('filas_copiadas')}" for e in ent
                    if e.get("filas_leidas") is None or e.get("filas_leidas") != e.get("filas_copiadas")]
            chk("Cada Copy en alcance copio todas las filas que leyo del origen", "CUMPLE" if not perd else "NO_CUMPLE",
                "; ".join(perd) if perd else "; ".join(f"{e['actividad']} {e['filas_leidas']} filas" for e in ent[:8]))
    no_tablas = [x["ruta"] for x in corr.get("salidas") or [] if "." not in (x.get("ruta") or "") and "/" not in (x.get("ruta") or "")]

    delta_ent = [e for e in ent if e.get("tipo") == "tabla Delta"]
    if delta_ent:
        sin_prod = [e["entrada"] for e in delta_ent if e.get("version_leida") is None]
        chk("Cada entrada Delta tiene identificado el commit que leyo el flujo", "CUMPLE" if not sin_prod else "NO_CUMPLE",
            f"{len(delta_ent)} entrada(s) Delta" + (f"; sin commit previo a la corrida: {sin_prod}" if sin_prod else ""))
        malas = [e["entrada"] for e in delta_ent if isinstance(e.get("producida_por"), dict) and e["producida_por"].get("estado") not in (None, "Succeeded")]
        chk("Las entradas producidas dentro de la cadena vienen de actividades Succeeded", "CUMPLE" if not malas else "NO_CUMPLE",
            f"producidas por una actividad no exitosa: {malas}" if malas else
            f"{sum(1 for e in delta_ent if isinstance(e.get('producida_por'), dict))} de {len(delta_ent)} entradas producidas dentro de la cadena")
    camb = [e["entrada"] for e in delta_ent if e.get("cambio_despues_de_iniciar_la_corrida")] + [
        f"{e['entrada']} ({e['archivos_escritos_despues_de_la_corrida']} archivo(s) hasta {e.get('ultima_escritura_utc')})"
        for e in ent if e.get("tipo") == "carpeta de archivos" and e.get("archivos_escritos_despues_de_la_corrida")]
    if ent and any(e.get("tipo") in ("tabla Delta", "carpeta de archivos") for e in ent):
        chk("Ninguna entrada cambio despues de iniciar la corrida", "CUMPLE" if not camb else "NO_CUMPLE",
            f"cambiaron despues: {camb} (la salida ya no refleja la entrada vigente)" if camb else
            "ninguna entrada (tabla o carpeta) fue escrita despues de iniciar la corrida")
    # salidas Postgres: no tienen _delta_log; las escribe una actividad Copy de la corrida (se prueba con sus filas copiadas)
    spg = [s for s in sal if s.get("tabla") and s.get("version_vigente") is None]
    if spg:
        copias = [a_ for a_ in (ev.get("actividades") or []) if a_.get("tipo") == "Copy"]
        ok_ = [a_ for a_ in copias if a_.get("estado") == "Succeeded" and (a_.get("filas_copiadas") or 0) > 0]
        for s_ in spg:
            s_["tipo"] = "tabla Postgres (sin _delta_log)"
            s_["escrita_por"] = [{"actividad": a_["actividad"], "estado": a_["estado"], "filas_copiadas": a_.get("filas_copiadas"),
                                  "inicio_utc": a_.get("inicio_utc"), "fin_utc": a_.get("fin_utc")} for a_ in copias]
            s_.pop("nota", None)
        chk("Cada salida Postgres la escribio una actividad Copy exitosa de la corrida validada", "CUMPLE" if ok_ and len(ok_) == len(copias) else "NO_CUMPLE",
            "; ".join(f"{a_['actividad']} {a_['estado']} {a_.get('filas_copiadas')} filas copiadas" for a_ in copias) or "la corrida no tiene actividad Copy")
    sd = [s for s in sal if s.get("tabla") and s.get("version_vigente") is not None]
    if sd:
        no = [s["tabla"] for s in sd if not s.get("escrita_por_la_corrida_validada")]
        chk("Cada salida se escribio dentro de la corrida validada", "CUMPLE" if not no else "NO_CUMPLE",
            f"sin commit en la ventana: {no}" if no else "; ".join(
                f"{_tabla_corta(s['tabla'])} v{(s['commits_en_la_corrida_validada'][-1] or {}).get('version')}" for s in sd))
        dif = [s["tabla"] for s in sd if s.get("version_medida_nivel_2") is not None and
               s.get("version_medida_nivel_2") not in [c["version"] for c in s.get("commits_en_la_corrida_validada") or []]]
        chk("La version medida en el nivel 2 es la que escribio la corrida validada", "CUMPLE" if not dif else "NO_CUMPLE",
            f"version medida distinta de la escrita por la corrida: {dif}" if dif else "coinciden en todas las salidas medidas")
        post = [s["tabla"] for s in sd if s.get("commits_posteriores_a_la_corrida")]
        chk("Ninguna salida fue reescrita despues de la corrida validada", "CUMPLE" if not post else "NO_CUMPLE",
            f"reescritas despues: {post}" if post else "la version vigente es la de la corrida validada")
    sc = [s for s in sal if s.get("destino")]
    for s in sc:
        chk(f"El destino {s['destino']} recibio archivos durante la corrida validada",
            "CUMPLE" if s.get("archivos_escritos_en_la_corrida") else "NO_CUMPLE",
            f"{s.get('archivos_escritos_en_la_corrida')} archivo(s) en {s.get('particiones_escritas_en_la_corrida')} particion(es); "
            f"{s.get('archivos_escritos_despues_de_la_corrida')} escrito(s) despues")

    # ---- flujos dependientes
    dep_val = raw.get("dependencias") or {}
    arriba = sorted({(e["producida_por"].get("actividad_del_orquestador") or "").replace("RunWorkflow_", "") or e["producida_por"].get("flujo")
                     for e in ent if isinstance(e.get("producida_por"), dict)} - {None, ""})
    mis_salidas = {_tabla_corta(s.get("tabla")) for s in sd}
    abajo = sorted({o_["flujo"] for o_ in (otros or []) if o_["flujo"] != n and mis_salidas & {_tabla_corta(x) for x in o_["entradas"]}}
                   | set(dep_val.get("downstream") or []))
    seccion = {"roles": ({"origen": "actividad Copy del pipeline (origen y destino)", "corregidos_respecto_al_validador": False,
                          "actividades_copy_fuera_del_alcance": [{"actividad": a_["actividad"], "estado": a_.get("estado"),
                                                                 **({"error": a_["error"]} if a_.get("error") else {})} for a_ in fuera]}
                         if r.get("roles_desde") == "actividad_copy" else
                         {"origen": "codigo del flujo (extract.py / load.py) + _delta_log", "zip": inv.get("zip"), "capa": inv.get("capa"),
                          "corregidos_respecto_al_validador": bool(corr.get("invertido")),
                          "que_se_corrigio": [{"tabla": c_["ruta"], "el_validador_decia": c_.get("rol_validador"), "segun_el_codigo": c_.get("rol_codigo")}
                                              for c_ in corr.get("cambios") or []],
                          "parametros_que_no_son_tablas": no_tablas}),
               "entradas": ent if ent else [{"entrada": x} for x in r.get("entradas") or []],
               "salidas": sal,
               "flujos_dependientes": {"de_los_que_depende": arriba, "que_dependen_de_este": abajo,
                                       "segun_el_validador": {"upstream": dep_val.get("upstream"), "downstream": dep_val.get("downstream")},
                                       "declaradas_en_el_trabajo": f.get("dependencias") or []}}
    if f["grupo"] == "analitica":
        ce = {c for x in ent for c in x.get("columnas") or []}
        cs = {c for x in sal for c in x.get("columnas") or []}
        seccion["transformacion"] = {"filas_de_entrada_por_tabla": {x["entrada"]: x.get("filas") for x in ent if x.get("filas") is not None},
                                     "filas_de_salida_por_tabla": {s["tabla"]: (s.get("commits_en_la_corrida_validada") or [{}])[-1].get("filas_escritas")
                                                                   for s in sd},
                                     "columnas_conservadas": sorted(ce & cs), "columnas_descartadas": sorted(ce - cs),
                                     "columnas_derivadas": sorted(cs - ce)}

    # ---- orquestacion
    if orq and orq.get("nombre"):
        pos = next((i for i, a in enumerate(acts_orq) if a["actividad"].replace("RunWorkflow_", "") == n), None)
        orquestacion = {"orquestador": orq["nombre"], "corrida": pad, "posicion_en_la_cadena": (pos + 1) if pos is not None else None,
                        "total_de_actividades": len(acts_orq),
                        "flujo_anterior": acts_orq[pos - 1] if pos else None,
                        "este_flujo": acts_orq[pos] if pos is not None else None,
                        "flujo_siguiente": acts_orq[pos + 1] if pos is not None and pos + 1 < len(acts_orq) else None,
                        "cadena": [{"orden": i + 1, "actividad": a["actividad"], "estado": a["estado"], "inicio_utc": a["inicio_utc"],
                                    "fin_utc": a["fin_utc"], **({"error": a["error"]} if a.get("error") else {})} for i, a in enumerate(acts_orq)],
                        "otras_corridas_del_orquestador": [c for c in orq.get("corridas") or [] if c.get("run_id") != (pad or {}).get("run_id")]}
        if pad and pad.get("estado") != "Completed":
            fall = next((i for i, a in enumerate(acts_orq) if a.get("estado") == "Failed"), None)
            orquestacion["nota"] = (f"El orquestador termino {pad['estado']}. " + (
                f"La falla esta en la actividad {fall + 1} ({acts_orq[fall]['actividad']}), "
                f"{'posterior' if pos is not None and fall > pos else 'ANTERIOR o igual'} a este flujo (posicion {pos + 1 if pos is not None else '?'})."
                if fall is not None else ""))
            if pos is not None and fall is not None:
                chk("La falla del orquestador es posterior a este flujo", "CUMPLE" if fall > pos else "NO_CUMPLE", orquestacion["nota"])
        if pos is not None:
            prev_malas = [a["actividad"] for a in acts_orq[:pos] if a.get("estado") != "Succeeded"]
            chk("Todos los flujos anteriores de la cadena terminaron Succeeded", "CUMPLE" if not prev_malas else "NO_CUMPLE",
                f"{pos} actividad(es) anteriores" + (f"; no exitosas: {prev_malas}" if prev_malas else ""))
    else:
        orquestacion = "NO APLICA"

    # ---- tablas y semaforo
    tabs = [{"clave": o["clave"], "fabric": (o.get("fabric") or {}).get("ruta"), "stratio": (o.get("stratio") or {}).get("ruta"),
             "estado": (t or {}).get("encabezado", {}).get("estado"), "resumen": (t or {}).get("encabezado", {}).get("resumen"),
             "sin_analizar": (t or {}).get("encabezado", {}).get("sin_analizar")} for o, t in zip(f["objetos"], tablas)]
    semaforo = None
    if sem:
        semaforo = {"estado": sem.get("estado"),
                    "que_significa": {"VERDE": "niveles 0 y 1 sin observaciones: paso al nivel 2",
                                      "AMARILLO": "paso al nivel 2 con avisos, que el nivel 2 debe explicar",
                                      "ROJO": "no paso: vuelve a desarrollo"}.get(sem.get("estado")),
                    "motivos_rojo": sem.get("motivos_rojo") or [], "avisos": sem.get("avisos") or [], "cumple": sem.get("cumple") or [],
                    "evaluado_utc": sem.get("evaluado_utc"),
                    "como_se_resolvieron_los_avisos": [
                        {"tabla": t["clave"], "estado_final": t["estado"], "resumen": t["resumen"]} for t in tabs]}

    # ---- decisiones de una persona sobre comprobaciones que no cumplen (causa medida, igual que una diferencia)
    for c in comp:
        d_ = (decisiones or {}).get(c["comprobacion"])
        if d_ and c["resultado"] == "NO_CUMPLE":
            c["decision"] = d_
            if d_.get("decision") == "JUSTIFICADA":
                c["resultado"] = "JUSTIFICADO"
    # ---- semaforo rojo levantado por una persona (los motivos quedan a la vista, con la causa)
    lev = (decisiones or {}).get("semaforo ROJO")
    rojo = (sem or {}).get("estado") == "ROJO"
    if semaforo and rojo and lev:
        semaforo["levantado"] = lev
    rojo_vigente = rojo and not (lev and lev.get("decision") == "JUSTIFICADA")
    # ---- estado
    ej = cv.get("estado") or r.get("estado_corrida")
    est = [t["estado"] for t in tabs]
    fallan = [c["comprobacion"] for c in comp if c["resultado"] == "NO_CUMPLE"]
    justificadas = [c["comprobacion"] for c in comp if c["resultado"] == "JUSTIFICADO"]
    alcance_ok = f["grupo"] == "ingesta" and any(c["comprobacion"].startswith("Las actividades que cargan") and c["resultado"] == "CUMPLE" for c in comp)
    if f["grupo"] == "orquestador":
        estado = "APROBADO" if ej == "Completed" else ("DEVUELTO" if ej in ("Failed", "Cancelled") else "EN_CURSO")
    elif (rojo_vigente or (ej in ("Failed", "Cancelled") and not alcance_ok)
          or (ver or {}).get("decision") == "CORREGIR" or "DEVUELTO" in est):
        estado = "DEVUELTO"     # una corrida fallida devuelve el flujo, salvo que lo fallido este fuera del alcance: eso lo decide una persona
    elif not est or any(e in (None, "EN_CURSO") for e in est):
        estado = "EN_CURSO"
    elif "EN_REVISION" in est or fallan or any(c["resultado"] == "NO_EVALUADO" for c in comp):
        estado = "EN_REVISION"
    elif "APROBADO_CON_VERIFICACION" in est:
        estado = "APROBADO_CON_VERIFICACION"
    elif "APROBADO_CON_JUSTIFICACION" in est or justificadas or (rojo and not rojo_vigente):
        estado = "APROBADO_CON_JUSTIFICACION"
    else:
        estado = "APROBADO"
    cab = {"formato": "pc.v4/cotejo_flujo@2", "estado": estado,
           "resumen": (f"Corrida {cv.get('estado')} {cv.get('inicio_utc')}–{cv.get('fin_utc')}. "
                       f"{sum(1 for c in comp if c['resultado'] == 'CUMPLE')} de {len(comp)} comprobaciones del flujo cumplen" +
                       (f"; no cumplen: {fallan}" if fallan else "") + ". Tablas: " +
                       ", ".join(f"{t['clave']} {t['estado']}" for t in tabs) + "."),
           "flujo": {"fl": f.get("fl"), "fabric": n, "stratio": f.get("nombre_stratio")}, "grupo": f["grupo"],
           "version": enc["version"], "orquestador": f.get("orquestador") or (orq.get("nombre") if orq else None),
           "version_anterior": enc.get("version_anterior"),
           "comprobaciones_que_no_cumplen": fallan,
           "trazabilidad": {"id": enc.get("id"), "trabajo": enc.get("trabajo"), "generado_utc": enc.get("generado_utc"),
                            "evidencia_medida_utc": ev.get("medido_utc"), "fuente_de_la_evidencia": ev.get("fuente")}}
    doc = {"encabezado": cab, "ejecucion": ejec, ("ingesta" if f["grupo"] == "ingesta" else "analitica"): seccion,
           "orquestacion": orquestacion, "comprobaciones": comp, "tablas": tabs, "semaforo": semaforo}
    if ver:
        doc["verificacion"] = ver
    return doc


def faltantes_flujo(doc):
    f, e = [], doc.get("encabezado") or {}
    ej = doc.get("ejecucion") or {}
    cv = ej.get("corrida_validada") or {}
    for k in ("run_id", "estado", "inicio_utc", "fin_utc", "duracion_s", "lanzada_por", "por_que_esta"):
        if cv.get(k) is None:
            f.append(f"ejecucion.corrida_validada.{k}")
    if not ej.get("actividades"):
        f.append("ejecucion.actividades")
    if not (ej.get("validador") or {}).get("pruebas"):
        f.append("ejecucion.validador.pruebas")
    sec = doc.get("analitica") or doc.get("ingesta") or {}
    if not sec.get("entradas"):
        f.append("entradas")
    if not sec.get("salidas"):
        f.append("salidas")
    for x in sec.get("entradas") or []:
        if "Copy" in str(x.get("tipo")) and x.get("filas_leidas") is None:
            f.append(f"entrada {x['entrada']}: la actividad Copy no reporta filas leidas")
        if x.get("tipo") == "tabla Delta" and x.get("version_leida") is None:
            f.append(f"entrada {x['entrada']}: sin version leida")
        if not x.get("tipo"):
            f.append(f"entrada {x.get('entrada')}: sin medir")
    if doc.get("orquestacion") is None:
        f.append("orquestacion")
    if e.get("orquestador") and doc.get("orquestacion") == "NO APLICA":
        f.append("orquestacion: el flujo declara orquestador pero no hay cadena medida")
    if not doc.get("comprobaciones"):
        f.append("comprobaciones")
    if not doc.get("semaforo"):
        f.append("semaforo")
    if not doc.get("tablas"):
        f.append("tablas")
    if not e.get("trazabilidad", {}).get("evidencia_medida_utc"):
        f.append("evidencia del flujo (pc etl evidencia)")
    return f
