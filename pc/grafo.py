"""Grafo del coordinador: de donde se leyo cada lado, que se bajo, que se midio, que se encontro y quien decidio.

Se arma SIEMPRE desde el disco del trabajo (lote.json, bitacora, ciclos, cache, v4/*, codigo/*, partes) y se guarda
en trabajos/<T>/grafo/grafo.json. No guarda nada que no este ya en esos archivos: es un indice para responder
rapido, para el panel y para los markdown de cierre.

  python -m pc grafo construir --trabajo T
  python -m pc grafo contexto  --trabajo T (--flujo F | --nodo ID) [--para agente]   10-20 lineas para decidir o seguir

Nodos (id · tipo): T:trabajo · F:flujo · O:objeto · L:clave/LADO (como se leyo) · D:clave/LADO (descarga en cache) ·
M:clave/LADO (medicion) · C:clave (cotejo) · X:clave/Dn (diferencia) · R:flujo/id (regla de codigo) ·
Q:... (decision de una persona) · P:ruta (publicacion, con URL de navegador) · A:p-NNNN (parte de agente).
"""
import datetime
import json
import os
import urllib.parse

from . import lote as L
from .config import FAB, CFG

_PORTAL = FAB.get("portal", "https://app.fabric.microsoft.com")


def url_navegador(ruta):
    """Files/... de OneLake -> enlace que abre el archivo en el portal de Fabric (no la ruta abfss/dfs)."""
    r = ruta if ruta.startswith(("Files/", "Tables/")) else f"Files/{ruta.lstrip('/')}"
    sel = urllib.parse.quote(r, safe="")
    return (f"{_PORTAL}/groups/{FAB['ws_datalake']}/lakehouses/{FAB['lh_transversal']}"
            f"?ctid={FAB['tenant']}&experience=fabric-developer&selectedPath={sel}&extensionScenario=openArtifact")


def url_bucket(ruta):
    """contenedor/ruta del bucket de metricas -> URL https del blob (la del navegador)."""
    return f"https://{CFG['bucket']['cuenta']}.blob.core.windows.net/{ruta.lstrip('/')}"


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class _G:
    def __init__(self):
        self.nodos, self.aristas = {}, []

    def n(self, id_, tipo_, etiqueta, **datos):
        x = self.nodos.setdefault(id_, {"id": id_, "tipo": tipo_, "etiqueta": etiqueta, "datos": {}, "eventos": []})
        x["datos"].update({k: v for k, v in datos.items() if v is not None})
        return id_

    def a(self, de, rel, a, **datos):
        if de in self.nodos and a in self.nodos:
            self.aristas.append({"de": de, "rel": rel, "a": a, **({"datos": datos} if datos else {})})


