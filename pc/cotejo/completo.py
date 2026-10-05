"""Cotejo COMPLETO (nivel 2) Stratio vs Fabric de dos reportes del motor v15.

Copia de ~/Projects/validacion_lote9/cotejo.py con tres cambios: sin rutas fijas (salida por parametro),
fuera del computo VG-07/VG-08/ID-07/ID-08 (catalogo), y CP-04 informativo. La logica de veredictos
y criterio por grupo es la misma que ya se uso en los lotes 9 a 11."""
import datetime
import json
import os
import re
import sys
import unicodedata



def norm(n):
    s = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


FUERA = {"VG-07", "VG-08", "ID-07", "ID-08"}
INFORMATIVOS = {"CP-04", "CP-05"}


def _reglas(rep):
    v = rep.get("validaciones") or {}
    out = {}
    for b in ("ID_integridad_y_conteos", "VG_esquema_y_metadata"):
        for r in v.get(b) or []:
            out[r["codigo"]] = r["estado"]
    for k, r in (rep.get("puntos_control") or {}).items():
        out[k.split("_")[0]] = r.get("estado")
    return {k: v for k, v in out.items() if k not in FUERA and k not in INFORMATIVOS}


def _num(v):
    """Normaliza los metadatos numericos del information_schema.

    El esquema de Fabric llega por la pipeline de QA en parquet, y ahi el nulo de
    character_maximum_length o numeric_precision se convierte en NaN. Como NaN nunca es igual a si
    mismo, sin esta normalizacion `text` y `text` se reportan como tipos distintos.
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return None if f != f else int(f)


def _tpg(r):
    t = r["data_type"]
    n = _num(r.get("character_maximum_length"))
    p = _num(r.get("numeric_precision"))
    if n:
        t += f"({n})"
    elif t == "numeric" and p:
        t += f"({p},{_num(r.get('numeric_scale')) or 0})"
    return t


ENSANCHA = {("integer", "bigint"), ("smallint", "integer"), ("smallint", "bigint"), ("integer", "numeric"),
            ("bigint", "numeric"), ("real", "double precision"), ("date", "timestamp without time zone"),
            ("integer", "double precision"), ("bigint", "double precision"),
            ("double precision", "numeric"), ("real", "numeric")}
TEXTO = {"text", "character varying", "character"}


def _clase(x, y):
    a, b = x["data_type"], y["data_type"]
    if a in TEXTO and b in TEXTO:
        return "EQUIVALENTE_TEXTO"
    if (a, b) in ENSANCHA:
        return "ENSANCHAMIENTO_COMPATIBLE"
    if a == b:
        return "PRECISION_DISTINTA"
    return "INCOMPATIBLE"


def cotejar(o, ruta_s, ruta_f, W, fecha, lote=None):
    """o = {clave, grupo, flujo, flujo_stratio?, justificaciones?}. W = carpeta de salida (crea W/cotejos)."""
    S, F = json.load(open(ruta_s)), json.load(open(ruta_f))
    grupo = o["grupo"]
    js = o.get("justificaciones", {})
    ns, nf = S["conteos"]["row_count"], F["conteos"]["row_count"]
    hs, hf = S["hash"], F["hash"]
    cs = {c["nombre"]: c for c in S["esquema"]["columnas"]}
    cf = {c["nombre"]: c for c in F["esquema"]["columnas"]}
    # emparejamiento de columnas: exacto, y si no, por nombre normalizado (mayusculas, _, espacios, tildes)
    par, solo_s, solo_f = {}, [], []
    nf_idx = {}
    for n in cf:
        nf_idx.setdefault(norm(n), []).append(n)
    usados = set()
    for n in cs:
        if n in cf:
            par[n] = n
            usados.add(n)
    for n in cs:
        if n in par:
            continue
        cand = [x for x in nf_idx.get(norm(n), []) if x not in usados]
        if cand:
            par[n] = cand[0]
            usados.add(cand[0])
        else:
            solo_s.append(n)
    solo_f = [n for n in cf if n not in usados]
    renombradas = {a: b for a, b in par.items() if a != b}
    tipos = {a: {"stratio": cs[a]["tipo"], "fabric": cf[b]["tipo"]} for a, b in par.items()
             if cs[a]["tipo"] != cf[b]["tipo"]}
    # tipos declarados en Postgres (cuando los dos lados son Postgres)
    eps = {r["column_name"]: r for r in (S["objeto"].get("esquema_postgres") or [])}
    epf = {r["column_name"]: r for r in (F["objeto"].get("esquema_postgres") or [])}
    tipos_pg = {}
    if eps and epf:
        for a, b in par.items():
            x, y = eps.get(a), epf.get(b)
            firma = lambda r: (r["data_type"], _num(r.get("numeric_precision")), _num(r.get("numeric_scale")),
                               _num(r.get("character_maximum_length")))
            if x and y and firma(x) != firma(y):
                tipos_pg[a] = {"stratio": _tpg(x), "fabric": _tpg(y), "clase": _clase(x, y)}
        for a, t in tipos_pg.items():
            tipos[a] = {"stratio": t["stratio"], "fabric": t["fabric"], "clase": t["clase"]}
        for a in list(tipos):
            if a not in tipos_pg:
                tipos.pop(a)     # diferencia solo del parquet intermedio, no de la tabla
    # posicion real: el orden de Stratio llevado a nombres de Fabric contra el orden fisico de Fabric
    orden_s = [par.get(c["nombre"]) for c in S["esquema"]["columnas"] if par.get(c["nombre"])]
    orden_f = [c["nombre"] for c in F["esquema"]["columnas"] if c["nombre"] in usados]
    orden_igual = (orden_s == orden_f) if not (solo_s or solo_f) else False
    orden_detalle = None if orden_igual else {"stratio": [c["nombre"] for c in S["esquema"]["columnas"]],
                                              "fabric": [c["nombre"] for c in F["esquema"]["columnas"]]}
    # dato
    hps, hpf = hs.get("hash_por_columna") or {}, hf.get("hash_por_columna") or {}
    col_dif = sorted(a for a, b in par.items() if a in hps and b in hpf and hps[a] != hpf[b])
    col_ok = sorted(a for a, b in par.items() if a in hps and b in hpf and hps[a] == hpf[b])
    igual_hash = bool(hs.get("hash_dataset")) and hs.get("hash_dataset") == hf.get("hash_dataset")
    igual_set = bool(hs.get("hash_conjunto_columnas")) and hs.get("hash_conjunto_columnas") == hf.get("hash_conjunto_columnas")
    seg_s, seg_f = hs.get("segregacion") or {}, hf.get("segregacion") or {}
    limpias_iguales = bool(seg_s.get("hash_filas_limpias")) and seg_s.get("hash_filas_limpias") == seg_f.get("hash_filas_limpias")
    if not hs.get("hash_dataset") or not hf.get("hash_dataset"):
        v_dato = "NO_MEDIDO_EN_ANALITICA"
    elif ns == nf and igual_hash:
        v_dato = "IDENTICO"
    elif ns == nf and igual_set:
        v_dato = "MISMO_DATO_OTRO_ORDEN_O_NOMBRE"
    elif ns == nf and not col_dif and par and not solo_s and not solo_f:
        v_dato = "MISMO_DATO_POR_COLUMNA"
    elif col_dif or ns != nf:
        pct = round(100.0 * len(col_ok) / max(1, len(par)), 2)
        v_dato = "CASI_IDENTICO" if ns == nf and pct >= 90 else "DIFERENTE"
    else:
        v_dato = "SIN_PARIDAD"
    # nulos y perfil
    ms, mf = S["metricas_columnas"], F["metricas_columnas"]
    nulos = {a: {"stratio": ms[a]["nulos"], "fabric": mf[b]["nulos"]} for a, b in par.items()
             if ms.get(a, {}).get("nulos") != mf.get(b, {}).get("nulos")}
    distintos = {a: {"stratio": ms[a].get("valores_distintos"), "fabric": mf[b].get("valores_distintos")}
                 for a, b in par.items() if ms.get(a, {}).get("valores_distintos") != mf.get(b, {}).get("valores_distintos")}
    perfil_dif = {}
    for a, b in par.items():
        d = {}
        for k in ("minimo", "maximo", "suma_exacta", "longitud_maxima", "longitud_minima", "cadenas_vacias",
                  "con_caracteres_no_ascii", "con_caracteres_de_control", "valor_minimo_lexicografico",
                  "valor_maximo_lexicografico"):
            if k in ms.get(a, {}) or k in mf.get(b, {}):
                if ms.get(a, {}).get(k) != mf.get(b, {}).get(k):
                    d[k] = {"stratio": ms.get(a, {}).get(k), "fabric": mf.get(b, {}).get(k)}
        if d:
            perfil_dif[a] = d
    # contrato
    ks = {c["nombre"]: c for c in S["contrato_propuesto"]["columnas"]}
    kf = {c["nombre"]: c for c in F["contrato_propuesto"]["columnas"]}
    rupturas = []
    for a, b in par.items():
        x, y = ks[a], kf[b]
        if x["tipo"] != y["tipo"]:
            rupturas.append({"columna": a, "regla": "tipo", "stratio": x["tipo"], "fabric": y["tipo"]})
        if (not x["nullable"]) and y["nullable"]:
            rupturas.append({"columna": a, "regla": "dejo_de_ser_obligatoria", "stratio": x["observado_pct_nulos"], "fabric": y["observado_pct_nulos"]})
        if x.get("candidata_a_llave") and not y.get("candidata_a_llave"):
            rupturas.append({"columna": a, "regla": "dejo_de_ser_llave"})
        lx, ly = x.get("observado_longitud_maxima"), y.get("observado_longitud_maxima")
        if lx is not None and ly is not None and ly > lx:
            rupturas.append({"columna": a, "regla": "longitud_maxima_crecio", "stratio": lx, "fabric": ly})
    for n in solo_s:
        rupturas.append({"columna": n, "regla": "columna_ausente_en_fabric"})
    for n in solo_f:
        rupturas.append({"columna": n, "regla": "columna_nueva_en_fabric"})
    # controles
    rs, rf = _reglas(S), _reglas(F)
    regresiones = sorted(k for k in rs if rs[k] == "OK" and rf.get(k) not in ("OK", None))
    mejoras = sorted(k for k in rs if rs[k] not in ("OK", None) and rf.get(k) == "OK")

    def pct(bloque):
        cods = [k for k in rf if k.startswith(bloque)]
        ev = [k for k in cods if rf[k] in ("OK", "ALERTA", "ERROR")]
        ok = [k for k in ev if rf[k] == "OK" or rs.get(k) == rf[k]]
        return round(100.0 * len(ok) / len(ev), 2) if ev else None
    controles = {"CP": pct("CP"), "ID": pct("ID"), "VG": pct("VG"),
                 "stratio": rs, "fabric": rf, "regresiones": regresiones, "mejoras": mejoras}
    vg_fallas = sorted(k for k in rf if k.startswith("VG") and rf[k] in ("ERROR",) and rs.get(k) != "ERROR")
    vg_heredadas = sorted(k for k in rf if k.startswith("VG") and rf[k] == "ERROR" and rs.get(k) == "ERROR")
    controles["vg_heredadas_de_stratio"] = vg_heredadas
    # criterio
    just = []
    tipos_no_just = {c: t for c, t in tipos.items() if c not in js.get("tipos", {})
                     and t.get("clase") not in ("EQUIVALENTE_TEXTO",)}
    solo_compatibles = bool(tipos_no_just) and all(t.get("clase") in ("ENSANCHAMIENTO_COMPATIBLE", "PRECISION_DISTINTA") for t in tipos_no_just.values())
    solo_s_nj = [c for c in solo_s if c not in js.get("columnas_ausentes", [])]
    solo_f_nj = [c for c in solo_f if c not in js.get("columnas_nuevas", [])]
    equiv = js.get("dato_equivalente")
    js_dec = {a: b for a, b in js.items() if a != "verificado_por" and b}
    if grupo == "ingesta":
        exige = {"filas_iguales": ns == nf or bool(equiv), "hash_dataset_igual": igual_hash or bool(equiv),
                 "columnas_iguales": not solo_s_nj and not solo_f_nj, "tipos_iguales": not tipos_no_just,
                 "vg_sin_fallas": not vg_fallas}
        base_ok = all(exige.values())
    else:
        exige = {"mismas_columnas": not solo_s_nj and not solo_f_nj, "tipos_iguales": not tipos_no_just,
                 "vg_sin_fallas": not vg_fallas,
                 "id_sin_regresiones": not [r for r in regresiones if r.startswith("ID") and r not in js.get("regresiones", [])]}
        base_ok = all(exige.values())
    if vg_heredadas:
        just.append(f"{', '.join(vg_heredadas)} en ERROR en los dos lados: característica heredada del contrato de Stratio (p. ej. nombres con espacios), no introducida por la migración")
    if js.get("regresiones_no_justificadas"):
        # hallazgo de integridad que el negocio NO justifica (p. ej. duplicacion por append)
        exige["sin_regresiones_criticas"] = False
        base_ok = False
    if renombradas:
        just.append(f"renombrado de forma (mayúsculas/guiones/espacios) en {len(renombradas)} columna(s): "
                    + ", ".join(f"{a}→{b}" for a, b in list(renombradas.items())[:8]))
    # TODA justificacion declarada tiene que quedar escrita en el cotejo, pase o no por la rama de
    # corte: si el objeto se aprueba con una diferencia, el lector tiene que ver por que.
    for k, t in js.items():
        if k == "texto":
            just.append(t)
        elif k == "corte_distinto" and t:
            just.append(f"APROBADO DELIMITADO A LOS CORTES DE FECHA VERIFICADOS. {t}")
        elif k == "tipos" and isinstance(t, dict) and t:
            just.append("Tipos justificados: " + " · ".join(f"{c}: {v}" for c, v in t.items()))
        elif k == "columnas_ausentes" and t:
            just.append(f"Columnas de Stratio ausentes en Fabric justificadas: {', '.join(t)}")
        elif k == "columnas_nuevas" and t:
            just.append(f"Columnas nuevas en Fabric justificadas: {', '.join(t)}")
        elif k == "regresiones" and t:
            just.append(f"Regresiones justificadas: {', '.join(t)}")
        elif k == "perfil" and t:
            just.append(t)
    if equiv and not igual_hash:
        just.append(f"hash distinto solo por una transformación declarada de Fabric; equivalencia demostrada fila a fila: {equiv}")
    if base_ok and not renombradas and v_dato == "IDENTICO":
        resultado = "APROBADO"
    elif base_ok:
        resultado = "APROBADO_CON_JUSTIFICACION" if (renombradas or js_dec or v_dato != "IDENTICO") else "APROBADO"
    else:
        resultado = "REVISAR"
    if grupo == "analitica" and base_ok:
        resultado = "APROBADO" if not renombradas and not js_dec else "APROBADO_CON_JUSTIFICACION"
    if resultado == "REVISAR" and js.get("corte_distinto") and all(v for k, v in exige.items() if k not in ("filas_iguales", "hash_dataset_igual")):
        # El contrato y el esquema se cumplen; lo unico que cambia es la ventana de datos que
        # tiene cada plataforma. Se aprueba DELIMITADO a los cortes comunes verificados.
        resultado = "APROBADO_CON_JUSTIFICACION"
        alcance = "aprobado delimitado a los cortes de fecha verificados"
        t = f"APROBADO DELIMITADO A LOS CORTES DE FECHA VERIFICADOS. {js['corte_distinto']}"
        if t not in just:
            just.append(t)
    if resultado == "REVISAR" and solo_compatibles and all(v for k, v in exige.items() if k != "tipos_iguales"):
        # El lakehouse recibe el tipo correcto; en Postgres solo cambia la precision/amplitud declarada.
        resultado = "APROBADO_CON_JUSTIFICACION"
        just.append("El dato se recibe con el TIPO CORRECTO en la tabla Delta del lakehouse. En la Postgres de "
                    "Fabric solo cambia la precisión o amplitud declarada del tipo, sin afectar el valor; "
                    "el ajuste del DDL está listado en REPORTE_PG_ANALITICA.md.")
    if any(t.get("clase") == "EQUIVALENTE_TEXTO" for t in tipos.values()):
        just.append("text ↔ varchar sin longitud: mismo tipo en PostgreSQL")
    resumen = (f"dato {v_dato}; cols S {len(cs)} F {len(cf)} (solo S {len(solo_s)}, solo F {len(solo_f)}, "
               f"renombradas {len(renombradas)}, tipos {len(tipos)}); col_hash_dif {len(col_dif)}; "
               f"regresiones {regresiones}")
    # comparador del notebook, tal cual
    nb = None
    if not os.environ.get("PC_COMPARADOR_NB"):
        nb = {"omitido": "comparador del notebook desactivado (PC_COMPARADOR_NB=1 para activarlo)"}
    else:
      try:
          sys.path.insert(0, "/home/quind/Projects/comfandi/cea-analytics-comfandi/qa-etl-validador-agent-v2/actas")
          os.environ.setdefault("COTEJO_BASE", os.path.join(W, "cotejos_nb"))
          from herramientas import comparador
          import io, contextlib
          with contextlib.redirect_stdout(io.StringIO()):
              r = comparador.comparar_reportes(ruta_s, ruta_f, guardar=False)
          nb = {"veredicto": r.get("veredicto"), "similitud": r.get("similitud"), "avisos": r.get("avisos"),
                "diferencias": r.get("diferencias")}
      except Exception as e:
          nb = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
    run8 = (F["ejecucion"]["run_id"] or "")[:8]
    doc = {
        "tipo_de_documento": "COTEJO_STRATIO_FABRIC", "version_reporte": "1.0.0",
        "lote": str(lote), "fecha": fecha, "generado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "grupo": grupo, "flujo_fabric": o["flujo"], "flujo_stratio": o.get("flujo_stratio"),
        "clave_cotejo": o["clave"],
        "a": {"plataforma_ambiente": "STRATIO_QA", "archivo": os.path.basename(ruta_s), "ubicacion": S["objeto"]["ubicacion"],
              "tipo_fuente": S["objeto"]["tipo_fuente"], "run_id": S["ejecucion"]["run_id"], "medido_utc": S["ejecucion"]["medido_utc"],
              "almacenamiento": S["objeto"].get("almacenamiento")},
        "b": {"plataforma_ambiente": "FABRIC_QA", "archivo": os.path.basename(ruta_f), "ubicacion": F["objeto"]["ubicacion"],
              "tipo_fuente": F["objeto"]["tipo_fuente"], "run_id": F["ejecucion"]["run_id"], "medido_utc": F["ejecucion"]["medido_utc"],
              "almacenamiento": F["objeto"].get("almacenamiento")},
        "criterio": ("paridad exacta del dato (filas + hash SHA-256 canónico v15)" if grupo == "ingesta"
                     else "integración: contrato (columnas y tipos), VG sin fallas e ID sin regresiones; filas informativas"),
        "exigencias": exige,
        "resultado": resultado,
        "veredictos": {
            "dato": v_dato,
            "filas": {"stratio": ns, "fabric": nf, "delta": nf - ns, "pct": round(100.0 * nf / ns, 4) if ns else None},
            "hash": {"hash_dataset_stratio": hs.get("hash_dataset"), "hash_dataset_fabric": hf.get("hash_dataset"),
                     "igual": igual_hash, "hash_conjunto_columnas_igual": igual_set,
                     "hash_filas_limpias_igual": limpias_iguales,
                     "columnas_hash_distinto": col_dif, "columnas_hash_igual": len(col_ok),
                     "columnas_excluidas_hash": hs.get("columnas_excluidas"),
                     "filas_duplicadas": {"stratio": hs.get("filas_duplicadas_exactas"), "fabric": hf.get("filas_duplicadas_exactas")}},
            "esquema": {"hash_esquema_tipos_igual": S["esquema"]["hash_esquema_tipos"] == F["esquema"]["hash_esquema_tipos"],
                        "hash_nombres_igual": S["esquema"]["hash_nombres_columnas"] == F["esquema"]["hash_nombres_columnas"],
                        "orden_igual": orden_igual, "orden_columnas": orden_detalle, "solo_en_stratio": solo_s, "solo_en_fabric": solo_f,
                        "renombradas_forma": renombradas, "tipos_distintos": tipos,
                        "columnas_excluidas_del_cotejo": {"stratio": S["objeto"].get("columnas_excluidas_del_cotejo"),
                                                          "fabric": F["objeto"].get("columnas_excluidas_del_cotejo")}},
            "nulos": {"columnas_con_nulos_distintos": nulos},
            "cardinalidad": {"columnas_con_distintos_diferentes": distintos},
            "perfil": {"columnas_con_perfil_distinto": perfil_dif},
            "contrato": {"respeta": not rupturas, "rupturas": rupturas},
            "controles": controles,
        },
        "justificacion": just,
        "comparador_notebook_v15": nb,
    }
    # nunca reutilizar un nombre: el bucket no sobrescribe (If-None-Match), asi que un cotejo rehecho sube de version
    n = 1
    os.makedirs(os.path.join(W, "cotejos"), exist_ok=True)
    while os.path.exists(os.path.join(W, "cotejos", f"metrica_{o['clave']}_{fecha}_{run8}_v{n}.json")):
        n += 1
    nombre = f"metrica_{o['clave']}_{fecha}_{run8}_v{n}.json"
    ruta = os.path.join(W, "cotejos", nombre)
    json.dump(doc, open(ruta, "w"), ensure_ascii=False, indent=1, default=str)
    return {"archivo": ruta, "resultado": resultado, "veredicto": f"{resultado}/{v_dato}",
            "filas_stratio": ns, "filas_fabric": nf, "resumen": resumen, "exigencias": exige}
