"""Comandos de terminal que usan las tareas programadas (Agente Recepción, de unidad y Control).

Los agentes no hablan con Odoo ni con las planillas directamente: llaman a estos comandos, que pasan
por `Ejecutor` (compañía forzada por unidad, sólo borradores, antiduplicado, evidencia, bitácora) y por
`Cola` (un archivo por pedido, estados válidos). Cada agente sólo puede actuar sobre su unidad.

    python -m facturacion.cli --prueba --agente transporte herramienta leer_fuente '{"unidad":"transporte","accion":"listar"}'
    python -m facturacion.cli --prueba --agente recepcion cola crear --unidad transporte --cliente Denver ...
    python -m facturacion.cli --agente control cola listar --estado borrador_creado
    python -m facturacion.cli reglas transporte

Salida: JSON por stdout. Código de salida 1 si la herramienta o la cola rechazan el pedido (el motivo va en
stdout para que el agente lo lea).
"""

from __future__ import annotations

import argparse
import json
import sys

import yaml

from . import prompts
from .cola import AGENTES, Cola, ErrorCola, dir_datos
from .ejecutor import NOMBRE_COORDINADOR, Ejecutor
from .fuentes import RAIZ, Fuentes, cargar_config
from .herramientas import HERRAMIENTAS_COORDINADOR, HERRAMIENTAS_ESPECIALISTA, UNIDADES

REGLAS = {
    "recepcion": prompts.COORDINADOR,
    "despacho": prompts.DESPACHO,
    "forwarder": prompts.FORWARDER,
    "transporte": prompts.TRANSPORTE,
    "ecommerce": prompts.ECOMMERCE,
}


def ejecutor(prueba: bool) -> Ejecutor:
    if prueba:
        from .odoo_simulado import OdooSimulado

        return Ejecutor(
            OdooSimulado(archivo=dir_datos(True) / "odoo_simulado.json"),
            Fuentes(cargar_config(RAIZ / "config" / "fuentes.prueba.yaml")),
            empresas=yaml.safe_load((RAIZ / "config" / "empresas.prueba.yaml").read_text(encoding="utf-8")),
            dir_bitacora=RAIZ / "prueba" / "bitacora",
        )
    from .odoo import Odoo

    return Ejecutor(Odoo.desde_entorno(), Fuentes())


def herramienta(prueba: bool, agente: str, nombre: str, entrada: dict) -> tuple[str, bool]:
    """Ejecuta una herramienta con los permisos del agente. Devuelve (texto, es_error)."""
    if agente in UNIDADES:
        permitidas, nombre_agente = HERRAMIENTAS_ESPECIALISTA, f"Facturación {agente}"
        if entrada.get("unidad") != agente:
            return f"El {AGENTES[agente]} sólo trabaja con unidad=\"{agente}\".", True
    else:  # Recepción y Control sólo leen, como el coordinador
        permitidas, nombre_agente = HERRAMIENTAS_COORDINADOR, NOMBRE_COORDINADOR
    definicion = next((h for h in permitidas if h["name"] == nombre), None)
    if definicion is None:
        return f"La herramienta {nombre} no está disponible para {AGENTES[agente]}.", True
    faltan = [c for c in definicion["input_schema"]["required"] if c not in entrada]
    if faltan:
        return f"Faltan campos obligatorios: {', '.join(faltan)}.", True
    return ejecutor(prueba).ejecutar(nombre, entrada, agente=nombre_agente)


