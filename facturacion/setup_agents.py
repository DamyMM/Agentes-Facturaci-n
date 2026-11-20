"""Crea (o actualiza) el entorno, los 4 especialistas y el coordinador en Claude Managed Agents.

Se corre UNA vez (y cada vez que cambien prompts o herramientas):
    python -m facturacion.setup_agents

Guarda los IDs en .agents.json; run.py los usa para abrir una sesión por solicitud.
"""

from __future__ import annotations

import json
from pathlib import Path

import anthropic

from . import prompts
from .ejecutor import NOMBRE_COORDINADOR
from .herramientas import HERRAMIENTAS_COORDINADOR, HERRAMIENTAS_ESPECIALISTA, TOOLSET_DESHABILITADO

ARCHIVO_IDS = Path(__file__).resolve().parent.parent / ".agents.json"

# Opus 5.5 en todos. Para bajar costo, los especialistas pueden pasar a "claude-sonnet-5-5".
MODELO_COORDINADOR = {"id": "claude-opus-5-5", "effort": "high"}
MODELO_ESPECIALISTA = {"id": "claude-opus-5-5", "effort": "high"}

ESPECIALISTAS = {
    "despacho": (
        "Facturación Despacho",
        "Factura operaciones de aduana (despachos de importación/exportación) liberadas: honorarios del despachante y "
        "gastos por cuenta y orden (derechos, tasas, VEP). Pasale cliente, carpeta/destinación y lo que hay que facturar.",
        prompts.DESPACHO,
    ),
    "forwarder": (
        "Facturación Forwarder",
        "Factura fletes internacionales (marítimo, aéreo, terrestre): BL/AWB/MIC/CRT, importación 5 días corridos antes "
        "del arribo. Pasale cliente, operación, ETA/ETD y documentos emitidos.",
        prompts.FORWARDER,
    ),
    "transporte": (
        "Facturación Transporte",
        "Factura servicios de camión de Logística y Depósito: retiros, entregas, devoluciones de vacíos, lavado, "
        "estadías y extras con evidencia de ejecución. Pasale cliente, carpeta, contenedor/remito y servicios.",
        prompts.TRANSPORTE,
    ),
    "ecommerce": (
        "Facturación E-commerce",
        "Factura la unidad Courier/E-commerce: quincena Optimus (TLEA, MANI, REENV, DESCO, extraordinarios, cuenta y "
        "orden) y ACC. Pasale cliente y período exacto (desde/hasta) o las carpetas C… a facturar.",
        prompts.ECOMMERCE,
    ),
}


def _guardar(ids: dict) -> None:
    ARCHIVO_IDS.write_text(json.dumps(ids, indent=2), encoding="utf-8")


def _crear_o_actualizar(client, ids: dict, clave: str, **config) -> dict:
    """Crea el agente o, si ya existe, lo actualiza (nueva versión)."""
    if clave in ids:
        actual = client.beta.agents.retrieve(ids[clave]["id"])
        agente = client.beta.agents.update(ids[clave]["id"], version=actual.version, **config)
        print(f"  actualizado {config['name']} -> v{agente.version}")
    else:
        agente = client.beta.agents.create(**config)
        print(f"  creado {config['name']} ({agente.id})")
    ids[clave] = {"id": agente.id, "version": agente.version}
    _guardar(ids)
    return ids[clave]


def main() -> None:
    client = anthropic.Anthropic()
    ids = json.loads(ARCHIVO_IDS.read_text()) if ARCHIVO_IDS.exists() else {}

    if "environment_id" not in ids:
        # Los agentes no usan el sandbox (sin bash ni web): red cerrada.
        env = client.beta.environments.create(
            name="facturacion-hg",
            config={"type": "cloud",
                    "networking": {"type": "limited", "allow_package_managers": False, "allow_mcp_servers": False}},
        )
        ids["environment_id"] = env.id
        _guardar(ids)
        print(f"  entorno {env.id}")

    roster = []
    for unidad, (nombre, descripcion, system) in ESPECIALISTAS.items():
        ref = _crear_o_actualizar(
            client, ids, f"especialista_{unidad}",
            name=nombre, description=descripcion, model=MODELO_ESPECIALISTA, system=system,
            tools=[TOOLSET_DESHABILITADO, *HERRAMIENTAS_ESPECIALISTA],
        )
        roster.append({"type": "agent", "id": ref["id"], "version": ref["version"]})

    _crear_o_actualizar(
        client, ids, "coordinador",
        name=NOMBRE_COORDINADOR,
        description="Recibe solicitudes de facturación y las deriva al especialista de cada unidad.",
        model=MODELO_COORDINADOR,
        system=prompts.COORDINADOR,
        tools=[TOOLSET_DESHABILITADO, *HERRAMIENTAS_COORDINADOR],
        multiagent={
            "type": "multiagent_20261001",
            # Sólo los 4 especialistas: ni copias del coordinador ni agentes improvisados
            "subagents": {"type": "enabled", "predefined_agents": roster, "inline_agents": {"type": "disabled"}},
            # Lotes grandes (semana de liberaciones, quincena Optimus) -> workflow run con los mismos especialistas
            "workflows": {"type": "enabled", "predefined_agents": roster, "inline_agents": {"type": "disabled"}},
        },
    )
    print(f"IDs guardados en {ARCHIVO_IDS}")


if __name__ == "__main__":
    main()
