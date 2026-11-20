"""Ejecuta las herramientas custom que piden los agentes, con controles del lado servidor.

Controles que NO dependen de que el modelo se porte bien:
- La compañía de Odoo la fija la unidad (config/empresas.yaml), no el agente.
- Lectura de Odoo limitada a una lista de modelos; sólo search_read.
- Escritura limitada a crear account.move tipo out_invoice en estado borrador.
- Antiduplicado: rechaza si existe factura no cancelada del mismo cliente con la misma referencia.
- El coordinador no puede crear facturas (sólo los especialistas).
- Todo queda en bitacora/AAAA-MM-DD.jsonl.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import yaml

from .herramientas import UNIDADES

RAIZ = Path(__file__).resolve().parent.parent
MODELOS_LECTURA = {
    "res.partner", "product.product", "account.move", "account.move.line", "account.tax", "res.currency",
    "account.journal", "sale.order", "sale.order.line", "purchase.order", "purchase.order.line",
    "project.project", "project.task", "account.analytic.account", "l10n_latam.document.type",
}
# Modelos sin company_id: no se filtra por compañía
MODELOS_SIN_COMPANIA = {"res.currency", "l10n_latam.document.type"}
NOMBRE_COORDINADOR = "Coordinador de Facturación"


class ErrorHerramienta(Exception):
    """Error que se devuelve al agente como tool_result con is_error=True."""


class Ejecutor:
    def __init__(self, odoo, fuentes, empresas: dict | None = None, dir_bitacora: Path | None = None):
        self.odoo = odoo
        self.fuentes = fuentes
        self.empresas = empresas if empresas is not None else yaml.safe_load(
            (RAIZ / "config" / "empresas.yaml").read_text(encoding="utf-8")
        )
        self.dir_bitacora = dir_bitacora or RAIZ / "bitacora"

    # ------------------------------------------------------------------ API
    def ejecutar(self, nombre: str, entrada: dict, agente: str | None = None) -> tuple[str, bool]:
        """Devuelve (texto_resultado, es_error)."""
        try:
            metodo = getattr(self, f"_h_{nombre}", None)
            if metodo is None:
                raise ErrorHerramienta(f"Herramienta desconocida: {nombre}")
            resultado = metodo(entrada, agente)
            self._log("tool", {"herramienta": nombre, "agente": agente, "entrada": entrada, "ok": True})
            return json.dumps(resultado, ensure_ascii=False, default=str), False
        except ErrorHerramienta as e:
            self._log("tool", {"herramienta": nombre, "agente": agente, "entrada": entrada, "error": str(e)})
            return str(e), True
        except Exception as e:  # error de infraestructura (Odoo caído, permisos de Google, etc.)
            self._log("tool", {"herramienta": nombre, "agente": agente, "entrada": entrada, "error": repr(e)})
            return f"Error técnico al ejecutar {nombre}: {e!r}. Informalo como pendiente; no reintentes en bucle.", True

    # ------------------------------------------------------------ helpers
    def _empresa(self, unidad: str) -> dict:
        if unidad not in UNIDADES:
            raise ErrorHerramienta(f"Unidad inválida: {unidad}")
        emp = self.empresas.get(unidad) or {}
        if not emp.get("company_id"):
            raise ErrorHerramienta(f"Falta configurar company_id de la unidad {unidad} en config/empresas.yaml")
        return emp

    def _log(self, tipo: str, datos: dict) -> None:
        self.dir_bitacora.mkdir(parents=True, exist_ok=True)
        ahora = dt.datetime.now().astimezone()
        with open(self.dir_bitacora / f"{ahora:%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": ahora.isoformat(), "tipo": tipo, **datos}, ensure_ascii=False, default=str) + "\n")

    # ------------------------------------------------------------ handlers
    def _h_odoo_buscar(self, e: dict, agente: str | None) -> Any:
        modelo = e["modelo"]
        if modelo not in MODELOS_LECTURA:
            raise ErrorHerramienta(f"Modelo no permitido para lectura: {modelo}")
        emp = self._empresa(e["unidad"])
        dominio = list(e.get("dominio") or [])
        cid = None
        if modelo not in MODELOS_SIN_COMPANIA:
            cid = emp["company_id"]
            if modelo != "res.partner":  # los contactos suelen ser compartidos entre compañías
                dominio = [["company_id", "in", [cid, False]]] + dominio
        return self.odoo.search_read(modelo, dominio, e["campos"], limit=min(int(e.get("limite", 50)), 200),
                                     order=e.get("orden"), company_id=cid)

    def _h_leer_fuente(self, e: dict, agente: str | None) -> Any:
        unidad = e["unidad"]
        if unidad not in UNIDADES:
            raise ErrorHerramienta(f"Unidad inválida: {unidad}")
        permitidas = self.fuentes.permitidas(None if agente == NOMBRE_COORDINADOR else unidad)
        accion = e["accion"]
        if accion == "listar":
            return {k: v.get("descripcion", "") for k, v in permitidas.items()}
        nombre = e.get("fuente")
        if nombre not in permitidas:
            raise ErrorHerramienta(f"Fuente '{nombre}' no disponible para {unidad}. Usá accion=listar.")
        if accion == "leer":
            if not e.get("hoja") and not e.get("rango"):
                return {"hojas": self.fuentes.hojas(nombre), "aviso": "Indicá hoja y rango para leer."}
            return self.fuentes.leer(nombre, e.get("hoja"), e.get("rango"))
        if accion == "buscar":
            if not e.get("texto"):
                raise ErrorHerramienta("Para buscar indicá 'texto'.")
            return self.fuentes.buscar(nombre, e.get("hoja"), e["texto"])
        raise ErrorHerramienta(f"Acción inválida: {accion}")

    def _h_odoo_crear_borrador_factura(self, e: dict, agente: str | None) -> Any:
        if agente == NOMBRE_COORDINADOR:
            raise ErrorHerramienta("El coordinador no crea facturas: derivá al especialista de la unidad.")
        emp = self._empresa(e["unidad"])
        cid = emp["company_id"]
        ref = e["referencia_operacion"].strip()
        if len(ref) < 3:
            raise ErrorHerramienta("referencia_operacion insuficiente: indicá carpeta/operación/guía/período.")
        if not e.get("lineas"):
            raise ErrorHerramienta("La factura no tiene líneas.")
        for i, l in enumerate(e["lineas"], 1):
            if not str(l.get("evidencia", "")).strip():
                raise ErrorHerramienta(f"Línea {i} sin evidencia: no se factura un servicio sin respaldo.")
            if l.get("cantidad", 0) <= 0:
                raise ErrorHerramienta(f"Línea {i}: cantidad debe ser mayor a 0.")

        # Antiduplicado (manual: «evitar facturar dos veces reemisiones», «doble facturación»)
        existentes = self.odoo.search_read(
            "account.move",
            [["move_type", "=", "out_invoice"], ["company_id", "=", cid], ["partner_id", "=", e["partner_id"]],
             ["state", "!=", "cancel"], "|", ["ref", "=", ref], ["invoice_origin", "=", ref]],
            ["id", "name", "state", "ref", "amount_total", "currency_id"], limit=5, company_id=cid,
        )
        if existentes:
            raise ErrorHerramienta(
                "Ya existe factura para este cliente y referencia; no se crea otra. "
                f"Existentes: {json.dumps(existentes, ensure_ascii=False, default=str)}. "
                "Si es un servicio adicional distinto, usá una referencia que lo identifique (ej. '22437-26 / estadía')."
            )

        moneda = self.odoo.search_read("res.currency", [["name", "=", e["moneda"].upper()]], ["id"], limit=1)
        if not moneda:
            raise ErrorHerramienta(f"Moneda no encontrada o inactiva en Odoo: {e['moneda']}")

        lineas = []
        for l in e["lineas"]:
            vals = {
                "name": f"{l['descripcion']} [{l['tipo_linea']}]",
                "quantity": l["cantidad"],
                "price_unit": l["precio_unitario"],
            }
            if l.get("product_id"):
                vals["product_id"] = l["product_id"]
            if l.get("impuestos_ids") is not None:
                vals["tax_ids"] = [(6, 0, l["impuestos_ids"])]
            lineas.append((0, 0, vals))

        evidencia = "\n".join(f"- {l['descripcion']}: {l['evidencia']}" for l in e["lineas"])
        vals = {
            "move_type": "out_invoice",
            "company_id": cid,
            "partner_id": e["partner_id"],
            "currency_id": moneda[0]["id"],
            "ref": ref,
            "invoice_origin": ref,
            "narration": (
                f"BORRADOR generado por agente de facturación ({e['unidad']}). Requiere revisión de Administración.\n\n"
                f"{e['notas_internas']}\n\nEvidencia por línea:\n{evidencia}"
            ),
            "invoice_line_ids": lineas,
        }
        if emp.get("journal_id"):
            vals["journal_id"] = emp["journal_id"]
        if e.get("fecha_factura"):
            vals["invoice_date"] = e["fecha_factura"]
        if e.get("tipo_documento_id"):
            vals["l10n_latam_document_type_id"] = e["tipo_documento_id"]

        move_id = self.odoo.create("account.move", vals, company_id=cid)
        creada = self.odoo.search_read("account.move", [["id", "=", move_id]],
                                       ["id", "name", "state", "amount_untaxed", "amount_total", "currency_id"],
                                       limit=1, company_id=cid)[0]
        if creada.get("state") != "draft":  # nunca debería pasar con create, pero lo verificamos
            raise ErrorHerramienta(f"La factura {move_id} no quedó en borrador (estado {creada.get('state')}). Avisar a Administración.")
        self._log("borrador", {"unidad": e["unidad"], "ref": ref, "move_id": move_id, "agente": agente})
        return {**creada, "link": self.odoo.link("account.move", move_id),
                "aviso": "Borrador creado. Administración debe revisarlo y validarlo en Odoo."}

    def _h_registrar_bitacora(self, e: dict, agente: str | None) -> Any:
        self._log("resultado", {**e, "agente": agente})
        return {"registrado": True}
