"""pipeline-comfandi · herramientas de la pipeline QA v2 (Stratio -> Fabric).

Cada subpaquete es la herramienta de un agente. Nada de aqui imprime credenciales.
"""

from .acceso import dns as _dns

_dns.activar()
