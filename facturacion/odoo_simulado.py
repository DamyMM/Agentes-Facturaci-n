"""Odoo simulado para el modo prueba: misma interfaz que `odoo.Odoo`, datos en un JSON local.

Los borradores que crean los agentes quedan en prueba/odoo_simulado.json para revisarlos.
Los datos iniciales son FICTICIOS (inspirados en ejemplos del manual) y sirven sólo para probar.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "prueba" / "odoo_simulado.json"

DATOS_INICIALES = {
    "res.company": [
        {"id": 1, "name": "Harbor Gateway SRL | Despacho"},
        {"id": 2, "name": "Harbor Gateway SRL | Logística y Depósito"},
        {"id": 3, "name": "Harbor Gateway SRL | Forwarder"},
        {"id": 4, "name": "Harbor Gateway SRL | Courier / E-commerce"},
    ],
    "res.currency": [{"id": 1, "name": "ARS"}, {"id": 2, "name": "USD"}, {"id": 3, "name": "EUR"}],
    "res.partner": [
        {"id": 10, "name": "Denver SA (ejemplo)", "vat": "30-00000001-1", "company_id": False},
        {"id": 11, "name": "Toray Argentina (ejemplo)", "vat": "30-00000002-2", "company_id": False},
        {"id": 12, "name": "Blend SRL (ejemplo)", "vat": "30-00000003-3", "company_id": False},
        {"id": 13, "name": "Optimus Courier (ejemplo)", "vat": "30-00000004-4", "company_id": False},
        {"id": 14, "name": "Carmocal SA (ejemplo)", "vat": "30-00000005-5", "company_id": False},
        {"id": 15, "name": "Transportes del Sur (proveedor, ejemplo)", "vat": "30-00000006-6", "company_id": False},
    ],
    "product.product": [
        {"id": 100, "name": "Honorarios despachante", "default_code": "DES-HON", "company_id": False},
        {"id": 101, "name": "Gastos por cuenta y orden", "default_code": "CYO", "company_id": False},
        {"id": 102, "name": "Flete internacional marítimo", "default_code": "FWD-MAR", "company_id": False},
        {"id": 103, "name": "Flete internacional aéreo", "default_code": "FWD-AIR", "company_id": False},
        {"id": 104, "name": "Flete terrestre / camión", "default_code": "TRA-FLETE", "company_id": False},
        {"id": 105, "name": "Estadía / demora", "default_code": "TRA-EST", "company_id": False},
        {"id": 106, "name": "Servicio courier TLEA", "default_code": "COU-TLEA", "company_id": False},
        {"id": 107, "name": "Servicio courier MANI / REENV", "default_code": "COU-MANI", "company_id": False},
    ],
    "account.tax": [
        {"id": 200, "name": "IVA 21% Ventas", "amount": 21.0, "type_tax_use": "sale", "company_id": 1},
        {"id": 201, "name": "IVA 21% Ventas", "amount": 21.0, "type_tax_use": "sale", "company_id": 2},
        {"id": 202, "name": "IVA 21% Ventas", "amount": 21.0, "type_tax_use": "sale", "company_id": 3},
        {"id": 203, "name": "IVA 21% Ventas", "amount": 21.0, "type_tax_use": "sale", "company_id": 4},
        {"id": 204, "name": "Exento / No gravado", "amount": 0.0, "type_tax_use": "sale", "company_id": 3},
    ],
    "account.journal": [
        {"id": 300, "name": "Ventas Despacho", "type": "sale", "company_id": 1},
        {"id": 301, "name": "Ventas Logística y Depósito", "type": "sale", "company_id": 2},
        {"id": 302, "name": "Ventas Forwarder", "type": "sale", "company_id": 3},
        {"id": 303, "name": "Ventas Courier", "type": "sale", "company_id": 4},
    ],
    "l10n_latam.document.type": [
        {"id": 1, "name": "Factura A", "code": "1"},
        {"id": 6, "name": "Factura B", "code": "6"},
        {"id": 19, "name": "Factura E", "code": "19"},
    ],
    "account.move": [
        # Ya facturada: sirve para probar el antiduplicado
        {"id": 500, "name": "FA-A 00004-00000202", "move_type": "out_invoice", "state": "posted", "company_id": 2,
         "partner_id": 11, "ref": "22437-26 / JXJU3331758", "invoice_origin": "22437-26 / JXJU3331758",
         "currency_id": 1, "amount_total": 580800.0, "invoice_date": "2026-11-05"},
        # Compra del transportista para la carpeta 22455-26
        {"id": 501, "name": "FA-A 00012-00003456", "move_type": "in_invoice", "state": "posted", "company_id": 2,
         "partner_id": 15, "ref": "22455-26 TRHU7624820 flete", "invoice_origin": False,
         "currency_id": 1, "amount_total": 726000.0, "invoice_date": "2026-11-19"},
    ],
    "project.project": [],
    "project.task": [],
    "sale.order": [],
    "sale.order.line": [],
    "purchase.order": [],
    "purchase.order.line": [],
    "account.move.line": [],
    "account.analytic.account": [],
}


def _match(reg: dict, cond) -> bool:
    campo, op, valor = cond
    v = reg.get(campo, False)
    if isinstance(v, list) and v and isinstance(v[0], int):  # many2one guardado como [id, nombre]
        v = v[0]
    if op == "=":
        return v == valor
    if op == "!=":
        return v != valor
    if op == "in":
        return v in valor
    if op == "not in":
        return v not in valor
    if op in ("ilike", "like"):
        return valor is not None and str(valor).lower() in str(v or "").lower()
    if op in (">", ">=", "<", "<="):
        return v is not False and {">": v > valor, ">=": v >= valor, "<": v < valor, "<=": v <= valor}[op]
    raise ValueError(f"Operador no soportado en el Odoo simulado: {op}")


def evaluar_dominio(reg: dict, dominio: list) -> bool:
    """Evalúa un dominio Odoo (notación polaca con '&', '|', '!'; AND implícito)."""
    pila = []
    for tok in reversed(dominio):
        if tok == "&":
            a, b = pila.pop(), pila.pop()
            pila.append(a and b)
        elif tok == "|":
            a, b = pila.pop(), pila.pop()
            pila.append(a or b)
        elif tok == "!":
            pila.append(not pila.pop())
        else:
            pila.append(_match(reg, tok))
    return all(pila)


class OdooSimulado:
    url = "http://odoo-simulado.local"

    def __init__(self, archivo: Path = ARCHIVO, reiniciar: bool = False):
        self.archivo = archivo
        if reiniciar or not archivo.exists():
            self.datos = copy.deepcopy(DATOS_INICIALES)
            self._guardar()
        else:
            self.datos = json.loads(archivo.read_text(encoding="utf-8"))

    def _guardar(self) -> None:
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        self.archivo.write_text(json.dumps(self.datos, indent=2, ensure_ascii=False), encoding="utf-8")

    def search_read(self, model, domain, fields, limit=50, order=None, company_id=None):
        regs = [r for r in self.datos.get(model, []) if evaluar_dominio(r, list(domain))]
        if order:
            campo, *dir_ = order.split()
            regs.sort(key=lambda r: (r.get(campo) is False, r.get(campo)), reverse=bool(dir_ and dir_[0] == "desc"))
        return [{k: r.get(k, False) for k in ["id", *fields]} for r in regs[:limit]]

    def create(self, model, vals, company_id=None) -> int:
        if model != "account.move":
            raise PermissionError("El Odoo simulado sólo permite crear account.move")
        regs = self.datos.setdefault(model, [])
        nuevo_id = max([r["id"] for r in regs], default=0) + 1
        lineas = [l[2] for l in vals.get("invoice_line_ids", [])]
        sin_imp = sum(l["quantity"] * l["price_unit"] for l in lineas)
        reg = {**{k: v for k, v in vals.items() if k != "invoice_line_ids"}, "id": nuevo_id, "name": "/",
               "state": "draft", "lineas": lineas, "amount_untaxed": round(sin_imp, 2), "amount_total": round(sin_imp, 2)}
        regs.append(reg)
        self._guardar()
        return nuevo_id

    def link(self, model: str, rec_id: int) -> str:
        return f"{self.url}/odoo/{model}/{rec_id}"
