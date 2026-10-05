# pipeline-comfandi · QA v2 de la migración Stratio → Microsoft Fabric

Validación de flujos migrados con **un coordinador en el chat y 11 agentes locales** (Claude Code). Por cada flujo:
ejecuta el ETL Validator v10, mide Stratio y Fabric (niveles 0, 1 y 2), coteja con Stratio como verdad, te pregunta lo
que necesita decidir una persona y, al final, arma el lote y el acta.

- Mapa del proceso: [`docs/mapa/mapa_evidencia_qa.html`](docs/mapa/mapa_evidencia_qa.html) (ábrelo en el navegador; página «v2 · arquitectura»).
- Reglas del coordinador: [`CLAUDE.md`](CLAUDE.md) · Formato de reportes: [`docs/REPORTES_V4.md`](docs/REPORTES_V4.md) · Alcance: [`docs/ALCANCE.md`](docs/ALCANCE.md)

---

## 1. Requisitos (una sola vez por persona)

| Qué | Para qué | Cómo comprobarlo |
|---|---|---|
| Linux o macOS con **Python 3.12** | herramientas `pc` | `python3 --version` |
| **Claude Code** instalado | el coordinador y los agentes | `claude --version` |
| **CLI de Fabric** (`fab`) con tu usuario de Comfandi | API y OneLake de QA | `fab auth status` |
| Acceso a los workspaces de QA (datalake-qa, ingestion-qa, orchestration-qa) | lanzar el validador, leer y publicar | lo da el admin de Fabric |
| **VPN de Comfandi** | Postgres, SFTP y Rocket de Stratio | `python -m pc stratio vpn` |
| Usuario de Rocket (Stratio) | cookie de sesión | entrar a `https://datafabric.comfandi.com.co/rocket` |

## 2. Instalación

```bash
cd ~/Projects
git clone <URL-del-repositorio> pipeline-comfandi
cd pipeline-comfandi

python3 -m venv ~/Projects/.venv               # si ya existe, se reutiliza
~/Projects/.venv/bin/python -m pip install -r requirements.txt

fab auth login                                 # una vez; dura hasta que caduque la sesión
```

## 3. Credenciales (fuera del repositorio, nunca se suben)

Por defecto se buscan en `~/Projects/`. Si las guardas en otra carpeta: `export PC_SECRETOS_DIR=/tu/carpeta`.

| Archivo | Contenido | Permisos |
|---|---|---|
| `~/Projects/.rocket_cookie` | el header **Cookie** completo de Rocket (stickyrocket + stratio-cookie + JSESSIONID). Opcional `.rocket_cookie_2` y `_3` (otras sesiones): las descargas se reparten entre ellas | `chmod 600` |
| `~/Projects/.stratio_conn.json` | `{"postgres": {"host","port","dbname","user","password"}, "sftp": {"host","port","user","password"}}` | `chmod 600` |
| `~/Projects/.azure_metricas_sas` | la firma SAS del bucket `comfqametricsdevqaeus2` | `chmod 600` |

**Cookie de Rocket, paso a paso:** entra a Rocket en el navegador → herramientas de desarrollador → pestaña Red →
cualquier petición a `/rocket/` → copia el valor completo del header `Cookie` → pégalo en el chat (el coordinador lo
guarda con permisos 600) o directamente en el archivo. Dura **2 a 3 horas**; el coordinador te avisa cuánto le queda.

## 4. Arrancar

```bash
cd ~/Projects/pipeline-comfandi
claude
```
y escríbele en lenguaje natural, por ejemplo:

- «Quiero validar el flujo `03-moves` y `23-landing-globales-ssf-tipo-identificacion`.»
- «Retomemos el trabajo `lote12-ola1`.» (todo queda en disco: si se apagó el equipo, sigue donde iba)
- «¿Qué está pendiente de decidir?»

El coordinador:
1. revisa si hay **mejoras sin compartir** y si `fab` tiene sesión;
2. te pregunta los flujos, su grupo (ingesta · analítica · orquestador), las rutas de cada tabla y la ventana de fechas;
3. avanza fase por fase y **se detiene a preguntarte** en cada decisión (tabla completa en `CLAUDE.md §1`).