def _salida(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m facturacion.cli", description=__doc__.split("\n")[0])
    p.add_argument("--prueba", action="store_true", help="Odoo simulado y planillas de prueba/datos/")
    p.add_argument("--agente", choices=list(AGENTES), help="Quién llama (define permisos)")
    sub = p.add_subparsers(dest="comando", required=True)

    h = sub.add_parser("herramienta", help="Ejecutar una herramienta (odoo_buscar, leer_fuente, ...)")
    h.add_argument("nombre")
    h.add_argument("entrada", help="JSON con los parámetros, o @archivo.json")

    r = sub.add_parser("reglas", help="Mostrar las reglas de facturación de un agente")
    r.add_argument("quien", choices=list(REGLAS))

    sub.add_parser("reiniciar-prueba", help="Volver el Odoo simulado a sus datos iniciales")

    c = sub.add_parser("cola", help="Pedidos entre tareas")
    cs = c.add_subparsers(dest="accion", required=True)
    cc = cs.add_parser("crear")
    cc.add_argument("--unidad", choices=UNIDADES + ["ninguna"], required=True)
    for campo in ("cliente", "referencia", "servicios", "motivo", "solicitud", "origen"):
        cc.add_argument(f"--{campo}", required=True)
    cv = cs.add_parser("ver")
    cv.add_argument("id")
    cl = cs.add_parser("listar")
    cl.add_argument("--estado")
    cl.add_argument("--unidad")
    ct = cs.add_parser("tomar")
    ct.add_argument("id")
    cx = cs.add_parser("cerrar", help="Resultado final del agente de unidad")
    cx.add_argument("id")
    cx.add_argument("estado", choices=["borrador_creado", "pendiente", "excepcion", "duplicado", "rechazado"])
    cx.add_argument("--resultado", required=True, help="JSON con el informe (o @archivo.json)")
    ci = cs.add_parser("informar", help="Control: marcar como informado")
    ci.add_argument("id")
    cr = cs.add_parser("reintentar", help="Control: volver a derivar un pedido trabado")
    cr.add_argument("id")
    ch = cs.add_parser("revision-humana", help="Control: frenar un pedido para que lo vea una persona")
    ch.add_argument("id")
    ch.add_argument("--motivo", required=True)
    cb = cs.add_parser("trabados")
    cb.add_argument("--horas", type=float, default=2.0)

    a = p.parse_args(argv)

    def _json(texto: str) -> dict:
        if texto.startswith("@"):
            texto = open(texto[1:], encoding="utf-8").read()
        return json.loads(texto)

    if a.comando == "reglas":
        print(REGLAS[a.quien])
        return 0
    if a.comando == "reiniciar-prueba":
        if not a.prueba:
            p.error("reiniciar-prueba sólo con --prueba")
        from .odoo_simulado import OdooSimulado

        OdooSimulado(archivo=dir_datos(True) / "odoo_simulado.json", reiniciar=True)
        _salida({"reiniciado": str(dir_datos(True) / "odoo_simulado.json")})
        return 0
    if not a.agente:
        p.error("Indicá --agente")

    if a.comando == "herramienta":
        texto, err = herramienta(a.prueba, a.agente, a.nombre, _json(a.entrada))
        print(texto)
        return 1 if err else 0

    cola = Cola(dir_datos(a.prueba))
    try:
        if a.accion == "crear":
            unidad = None if a.unidad == "ninguna" else a.unidad
            res = cola.crear(solicitud=a.solicitud, origen=a.origen, unidad=unidad, cliente=a.cliente,
                             referencia=a.referencia, servicios=a.servicios, motivo_unidad=a.motivo, agente=a.agente)
        elif a.accion == "ver":
            res = cola.leer(a.id)
        elif a.accion == "listar":
            res = cola.listar(a.estado, a.unidad)
        elif a.accion == "tomar":
            res = cola.tomar(a.id, a.agente)
        elif a.accion == "cerrar":
            res = cola.cambiar(a.id, a.estado, a.agente, f"cerrado: {a.estado}", resultado=_json(a.resultado))
        elif a.accion == "informar":
            res = cola.cambiar(a.id, "informado", a.agente, "informado en el resumen")
        elif a.accion == "reintentar":
            if a.agente != "control":
                raise ErrorCola("Sólo Control reintenta pedidos.")
            res = cola.reintentar(a.id)
        elif a.accion == "revision-humana":
            res = cola.cambiar(a.id, "revision_humana", a.agente, f"a revisión humana: {a.motivo}")
        elif a.accion == "trabados":
            res = cola.trabados(a.horas)
    except ErrorCola as e:
        print(str(e))
        return 1
    _salida(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
