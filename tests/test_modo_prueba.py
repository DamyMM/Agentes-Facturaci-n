"""El modo prueba de punta a punta, sin Claude: se llaman las herramientas como lo haría un especialista."""

import json

import pytest
import yaml

from facturacion.ejecutor import Ejecutor
from facturacion.fuentes import RAIZ, Fuentes, cargar_config
from facturacion.odoo_simulado import OdooSimulado, evaluar_dominio


@pytest.fixture
def ej(tmp_path):
    return Ejecutor(
        OdooSimulado(archivo=tmp_path / "odoo.json", reiniciar=True),
        Fuentes(cargar_config(RAIZ / "config" / "fuentes.prueba.yaml")),
        empresas=yaml.safe_load((RAIZ / "config" / "empresas.prueba.yaml").read_text()),
        dir_bitacora=tmp_path,
    )


def llamar(ej, herramienta, agente="Facturación Transporte", **entrada):
    texto, err = ej.ejecutar(herramienta, entrada, agente=agente)
    return (texto if err else json.loads(texto)), err


def test_dominio_polaco():
    r = {"ref": "A", "invoice_origin": "B", "state": "draft", "company_id": 2}
    assert evaluar_dominio(r, [["company_id", "in", [2, False]], "|", ["ref", "=", "X"], ["invoice_origin", "=", "B"]])
    assert not evaluar_dominio(r, [["state", "!=", "draft"]])
    assert evaluar_dominio(r, ["!", ["ref", "ilike", "z"]])


def test_flujo_transporte_22455(ej):
    fuentes, err = llamar(ej, "leer_fuente", unidad="transporte", accion="listar")
    assert not err and "chx_seguimiento" in fuentes and "detalles_optimus" not in fuentes

    hito, _ = llamar(ej, "leer_fuente", unidad="transporte", accion="buscar", fuente="chx_seguimiento",
                     hoja="BaseDatos", texto="TRHU7624820")
    assert hito["total"] == 1 and "2026-11-19" in hito["coincidencias"][0]["valores"]

    tarifa, _ = llamar(ej, "leer_fuente", unidad="transporte", accion="buscar", fuente="tarifarios_clientes",
                       hoja="Tarifas", texto="Denver")
    assert tarifa["total"] == 3

    cliente, _ = llamar(ej, "odoo_buscar", unidad="transporte", modelo="res.partner",
                        dominio=[["name", "ilike", "denver"]], campos=["name"])
    assert cliente[0]["id"] == 10

    compra, _ = llamar(ej, "odoo_buscar", unidad="transporte", modelo="account.move",
                       dominio=[["move_type", "=", "in_invoice"], ["ref", "ilike", "22455-26"]], campos=["name", "amount_total"])
    assert compra[0]["name"] == "FA-A 00012-00003456"

    borrador, err = llamar(ej, "odoo_crear_borrador_factura", unidad="transporte", partner_id=10,
                           referencia_operacion="22455-26 / TRHU7624820", moneda="ARS",
                           notas_internas="Devolución acreditada 19/11.",
                           lineas=[{"descripcion": "Retiro y devolución de contenedor", "tipo_linea": "servicio",
                                    "cantidad": 1, "precio_unitario": 850000, "product_id": 104, "impuestos_ids": [201],
                                    "evidencia": "BaseDatos fila 2 + interchange Exolgan 19/11"}])
    assert not err, borrador
    assert borrador["state"] == "draft" and borrador["amount_untaxed"] == 850000

    # Segundo intento con la misma referencia: rechazado
    _, err = llamar(ej, "odoo_crear_borrador_factura", unidad="transporte", partner_id=10,
                    referencia_operacion="22455-26 / TRHU7624820", moneda="ARS", notas_internas="-",
                    lineas=[{"descripcion": "x", "tipo_linea": "servicio", "cantidad": 1, "precio_unitario": 1, "evidencia": "x"}])
    assert err


def test_ya_facturada_en_datos_iniciales(ej):
    texto, err = llamar(ej, "odoo_crear_borrador_factura", unidad="transporte", partner_id=11,
                        referencia_operacion="22437-26 / JXJU3331758", moneda="ARS", notas_internas="-",
                        lineas=[{"descripcion": "x", "tipo_linea": "servicio", "cantidad": 1, "precio_unitario": 1, "evidencia": "x"}])
    assert err and "FA-A 00004-00000202" in texto


def test_planillas_de_todas_las_unidades(ej):
    for unidad, fuente, hoja, texto in [
        ("despacho", "despacho_operaciones", "Operaciones", "22470-26"),
        ("forwarder", "forwarder_operaciones", "Operaciones", "FWD-1102"),
        ("ecommerce", "detalles_optimus", "Hoja1", "001-10047951"),
        ("despacho", "transferencias", "Pagos Diarios", "22470-26"),
    ]:
        r, err = llamar(ej, "leer_fuente", agente=f"Facturación {unidad}", unidad=unidad, accion="buscar",
                        fuente=fuente, hoja=hoja, texto=texto)
        assert not err and r["total"] >= 1, (unidad, fuente, r)
