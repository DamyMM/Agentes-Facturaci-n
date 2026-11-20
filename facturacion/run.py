"""Procesa una solicitud de facturación: abre una sesión con el coordinador y atiende
las herramientas custom que piden él y los especialistas.

    python -m facturacion.run "Facturar a Denver la devolución del contenedor TRHU7624820, carpeta 22455-26"
    python -m facturacion.run --archivo pedido.txt
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic

from .ejecutor import NOMBRE_COORDINADOR, Ejecutor
import yaml

from .fuentes import RAIZ, Fuentes, cargar_config
from .odoo import Odoo
from .setup_agents import ARCHIVO_IDS


def ejecutor_prueba(reiniciar: bool = False) -> Ejecutor:
    """Odoo simulado + planillas de ejemplo: no toca ningún sistema real."""
    from .odoo_simulado import OdooSimulado

    return Ejecutor(
        OdooSimulado(reiniciar=reiniciar),
        Fuentes(cargar_config(RAIZ / "config" / "fuentes.prueba.yaml")),
        empresas=yaml.safe_load((RAIZ / "config" / "empresas.prueba.yaml").read_text(encoding="utf-8")),
        dir_bitacora=RAIZ / "prueba" / "bitacora",
    )


def procesar_solicitud(texto: str, client: anthropic.Anthropic | None = None, ejecutor: Ejecutor | None = None) -> str:
    client = client or anthropic.Anthropic()
    ejecutor = ejecutor or Ejecutor(Odoo.desde_entorno(), Fuentes())
    ids = json.loads(ARCHIVO_IDS.read_text())
    tope = os.environ.get("SESSION_BUDGET_USD_CENTS", "500")

    session = client.beta.sessions.create(
        agent={"type": "agent", **ids["coordinador"]},
        environment_id=ids["environment_id"],
        title=f"Facturación: {texto[:60]}",
        # Un tope por solicitud: cubre al coordinador, los especialistas y cualquier workflow run.
        budget={"type": "limit", "max_list_cost": {"amount": tope, "currency": "USD"}},
    )
    print(f"Sesión {session.id}  (traza: https://platform.claude.com/workspaces/default/sessions/{session.id})", file=sys.stderr)

    hilos: dict[str, str] = {}      # session_thread_id -> nombre del agente
    runs_abiertos: set[str] = set()
    respuesta: list[str] = []

    with client.beta.sessions.events.stream(session_id=session.id) as stream:
        client.beta.sessions.events.send(
            session_id=session.id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": texto}]}],
        )
        for ev in stream:
            tipo = ev.type
            hilo = getattr(ev, "session_thread_id", None)

            if tipo == "session.thread_created":
                hilos[hilo] = ev.agent_name
            elif tipo == "agent.thread_message_sent":
                print(f"\n→ {ev.to_agent_name}", file=sys.stderr)
            elif tipo == "agent.thread_message_received":
                print(f"\n← informe de {ev.from_agent_name}", file=sys.stderr)

            elif tipo == "agent.message":  # los mensajes de los especialistas no se replican al stream principal
                for b in ev.content:
                    if b.type == "text":
                        respuesta.append(b.text)
                        print(b.text, end="", flush=True)

            elif tipo == "agent.custom_tool_use":
                # Llegan al stream principal aunque las pida un especialista o un hilo de workflow.
                agente = hilos.get(hilo, NOMBRE_COORDINADOR)  # hilo principal o desconocido -> coordinador
                print(f"\n  [{agente}] {ev.name}", file=sys.stderr)
                texto_res, es_error = ejecutor.ejecutar(ev.name, dict(ev.input), agente=agente)
                client.beta.sessions.events.send(
                    session_id=session.id,
                    events=[{
                        "type": "user.custom_tool_result",
                        "custom_tool_use_id": ev.id,
                        "content": [{"type": "text", "text": texto_res}],
                        "is_error": es_error,
                    }],
                )

            elif tipo in ("agent.tool_use", "agent.mcp_tool_use") and getattr(ev, "evaluated_permission", None) == "ask":
                # No hay herramientas del sandbox habilitadas; si algo pide permiso, se niega.
                client.beta.sessions.events.send(
                    session_id=session.id,
                    events=[{"type": "user.tool_confirmation", "tool_use_id": ev.id, "result": "deny"}],
                )

            elif tipo.startswith("workflow_run."):
                run_id = getattr(ev, "workflow_run_id", None) or getattr(ev, "id", None)
                if tipo == "workflow_run.status_ended":
                    runs_abiertos.discard(run_id)
                elif run_id:
                    runs_abiertos.add(run_id)

            elif tipo == "session.status_idle":
                motivo = ev.stop_reason.type
                if motivo == "requires_action":
                    continue  # espera nuestras respuestas de herramientas: seguir escuchando
                if motivo == "end_turn" and not runs_abiertos:
                    break
                if motivo == "budget_reached":
                    respuesta.append(f"\n[Se alcanzó el tope de gasto de la sesión ({tope} centavos USD).]")
                    break
                if motivo == "retries_exhausted":
                    respuesta.append("\n[El agente no pudo completar el turno por errores repetidos.]")
                    break
            elif tipo == "session.status_terminated":
                break
            elif tipo == "session.error":
                print(f"\n[session.error] {ev}", file=sys.stderr)

    print(file=sys.stderr)
    return "".join(respuesta)


def main() -> None:
    p = argparse.ArgumentParser(description="Circuito de facturación Harbor Gateway")
    p.add_argument("solicitud", nargs="?", help="Texto de la solicitud de facturación")
    p.add_argument("--archivo", type=Path, help="Leer la solicitud desde un archivo (p. ej. un correo exportado)")
    p.add_argument("--prueba", action="store_true", help="Usar Odoo simulado y planillas de ejemplo (no toca sistemas reales)")
    p.add_argument("--reiniciar", action="store_true", help="Con --prueba: volver el Odoo simulado a sus datos iniciales")
    a = p.parse_args()
    texto = a.archivo.read_text(encoding="utf-8") if a.archivo else a.solicitud
    if not texto:
        p.error("Indicá la solicitud o --archivo")
    if a.reiniciar and not a.prueba:
        p.error("--reiniciar sólo se usa con --prueba")
    ejecutor = ejecutor_prueba(a.reiniciar) if a.prueba else None
    if a.prueba:
        print("MODO PRUEBA: Odoo simulado (prueba/odoo_simulado.json) y planillas de prueba/datos/", file=sys.stderr)
    procesar_solicitud(texto, ejecutor=ejecutor)


if __name__ == "__main__":
    main()