## 5. Qué vas a ver en cada fase

| Fase | Qué hace | Qué te pregunta |
|---|---|---|
| Arranque | crea el trabajo `trabajos/<T>/` | flujos, grupo, rutas, ventana de fechas |
| ETL v10 | ejecuta el flujo en Fabric y corrige entradas/salidas con el código del flujo | si falta un productor: ¿ejecutarlo? |
| Niveles 0 y 1 | esquema, conteo y nulos de los dos lados (Fabric sin descargar; Postgres dentro de la base) | estado de la cookie y la VPN |
| Semáforo | VERDE y AMARILLO siguen; ROJO vuelve a desarrollo | confirmar la devolución si es ROJO |
| Descarga + nivel 2 | descarga a `cache/` y mide exacto (SHA-256, duplicados, perfil, contrato) | **siempre** avisa tablas, MB y tiempo; las grandes esperan tu confirmación |
| Cotejo | Stratio contra Fabric; el agente mira las dos tablas y documenta cada diferencia | **por cada diferencia**, con todos los datos: justificar · verificar con QA/Comfandi · devolver · analizar más |
| Publicación | sube a OneLake `reportes_v4/` y las mediciones al bucket | — |
| Cierre | expediente por flujo → lote → 3 compuertas → acta (local) | qué entra al lote, responsable y aprobaciones |

## 6. Comandos útiles (los usa el coordinador; también puedes correrlos tú)

```bash
P=~/Projects/.venv/bin/python
$P -m pc trabajo siguiente --trabajo T      # dónde quedó cada flujo y qué sigue
$P -m pc decision --trabajo T               # todo lo que espera tu decisión, con los datos para decidir
$P -m pc trabajo bitacora --trabajo T       # el log de agentes
$P -m pc stratio cookie                     # cuánto le queda a cada cookie
$P -m pc estimar --trabajo T                # tiempo estimado del nivel 2
$P -m pc lote disponibles                   # expedientes listos para un lote
$P -m pc mejora pendientes                  # mejoras del proceso sin compartir
```

## 7. Qué se publica y qué queda local

- **Se publica** (OneLake `Files/resultados/reportes_v4/` + bucket): medición Fabric, medición Stratio, cotejo y cotejo de flujo.
- **Queda local:** el log de agentes, el expediente de cada flujo y el acta (`.docx` y su JSON).
- **Nunca se sube:** credenciales, `trabajos/`, `cache/` y `lotes/` (están en `.gitignore`).

## 8. Si se mejora algo del proceso

Cuando en una sesión se cambia un agente, una herramienta o una regla, el coordinador lo **registra**
(`python -m pc mejora registrar …`) y te avisa. Para compartirlo con el equipo: commit + push y
`python -m pc mejora compartida --id M-00N --commit <sha>`. El registro está en [`docs/MEJORAS.md`](docs/MEJORAS.md).

## 9. Estructura

```
CLAUDE.md                 el coordinador: preguntas por fase, ciclo, estados, imparcialidad, mejoras
.claude/agents/           11 agentes: etl-validador (v10), medidor-rapido-fabric, medidor-rapido-stratio,
                          postgres-fabric, semaforo, gestor-descargas, medidor-completo, cotejador,
                          publicador-reportes, consolidador-revision, acta-final
config/                   pipeline.json (ids, hilos, tasas) · controles.json (catálogo) · acta.json (firmantes)
pc/                       herramientas: python -m pc …
fabric/                   notebook del ETL Validator (v9 base y v10 parametrizado)
docs/                     REPORTES_V4 · ALCANCE · MEJORAS · ESTADO_PRUEBAS · contextos · mapa/
muestras/                 respaldos (pipelines viejas, agentes retirados)
pruebas/                  scripts y definiciones de trabajos de prueba
trabajos/ cache/ lotes/   estado local (no se versiona)
```