def construir(trabajo, guardar=True):
    d = L.leer(trabajo, "lote.json")
    if not d:
        raise FileNotFoundError(f"no existe el trabajo {trabajo}")
    g = _G()
    t = g.n(f"T:{trabajo}", "trabajo", str(trabajo), responsable_acta=d.get("responsable_acta"), pruebas=d.get("pruebas"))
    ciclos = L.leer(trabajo, "v4/ciclos.json", {}) or {}
    from .cache import gestor
    try:
        man = gestor.manifiesto(trabajo)["entradas"]
    except Exception:
        man = {}
    pub = {x["ruta"]: x for x in ((L.leer(trabajo, "v4/publicado.json") or {}).get("archivos") or [])}
    for f in d["flujos"]:
        n = f["nombre_fabric"]
        c = ciclos.get(n) or {}
        cf = L.leer(trabajo, f"v4/flujos/{n}.json") or {}
        enc = cf.get("encabezado") or {}
        sem = L.leer(trabajo, f"semaforo/{n}.json") or {}
        fid = g.n(f"F:{n}", "flujo", n, stratio=f.get("nombre_stratio"), fl=f.get("fl"), grupo=f["grupo"],
                  version=c.get("version", 1), alcance_ciclo=c.get("alcance"), motivo_ciclo=c.get("motivo"),
                  reutilizado_de=c.get("reutilizado_de"), estado=enc.get("estado") or "EN_CURSO", resumen=enc.get("resumen"),
                  semaforo=sem.get("estado"), motivos_rojo=sem.get("motivos_rojo") or None,
                  version_stratio=f.get("version_stratio"), orquestador=f.get("orquestador"))
        g.a(t, "contiene", fid)
        rc = L.leer(trabajo, f"codigo/{n}/revision.json") or {}
        if rc:
            g.nodos[fid]["datos"]["codigo"] = rc.get("veredicto")
            for r in rc.get("reglas") or []:
                rid = g.n(f"R:{n}/{r['id']}", "regla", r.get("regla", "")[:120], resultado=r.get("resultado"),
                          stratio=r.get("stratio"), fabric=r.get("fabric"), impacto=r.get("impacto"), decision=r.get("decision"))
                g.a(fid, "tiene_regla", rid)
        ver = (L.leer(trabajo, "v4/verificaciones.json", {}) or {}).get(n)
        if ver:
            q = g.n(f"Q:{n}/verificacion", "decision", f"verificación {ver.get('decision')}", por=ver.get("por"),
                    decision=ver.get("decision"), nota=ver.get("nota"), utc=ver.get("utc"))
            g.a(q, "decidio", fid)
        for o in f["objetos"]:
            k = o["clave"]
            oid = g.n(f"O:{k}", "objeto", k, ventana=o.get("ventana_fechas"), llave=o.get("llave"),
                      excluir=o.get("excluir_columnas") or None)
            g.a(fid, "contiene", oid)
            cot = L.leer(trabajo, f"v4/cotejos/{k}.json") or {}
            ce = cot.get("encabezado") or {}
            leido = ce.get("como_se_leyo") or {}
            for lado in ("STRATIO", "FABRIC"):
                src = o.get(lado.lower())
                if not src:
                    continue
                cl = leido.get(lado.lower()) or {}
                lid = g.n(f"L:{k}/{lado}", "lectura", f"{lado} {src.get('ruta')}", tipo=src.get("tipo"), ruta=src.get("ruta"),
                          fuente=cl.get("fuente"), filas=cl.get("filas"), bytes=cl.get("bytes"), version_delta=cl.get("version_delta"),
                          commit_utc=cl.get("commit_utc"), medido_utc=cl.get("medido_utc"), nivel=cl.get("nivel_alcanzado"))
                g.a(oid, "lee_de", lid)
                e = man.get(f"{lado}/{k}")
                if e:
                    did = g.n(f"D:{k}/{lado}", "descarga", f"caché {lado} {k}", carpeta=e.get("carpeta"), origen=e.get("origen"),
                              bytes=e.get("bytes"), archivos=e.get("num_archivos") or e.get("archivos"), estado=e.get("estado"),
                              lector=(e.get("meta") or {}).get("lector"), segundos=(e.get("meta") or {}).get("segundos"))
                    g.a(lid, "bajo_a", did)
                m = L.leer(trabajo, f"v4/mediciones/{lado}/{k}.json")
                if m:
                    me = m.get("encabezado") or {}
                    mid = g.n(f"M:{k}/{lado}", "medicion", f"medición {lado} {k}", nivel=me.get("nivel_alcanzado"),
                              medido_utc=me.get("medido_utc"), estado_controles=m.get("estado_controles"))
                    g.a(f"D:{k}/{lado}" if e else lid, "midio", mid)
            if cot:
                met = (cot.get("metricas") or {}).get("filas") or {}
                cid = g.n(f"C:{k}", "cotejo", f"cotejo {k}", estado=ce.get("estado"), resumen=ce.get("resumen"),
                          nivel=ce.get("nivel_alcanzado"), filas_stratio=met.get("stratio"), filas_fabric=met.get("fabric"),
                          delta=met.get("delta"), sin_analizar=ce.get("sin_analizar") or None, faltantes=ce.get("faltantes") or None)
                for lado in ("STRATIO", "FABRIC"):
                    g.a(f"M:{k}/{lado}", "coteja", cid)
                g.a(oid, "cotejado_en", cid)
                for j in cot.get("justificaciones") or []:
                    xid = g.n(f"X:{k}/{j['id']}", "diferencia", f"{j['id']} {j.get('control')} {j.get('tipo') or ''}".strip(),
                              control=j.get("control"), tipo=j.get("tipo"), columna=j.get("columna"),
                              filas_afectadas=j.get("filas_afectadas"), decision=j.get("decision"), causa=j.get("causa"),
                              causa_medida=j.get("causa_medida"), que=j.get("que_se_encontro"), decidido_por=j.get("decidido_por"),
                              ejemplos=len(j.get("ejemplos") or []))
                    g.a(cid, "encontro", xid)
                    if j.get("decidido_por"):
                        dp = j["decidido_por"]
                        quien = (f"{dp.get('quien') or ''} {dp.get('usuario') or ''}".strip() if isinstance(dp, dict) else str(dp))
                        q = g.n(f"Q:{k}/{j['id']}", "decision", f"{j.get('decision')} · {quien}",
                                decision=j.get("decision"), por=quien)
                        g.a(q, "decidio", xid)
                    cols = [x.strip().lower() for x in (j.get("columna") or "").split(",") if x.strip()]
                    for r in rc.get("reglas") or []:
                        txt = " ".join(str(r.get(x) or "") for x in ("regla", "impacto", "stratio", "fabric")).lower()
                        if cols and any(cc in txt for cc in cols):
                            g.a(f"R:{n}/{r['id']}", "explica", xid)
        for ruta, x in pub.items():
            nombre = ruta.rsplit("/", 1)[-1]
            ligado = None
            if x["tipo"] == "cotejo_flujo" and f"_{n}_v" in nombre:
                ligado = fid
            else:
                for o in f["objetos"]:
                    if f"_{o['clave']}_v" in nombre:
                        ligado = f"C:{o['clave']}" if x["tipo"].startswith("cotejo") else \
                            f"M:{o['clave']}/{'STRATIO' if 'stratio' in x['tipo'] else 'FABRIC'}"
            if not ligado:
                continue
            pid = g.n(f"P:{ruta}", "publicacion", nombre, tipo=x["tipo"], version=x.get("version"), head_ok=x.get("head_ok"),
                      url=url_navegador(ruta), bucket=x.get("bucket"), url_bucket=url_bucket(x["bucket"]) if x.get("bucket") else None)
            g.a(ligado if ligado in g.nodos else fid, "publico", pid)
    from . import parte as P
    for p in P.listar(trabajo):
        aid = g.n(f"A:{p['id']}", "parte", f"{p['agente']}: {p['hecho'][:80]}", agente=p["agente"], estado=p["estado"],
                  ts=p["ts"], pregunta=p.get("pregunta"), siguiente=p.get("siguiente"))
        destino = f"O:{p['clave']}" if p.get("clave") else f"F:{p['flujo']}" if p.get("flujo") else t
        g.a(aid, "reporta", destino)
    ev = L.leer_bitacora(trabajo)
    for e in ev:
        ids = ([f"O:{e['clave']}"] if e.get("clave") else []) + ([f"F:{e['flujo']}"] if e.get("flujo") else [])
        for i in ids[:1] or [t]:
            if i in g.nodos:
                g.nodos[i]["eventos"].append(e["evento"])
        if e["estado"] == "DECISION" and e.get("flujo"):
            q = g.n(f"Q:{e['evento']}", "decision", f"{e['accion']} ({e.get('usuario')})", accion=e["accion"],
                    por=e.get("usuario"), utc=e["ts"], detalle=e.get("detalle"))
            g.a(q, "decidio", f"F:{e['flujo']}")
    for x in g.nodos.values():          # solo las ultimas referencias: el detalle esta en la bitacora
        x["n_eventos"] = len(x["eventos"])
        x["eventos"] = x["eventos"][-5:]
    doc = {"trabajo": str(trabajo), "construido_utc": _ahora(), "eventos_bitacora": len(ev),
           "conteo": {tp: sum(1 for x in g.nodos.values() if x["tipo"] == tp) for tp in sorted({x["tipo"] for x in g.nodos.values()})},
           "nodos": g.nodos, "aristas": g.aristas}
    if guardar:
        L.guardar(trabajo, "grafo/grafo.json", doc)
    return doc


