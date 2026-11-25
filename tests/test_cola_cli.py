"""Cola de pedidos y comandos de terminal que usan las tareas programadas (sin red)."""

import datetime as dt
import json

import pytest

from facturacion import cli
from facturacion.cola import Cola, ErrorCola


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setenv("HG_DATOS_DIR", str(tmp_path))
    cli.main(["--prueba", "reiniciar-prueba"])
    return tmp_path


def correr(capsys, *args):
    codigo = cli.main(["--prueba", *args])
    salida = capsys.readouterr().out
    try:
        return codigo, json.loads(salida)
    except json.JSONDecodeError:
        return codigo, salida.strip()


def crear(capsys, unidad="transporte", referencia="22455-26", cliente="Denver", servicios="devolución"):
    return correr(capsys, "--agente", "recepcion", "cola", "crear", "--unidad", unidad, "--cliente", cliente,
                  "--referencia", referencia, "--servicios", servicios, "--motivo", "camión",
                  "--origen", "prueba", "--solicitud", "Facturar a Denver la devolución")


def test_circuito_completo(datos, capsys):
    cod, p = crear(capsys)
    assert cod == 0 and p["estado"] == "derivado" and p["id"].startswith("HG-")
    pid = p["id"]

    cod, _ = correr(capsys, "--agente", "despacho", "cola", "tomar", pid)
    assert cod == 1  # no es de su unidad
    cod, p = correr(capsys, "--agente", "transporte", "cola", "tomar", pid)
    assert cod == 0 and p["estado"] == "en_proceso"
    cod, _ = correr(capsys, "--agente", "transporte", "cola", "tomar", pid)
    assert cod == 1  # ya tomado

    borrador = {"unidad": "transporte", "partner_id": 10, "referencia_operacion": "22455-26 / TRHU7624820",
                "moneda": "ARS", "notas_internas": "-",
                "lineas": [{"descripcion": "Devolución", "tipo_linea": "servicio", "cantidad": 1,
                            "precio_unitario": 850000, "evidencia": "BaseDatos fila 2"}]}
    cod, f = correr(capsys, "--agente", "transporte", "herramienta", "odoo_crear_borrador_factura", json.dumps(borrador))
    assert cod == 0 and f["state"] == "draft"
    # El Odoo simulado vive en la carpeta compartida: otra sesión ve el borrador
    assert "22455-26 / TRHU7624820" in (datos / "odoo_simulado.json").read_text()

    with pytest.raises(SystemExit):  # cerrar exige --resultado
        correr(capsys, "--agente", "transporte", "cola", "cerrar", pid, "borrador_creado")
    cod, p = correr(capsys, "--agente", "transporte", "cola", "cerrar", pid, "borrador_creado",
                    "--resultado", json.dumps({"factura": {"id": f["id"]}}))
    assert cod == 0 and p["estado"] == "borrador_creado"

    cod, _ = correr(capsys, "--agente", "transporte", "cola", "informar", pid)
    assert cod == 1  # sólo Control informa
    cod, p = correr(capsys, "--agente", "control", "cola", "informar", pid)
    assert cod == 0 and p["estado"] == "informado" and len(p["historial"]) == 4


def test_permisos_de_herramientas(datos, capsys):
    entrada = json.dumps({"unidad": "transporte", "accion": "listar"})
    assert correr(capsys, "--agente", "despacho", "herramienta", "leer_fuente", entrada)[0] == 1
    assert correr(capsys, "--agente", "transporte", "herramienta", "leer_fuente", entrada)[0] == 0
    assert correr(capsys, "--agente", "recepcion", "herramienta", "leer_fuente", entrada)[0] == 0
    borrador = json.dumps({"unidad": "transporte", "partner_id": 10, "referencia_operacion": "X-123",
                           "moneda": "ARS", "notas_internas": "-", "lineas": []})
    cod, texto = correr(capsys, "--agente", "recepcion", "herramienta", "odoo_crear_borrador_factura", borrador)
    assert cod == 1 and "no está disponible" in texto
    cod, texto = correr(capsys, "--agente", "control", "herramienta", "odoo_crear_borrador_factura", borrador)
    assert cod == 1
    cod, texto = correr(capsys, "--agente", "transporte", "herramienta", "odoo_crear_borrador_factura",
                        json.dumps({"unidad": "transporte"}))
    assert cod == 1 and "Faltan campos" in texto


def test_solo_recepcion_crea_y_sin_repetidos(datos, capsys):
    assert crear(capsys)[0] == 0
    cod, texto = crear(capsys)
    assert cod == 1 and "repetido" in texto
    # Misma operación, otra unidad: es otro pedido (operación de varias unidades)
    assert crear(capsys, unidad="despacho", servicios="despacho")[0] == 0
    with pytest.raises(ErrorCola):
        Cola(datos).crear(solicitud="x", origen="x", unidad="transporte", cliente="x", referencia="123",
                          servicios="x", motivo_unidad="x", agente="transporte")


def test_sin_unidad_va_a_revision_humana(datos, capsys):
    cod, p = crear(capsys, unidad="ninguna", referencia="", cliente="")
    assert cod == 0 and p["estado"] == "revision_humana"


def test_reintento_una_sola_vez(datos, capsys):
    cola = Cola(datos)
    p = cola.crear(solicitud="x", origen="x", unidad="forwarder", cliente="Blend", referencia="FWD-1102",
                   servicios="flete", motivo_unidad="flete")
    p["historial"][-1]["hora"] = (dt.datetime.now().astimezone() - dt.timedelta(hours=3)).isoformat()
    cola._guardar(p)
    assert [t["id"] for t in cola.trabados(2)] == [p["id"]]
    assert correr(capsys, "--agente", "transporte", "cola", "reintentar", p["id"])[0] == 1
    assert correr(capsys, "--agente", "control", "cola", "reintentar", p["id"])[0] == 0
    cod, texto = correr(capsys, "--agente", "control", "cola", "reintentar", p["id"])
    assert cod == 1 and "revisión humana" in texto
    cod, q = correr(capsys, "--agente", "control", "cola", "revision-humana", p["id"], "--motivo", "trabado")
    assert cod == 0 and q["estado"] == "revision_humana"


def test_reglas_por_agente(capsys):
    assert cli.main(["reglas", "transporte"]) == 0
    assert "TRANSPORTE" in capsys.readouterr().out
