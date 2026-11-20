"""Pruebas de los controles del servidor con un Odoo falso (no requieren red ni API key)."""

import json

import pytest

from facturacion.ejecutor import NOMBRE_COORDINADOR, Ejecutor
from facturacion.fuentes import Fuentes

EMPRESAS = {
    "despacho": {"company_id": 1, "journal_id": 10},
    "transporte": {"company_id": 2, "journal_id": 20},
    "forwarder": {"company_id": 3, "journal_id": 30},
    "ecommerce": {"company_id": None},  # sin configurar
}


class OdooFalso:
    def __init__(self):
        self.moves = []
        self.llamadas = []

    def search_read(self, model, domain, fields, limit=50, order=None, company_id=None):
        self.llamadas.append((model, domain, company_id))
        if model == "res.currency":
            return [{"id": 99}] if domain == [["name", "=", "USD"]] or domain == [["name", "=", "ARS"]] else []
        if model == "account.move":
            ids = [d[2] for d in domain if isinstance(d, list) and d[0] == "id"]
            if ids:
                return [m for m in self.moves if m["id"] in ids]
            refs = {d[2] for d in domain if isinstance(d, list) and d[0] in ("ref", "invoice_origin")}
            partner = next(d[2] for d in domain if isinstance(d, list) and d[0] == "partner_id")
            return [m for m in self.moves if m["ref"] in refs and m["partner_id"] == partner and m["state"] != "cancel"]
        return []

    def create(self, model, vals, company_id=None):
        assert model == "account.move"
        mid = len(self.moves) + 1
        self.moves.append({"id": mid, "name": "/", "state": "draft", "ref": vals["ref"], "partner_id": vals["partner_id"],
                           "amount_total": 0, "vals": vals})
        return mid

    def link(self, model, rec_id):
        return f"https://odoo/{model}/{rec_id}"


FUENTES = {
    "chx_seguimiento": {"tipo": "xlsx", "path": "x.xlsx", "unidades": ["transporte"], "descripcion": "CHX"},
    "detalles_optimus": {"tipo": "gsheet", "id": "x", "unidades": ["ecommerce"], "descripcion": "Optimus"},
}


@pytest.fixture
def ej(tmp_path):
    return Ejecutor(OdooFalso(), Fuentes(FUENTES), EMPRESAS, dir_bitacora=tmp_path)


def pedido(**kw):
    base = {
        "unidad": "transporte", "partner_id": 7, "referencia_operacion": "22455-26 / TRHU7624820", "moneda": "ARS",
        "notas_internas": "Devolución acreditada por interchange 19/11 09:26.",
        "lineas": [{"descripcion": "Flete retiro y devolución", "tipo_linea": "servicio", "cantidad": 1,
                    "precio_unitario": 850000, "evidencia": "BaseDatos U399 + interchange Exolgan 19/11"}],
    }
    base.update(kw)
    return base


def test_crea_borrador_con_compania_de_la_unidad(ej):
    res, err = ej.ejecutar("odoo_crear_borrador_factura", pedido(), agente="Facturación Transporte")
    assert not err, res
    datos = json.loads(res)
    assert datos["state"] == "draft"
    vals = ej.odoo.moves[0]["vals"]
    assert vals["move_type"] == "out_invoice" and vals["company_id"] == 2 and vals["journal_id"] == 20
    assert "[servicio]" in vals["invoice_line_ids"][0][2]["name"]


def test_rechaza_duplicado(ej):
    ej.ejecutar("odoo_crear_borrador_factura", pedido(), agente="Facturación Transporte")
    res, err = ej.ejecutar("odoo_crear_borrador_factura", pedido(), agente="Facturación Transporte")
    assert err and "Ya existe factura" in res
    assert len(ej.odoo.moves) == 1


def test_linea_sin_evidencia(ej):
    p = pedido()
    p["lineas"][0]["evidencia"] = "  "
    res, err = ej.ejecutar("odoo_crear_borrador_factura", p, agente="Facturación Transporte")
    assert err and "sin evidencia" in res


def test_coordinador_no_factura(ej):
    res, err = ej.ejecutar("odoo_crear_borrador_factura", pedido(), agente=NOMBRE_COORDINADOR)
    assert err and "no crea facturas" in res


def test_unidad_sin_configurar(ej):
    res, err = ej.ejecutar("odoo_crear_borrador_factura", pedido(unidad="ecommerce"), agente="Facturación E-commerce")
    assert err and "company_id" in res


def test_moneda_inexistente(ej):
    res, err = ej.ejecutar("odoo_crear_borrador_factura", pedido(moneda="XYZ"), agente="Facturación Transporte")
    assert err and "Moneda" in res


def test_lectura_modelo_no_permitido(ej):
    res, err = ej.ejecutar("odoo_buscar", {"unidad": "despacho", "modelo": "res.users", "dominio": [], "campos": ["login"]})
    assert err and "no permitido" in res


def test_lectura_filtra_compania(ej):
    ej.ejecutar("odoo_buscar", {"unidad": "forwarder", "modelo": "account.move", "dominio": [], "campos": ["name"]},
                agente="Facturación Forwarder")
    model, domain, cid = ej.odoo.llamadas[-1]
    assert cid == 3 and domain[0] == ["company_id", "in", [3, False]]


def test_fuentes_por_unidad(ej):
    res, err = ej.ejecutar("leer_fuente", {"unidad": "transporte", "accion": "listar"}, agente="Facturación Transporte")
    assert not err and list(json.loads(res)) == ["chx_seguimiento"]
    res, err = ej.ejecutar("leer_fuente", {"unidad": "transporte", "accion": "leer", "fuente": "detalles_optimus",
                                           "hoja": "Hoja1", "rango": "A1:B2"}, agente="Facturación Transporte")
    assert err and "no disponible" in res


def test_bitacora(ej, tmp_path):
    ej.ejecutar("registrar_bitacora", {"unidad": "despacho", "referencia_operacion": "X-1", "resultado": "pendiente",
                                       "detalle": "falta liberación"}, agente="Facturación Despacho")
    lineas = next(tmp_path.glob("*.jsonl")).read_text().splitlines()
    assert any('"resultado": "pendiente"' in l for l in lineas)


def test_xlsx_leer_y_buscar(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "BaseDatos"
    ws.append(["Carpeta", "Contenedor", "Devolución"])
    ws.append(["22437-26", "JXJU3331758", "04/11"])
    ws.append(["22455-26", "TRHU7624820", None])
    path = tmp_path / "chx.xlsx"
    wb.save(path)
    f = Fuentes({"chx": {"tipo": "xlsx", "path": str(path), "unidades": ["transporte"]}})
    assert f.leer("chx", "BaseDatos", "A2:C2") == [["22437-26", "JXJU3331758", "04/11"]]
    r = f.buscar("chx", "BaseDatos", "trhu7624820")
    assert r["total"] == 1 and r["coincidencias"][0]["fila"] == 3 and r["encabezado"][0] == "Carpeta"