def cargar(trabajo, reconstruir=True):
    return construir(trabajo) if reconstruir else (L.leer(trabajo, "grafo/grafo.json") or construir(trabajo))


def _vecinos(g, id_, rel=None, hacia="a"):
    out = []
    for e in g["aristas"]:
        if rel and e["rel"] != rel:
            continue
        if hacia == "a" and e["de"] == id_:
            out.append(g["nodos"][e["a"]])
        elif hacia == "de" and e["a"] == id_:
            out.append(g["nodos"][e["de"]])
    return out


def _f(n):
    return f"{n:,}".replace(",", ".") if isinstance(n, int) else ("—" if n is None else str(n))


def _mb(b):
    return "—" if not b else f"{b / 1e6:,.1f} MB".replace(",", ".")


def contexto(trabajo, flujo=None, nodo=None, para=None, g=None):
    """Lo necesario para decidir o continuar, sin suponer lecturas anteriores (10-20 lineas)."""
    g = g or cargar(trabajo)
    if nodo and nodo not in g["nodos"]:
        raise KeyError(f"no existe el nodo {nodo}")
    if nodo and not nodo.startswith("F:"):
        x = g["nodos"][nodo]
        out = [f"[{x['tipo']}] {x['id']} · {x['etiqueta']}"]
        out += [f"  {k}: {json.dumps(v, ensure_ascii=False, default=str)[:200]}" for k, v in x["datos"].items()]
        for e in g["aristas"]:
            if e["de"] == nodo:
                out.append(f"  → {e['rel']} {e['a']}")
            elif e["a"] == nodo:
                out.append(f"  ← {e['rel']} {e['de']}")
        return "\n".join(out[:30])
    fid = nodo or f"F:{flujo}"
    if fid not in g["nodos"]:
        raise KeyError(f"no existe el flujo {flujo}")
    F = g["nodos"][fid]
    fd = F["datos"]
    out = [f"FLUJO {F['etiqueta']} (Stratio {fd.get('stratio') or '?'} · {fd.get('fl') or 'FL ?'} · {fd.get('grupo')}) "
           f"v{fd.get('version')} · {fd.get('estado')} · semáforo {fd.get('semaforo') or '—'} · código {fd.get('codigo') or 'sin revisión'}"]
    if fd.get("alcance_ciclo"):
        out.append(f"  ciclo v{fd['version']} ({fd['alcance_ciclo']}): {fd.get('motivo_ciclo')}")
    for m in (fd.get("motivos_rojo") or [])[:3]:
        out.append(f"  ROJO: {m[:160]}")
    distintas = [r for r in _vecinos(g, fid, "tiene_regla") if r["datos"].get("resultado") != "IGUAL"]
    for r in distintas[:4]:
        out.append(f"  regla {r['id'].split('/')[-1]} {r['datos'].get('resultado')}: {r['etiqueta'][:110]}")
    for o in _vecinos(g, fid, "contiene"):
        k = o["etiqueta"]
        c = g["nodos"].get(f"C:{k}")
        cd = c["datos"] if c else {}
        out.append(f"  TABLA {k}: {cd.get('estado') or 'sin cotejo'} · filas S {_f(cd.get('filas_stratio'))} | F {_f(cd.get('filas_fabric'))}"
                   f" (Δ {_f(cd.get('delta'))})")
        for lado in ("STRATIO", "FABRIC"):
            ln = g["nodos"].get(f"L:{k}/{lado}")
            if not ln:
                continue
            ld = ln["datos"]
            dn = g["nodos"].get(f"D:{k}/{lado}")
            extra = f" · caché {_mb(dn['datos'].get('bytes'))} {dn['datos'].get('estado') or ''}" if dn else " · sin descargar"
            ver = f" v{ld['version_delta']}" if ld.get("version_delta") is not None else ""
            out.append(f"    {lado[0]}: {ld.get('ruta')}{ver} · {ld.get('fuente') or ld.get('tipo')}"
                       f"{' · commit ' + ld['commit_utc'][:16] if ld.get('commit_utc') else ''}{extra}")
        if c:
            difs = _vecinos(g, c["id"], "encontro")
            pend = [x for x in difs if x["datos"].get("decision") in ("PENDIENTE", "A_VERIFICAR", None)]
            if difs:
                out.append(f"    diferencias: {len(difs)} ({len(pend)} sin decidir)")
            for x in pend[:3 if para != "cotejador" else 8]:
                xd = x["datos"]
                regla = [e["de"] for e in g["aristas"] if e["a"] == x["id"] and e["rel"] == "explica"]
                out.append(f"     · {x['id']}: {xd.get('control')} {xd.get('columna') or ''} {_f(xd.get('filas_afectadas'))} filas"
                           f" · causa: {(xd.get('causa') or 'sin causa')[:90]}{' (medida)' if xd.get('causa_medida') else ''}"
                           + (f" · regla {', '.join(r.split('/')[-1] for r in regla)}" if regla else ""))
            if cd.get("sin_analizar"):
                out.append(f"    sin analizar: {', '.join(map(str, cd['sin_analizar']))[:150]}")
    partes = [x for x in _vecinos(g, fid, "reporta", "de")] + \
             [p for o in _vecinos(g, fid, "contiene") for p in _vecinos(g, o["id"], "reporta", "de")]
    for p in sorted(partes, key=lambda p: p["datos"].get("ts", ""))[-3:]:
        out.append(f"  parte {p['id'][2:]} {p['etiqueta'][:120]}")
        if p["datos"].get("pregunta"):
            out.append(f"    PREGUNTA: {p['datos']['pregunta'].get('texto', '')[:150]}")
    from . import coordinacion as K
    for s in K.siguiente(trabajo):
        if s["flujo"] == F["etiqueta"]:
            out.append(f"  SIGUE: {s['paso']} [{s['agente']}]\n    {s['comando']}")
    return "\n".join(out)


