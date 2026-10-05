"""Compuerta rapida: con el ETL Validator y el cotejo rapido, decide si el flujo sigue al nivel 2.

  VERDE    corrida OK, roles coherentes, nivel 0/1 cumple            -> se lanza el nivel 2
  AMARILLO corrida OK pero hay avisos (roles corregidos, CP-05 sin ventana, informativos llamativos)
           -> sigue al nivel 2, y el aviso viaja al reporte
  ROJO     no admite justificacion: la corrida fallo, bloqueante real, salida sin commit en la corrida,
           o la tabla quedo vacia -> vuelve a desarrollo HOY; el nivel 2 no se lanza
  (un control 0/1 que no cumple da AMARILLO: la diferencia se analiza en el nivel 2 y al salir se decide)

Un hallazgo NO detiene el lote: el flujo en ROJO sale del lote y se confirma en un lote adicional.
"""
import datetime


def evaluar(flujo, grupo, etl=None, cotejos=None, orquestador_hijos=None, claves_esperadas=None):
    """etl = validador.resumen(...); cotejos = {clave: cotejo_rapido}; orquestador_hijos = [{flujo, estado}]."""
    rojo, amarillo, verde = [], [], []
    if grupo == "orquestador":
        if not etl or etl.get("estado_corrida") != "Completed":
            rojo.append(f"corrida del orquestador: {(etl or {}).get('estado_corrida') or 'sin corrida'}")
        for h in orquestador_hijos or []:
            if h.get("estado") != "Completed":
                rojo.append(f"flujo invocado {h.get('flujo')}: {h.get('estado')}")
        if not rojo:
            verde.append("orquestador aprobado por ejecucion")
    else:
        if not etl:
            amarillo.append("sin corrida del ETL Validator: el nivel 0/1 se evaluo sobre la ultima escritura")
        else:
            if etl.get("estado_corrida") != "Completed":
                rojo.append(f"la corrida termino en {etl.get('estado_corrida')}")
            for b in etl.get("bloqueantes") or []:
                rojo.append(f"bloqueante del validador: {b.get('prueba')} · {b.get('detalle')}")
            if etl.get("roles_invertidos"):
                amarillo.append("el validador invirtio entradas/salidas: se usan los roles del codigo del flujo")
            if etl.get("salidas_sin_commit"):
                rojo.append(f"salidas sin commit en la corrida: {etl['salidas_sin_commit']}")
        for clave in sorted(set(claves_esperadas or []) - set(cotejos or {})):
            amarillo.append(f"{clave} · sin cotejo rapido (falta medir un lado): el nivel 2 decidira")
        for clave, c in (cotejos or {}).items():
            for cod in c.get("no_cumple", []):
                fila = c["controles"][cod]
                txt = (f"{clave} · {cod} no cumple ({fila.get('criterio')})"
                       + (f": Stratio {fila.get('valor_stratio')} vs Fabric {fila.get('valor_fabric')}" if cod == "CP-01" else ""))
                if cod == "ID-01":           # tabla vacia en Fabric con dato en Stratio: no hay nada que analizar
                    rojo.append(txt + " · la tabla quedó vacía")
                else:                        # se analiza en el nivel 2 y se decide al salir de el
                    amarillo.append(txt + " · se analiza en el nivel 2 para decidir si es justificable")
            if (c["controles"].get("CP-05") or {}).get("resultado") == "NO_EVALUADO":
                amarillo.append(f"{clave} · CP-05 sin ventana de corrida")
            if c.get("nulos_distintos"):
                amarillo.append(f"{clave} · nulos distintos en {len(c['nulos_distintos'])} columna(s)")
            if not c.get("no_cumple"):
                verde.append(f"{clave} · nivel 0/1 cumple")
    estado = "ROJO" if rojo else ("AMARILLO" if amarillo else "VERDE")
    return {"flujo": flujo, "grupo": grupo, "estado": estado,
            "siguiente": {"ROJO": "devolver a desarrollo; no lanzar nivel 2",
                          "AMARILLO": "lanzar nivel 2 y llevar los avisos al reporte",
                          "VERDE": "lanzar nivel 2"}[estado] if grupo != "orquestador" else
                         ("aprobado por ejecucion" if estado != "ROJO" else "devolver a desarrollo"),
            "motivos_rojo": rojo, "avisos": amarillo, "cumple": verde,
            "evaluado_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
