"""Cotejo RAPIDO (niveles 0 y 1): enfrenta dos reportes rapidos (Stratio y Fabric) de la misma tabla.

Aplica el catalogo config/controles.json segun el grupo (ingesta | analitica). Lo que solo se
decide en nivel 2 queda PENDIENTE; nunca se da por cumplido.
"""
import datetime

from ..config import CONTROLES, criterio
from .completo import norm

PEOR = {"OK": 0, "INFORMATIVO": 0, "NO_EVALUADO": 0, "NO_APLICA": 0, "PENDIENTE_NIVEL_2": 0, "ALERTA": 1, "ERROR": 2}


def _par(cs, cf):
    """Empareja columnas: exacto y luego por nombre normalizado."""
    par, usados = {}, set()
    idx = {}
    for n in cf:
        idx.setdefault(norm(n), []).append(n)
    for n in cs:
        if n in cf:
            par[n] = n
            usados.add(n)
    for n in cs:
        if n not in par:
            c = [x for x in idx.get(norm(n), []) if x not in usados]
            if c:
                par[n] = c[0]
                usados.add(c[0])
    return par, [n for n in cs if n not in par], [n for n in cf if n not in usados]


def cotejar(S, F, grupo, ventana_fabric=None):
    """S, F = reportes rapidos. Devuelve el cotejo rapido con estado por control."""
    cs = {c["nombre"]: c for c in S["nivel0"]["columnas"]}
    cf = {c["nombre"]: c for c in F["nivel0"]["columnas"]}
    par, solo_s, solo_f = _par(cs, cf)
    tipos = {a: {"stratio": cs[a]["tipo"], "fabric": cf[b]["tipo"]} for a, b in par.items() if cs[a]["tipo"] != cf[b]["tipo"]}
    ns, nf = S["nivel1"]["filas"], F["nivel1"]["filas"]
    ks, kf = S["nivel1"]["columnas"], F["nivel1"]["columnas"]
    nulos = {}
    for a, b in par.items():
        x, y = ks.get(a, {}), kf.get(b, {})
        if x.get("nivel_perfil") == "SIN_ESTADISTICAS" or y.get("nivel_perfil") == "SIN_ESTADISTICAS":
            continue
        if x.get("nulos") != y.get("nulos"):
            nulos[a] = {"stratio": x.get("nulos"), "fabric": y.get("nulos"),
                        "pct_stratio": x.get("pct_nulos"), "pct_fabric": y.get("pct_nulos")}
    vacias_nuevas = [a for a, b in par.items() if (kf.get(b, {}).get("pct_nulos") == 100.0)
                     and (ks.get(a, {}).get("pct_nulos") or 0) < 100.0]
    constantes_nuevas = [a for a, b in par.items() if kf.get(b, {}).get("es_constante") and not ks.get(a, {}).get("es_constante")
                         and ks.get(a, {}).get("nivel_perfil") != "SIN_ESTADISTICAS"]
    ctl = {}
    for c in CONTROLES["controles"]:
        cod, cri = c["codigo"], criterio(c["codigo"], grupo)
        es, ef = (S["controles"].get(cod) or {}).get("estado"), (F["controles"].get(cod) or {}).get("estado")
        fila = {"codigo": cod, "nivel": c["nivel"], "criterio": cri, "stratio": es, "fabric": ef}
        if c["nivel"] == 2:
            fila["resultado"] = "PENDIENTE_NIVEL_2"
        elif cri == "no_aplica":
            fila["resultado"] = "NO_APLICA"
        elif cod == "CP-01":
            fila.update(valor_stratio=ns, valor_fabric=nf, delta=nf - ns,
                        resultado=("CUMPLE" if ns == nf else "NO_CUMPLE") if cri == "igual" else "INFORMATIVO")
        elif cod == "CP-02":
            ok = not solo_s and not solo_f and not tipos
            fila.update(resultado="CUMPLE" if ok else "NO_CUMPLE", solo_en_stratio=solo_s, solo_en_fabric=solo_f,
                        tipos_distintos=tipos)
        elif cod == "CP-05":
            fila["resultado"] = {"OK": "CUMPLE", "ERROR": "NO_CUMPLE", "NO_APLICA": "NO_APLICA"}.get(ef, "NO_EVALUADO")
            fila["detalle"] = (F["controles"].get("CP-05") or {}).get("detalle")
        elif cri == "sin_fallas":
            fila["resultado"] = "NO_CUMPLE" if ef == "ERROR" and es != "ERROR" else (
                "HEREDADO" if ef == "ERROR" else "CUMPLE")
        elif cri == "sin_regresion":
            fila["resultado"] = "NO_CUMPLE" if PEOR.get(ef, 0) > PEOR.get(es, 0) else "CUMPLE"
        else:
            fila["resultado"] = "INFORMATIVO"
        if cod == "ID-03" and vacias_nuevas:
            fila.update(resultado="NO_CUMPLE", columnas_vacias_solo_en_fabric=vacias_nuevas)
        if cod == "ID-06" and constantes_nuevas:
            fila["constantes_solo_en_fabric"] = constantes_nuevas
        ctl[cod] = fila
    no_cumple = [k for k, v in ctl.items() if v["resultado"] == "NO_CUMPLE"]
    return {"tipo_reporte": "cotejo_rapido", "grupo": grupo,
            "generado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "stratio": {"ubicacion": S["objeto"]["ubicacion"], "tipo_fuente": S["objeto"]["tipo_fuente"], "medido_utc": S["medido_utc"]},
            "fabric": {"ubicacion": F["objeto"]["ubicacion"], "tipo_fuente": F["objeto"]["tipo_fuente"], "medido_utc": F["medido_utc"]},
            "filas": {"stratio": ns, "fabric": nf, "delta": nf - ns, "pct": round(100.0 * nf / ns, 4) if ns else None},
            "esquema": {"columnas_stratio": len(cs), "columnas_fabric": len(cf), "solo_en_stratio": solo_s,
                        "solo_en_fabric": solo_f, "tipos_distintos": tipos,
                        "renombradas_forma": {a: b for a, b in par.items() if a != b}},
            "nulos_distintos": nulos, "vacias_solo_en_fabric": vacias_nuevas, "constantes_solo_en_fabric": constantes_nuevas,
            "controles": ctl, "no_cumple": no_cumple,
            "resultado_rapido": "NO_CUMPLE" if no_cumple else "CUMPLE_NIVEL_0_1",
            "pendiente_nivel2": [k for k, v in ctl.items() if v["resultado"] == "PENDIENTE_NIVEL_2"]}