def mermaid(trabajo, flujo, g=None):
    """Subgrafo del flujo en Mermaid (para los markdown de cierre)."""
    g = g or cargar(trabajo, reconstruir=False)
    fid = f"F:{flujo}"
    ids = {fid}
    for _ in range(4):
        ids |= {e["a"] for e in g["aristas"] if e["de"] in ids and not e["a"].startswith("P:")}
        ids |= {e["de"] for e in g["aristas"] if e["a"] in ids and e["de"].startswith(("Q:", "R:"))}
    alias = {i: f"n{j}" for j, i in enumerate(sorted(ids))}
    forma = {"flujo": ("[[", "]]"), "objeto": ("[", "]"), "lectura": ("[/", "/]"), "descarga": ("[(", ")]"),
             "medicion": ("(", ")"), "cotejo": ("{{", "}}"), "diferencia": (">", "]"), "decision": ("([", "])"),
             "regla": ("[\\", "\\]"), "parte": ("(", ")")}
    out = ["```mermaid", "flowchart LR"]
    for i in sorted(ids):
        x = g["nodos"][i]
        a, b = forma.get(x["tipo"], ("[", "]"))
        et = x["etiqueta"].replace('"', "'")[:60]
        extra = x["datos"].get("estado") or x["datos"].get("decision") or x["datos"].get("resultado") or ""
        out.append(f'  {alias[i]}{a}"{et}{(" · " + str(extra)) if extra else ""}"{b}')
    for e in g["aristas"]:
        if e["de"] in ids and e["a"] in ids:
            out.append(f"  {alias[e['de']]} -->|{e['rel']}| {alias[e['a']]}")
    out.append("```")
    return "\n".join(out)
