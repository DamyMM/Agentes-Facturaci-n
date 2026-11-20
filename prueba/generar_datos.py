"""Genera las planillas de ejemplo del modo prueba (prueba/datos/*.xlsx).

Datos FICTICIOS, inspirados en los ejemplos del manual de procesos, pensados para
ejercitar casos normales y excepciones. Ninguno de estos importes es real.

    python prueba/generar_datos.py
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

DIR = Path(__file__).resolve().parent / "datos"


def libro(nombre: str, hojas: dict[str, list[list]]) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for titulo, filas in hojas.items():
        ws = wb.create_sheet(titulo)
        for fila in filas:
            ws.append(fila)
        for c in ws[1]:
            c.font = Font(bold=True)
    DIR.mkdir(parents=True, exist_ok=True)
    wb.save(DIR / nombre)
    print("  ", DIR / nombre)


def main() -> None:
    libro("tarifarios_clientes.xlsx", {"Tarifas": [
        ["Cliente", "Unidad", "Servicio", "Unidad de medida", "Moneda", "Precio", "Vigente desde", "Observaciones"],
        ["Denver SA", "transporte", "Retiro y devolución de contenedor (AMBA)", "por contenedor", "ARS", 850000, "2026-10-01", ""],
        ["Denver SA", "transporte", "Estadía / demora de camión", "por día", "ARS", 60000, "2026-10-01", "Requiere aviso del transportista y factura del proveedor"],
        ["Denver SA", "transporte", "Desvío", "por evento", "ARS", 45000, "2026-10-01", ""],
        ["Carmocal SA", "transporte", "Retiro y devolución de contenedor (AMBA)", "por contenedor", "ARS", 820000, "2026-09-01", ""],
        ["Toray Argentina", "despacho", "Honorarios despacho importación", "por destinación", "USD", 450, "2026-07-01", "Más gastos por cuenta y orden al costo"],
        ["Toray Argentina", "despacho", "Gastos operativos despachante", "por destinación", "USD", 60, "2026-07-01", ""],
        ["Blend SRL", "forwarder", "Flete marítimo FCL 40' Shanghai-Buenos Aires", "por contenedor", "USD", 2800, "2026-10-15", "Cotización COT-FWD-0457"],
        ["Blend SRL", "forwarder", "Gastos en origen (handling, BL)", "por embarque", "USD", 180, "2026-10-15", ""],
        ["Blend SRL", "forwarder", "Bidones CHX (venta de insumo)", "por unidad", "USD", 35, "2026-10-15", "Costo lo toma Transporte"],
        ["Optimus Courier", "ecommerce", "TLEA (guía aérea courier)", "por guía", "ARS", 9000, "2026-08-01", ""],
        ["Optimus Courier", "ecommerce", "MANI", "por manifiesto", "ARS", 25000, "2026-08-01", ""],
        ["Optimus Courier", "ecommerce", "REENV (reenvase)", "por reenvase", "ARS", 15000, "2026-08-01", ""],
        ["Optimus Courier", "ecommerce", "DESCO", "por consolidado", "ARS", 12000, "2026-08-01", ""],
    ]})

    libro("chx_seguimiento.xlsx", {
        "BaseDatos": [
            ["Carpeta", "Cliente", "Contenedor", "Servicio", "Turno", "Retiro real", "Entrega real", "Devolución real", "Transportista", "Observaciones"],
            ["22455-26", "Denver SA", "TRHU7624820", "Retiro y devolución", "2026-11-17", "2026-11-17", "2026-11-18", "2026-11-19",
             "Transportes del Sur", "Interchange Exolgan 19/11 09:26. Transportista anunció extras por demora (1 día) y desvío"],
            ["22460-26", "Carmocal SA", "MSKU5550001", "Retiro y devolución", "2026-11-21", "", "", "", "Transportes del Sur", "Sólo turno asignado"],
            ["22437-26", "Toray Argentina", "JXJU3331758", "Retiro y devolución", "2026-11-03", "2026-11-03", "2026-11-04", "2026-11-04",
             "Transportes del Sur", "En pedido Blend figura como 22436-26"],
            ["BA01-26", "Denver SA", "TCLU0000001", "Retiro", "2026-11-10", "", "", "", "Transportes del Sur", "CANCELADO según Damián"],
            ["CHX16-26", "Blend SRL", "-", "Entrega de 5 bidones", "2026-11-12", "2026-11-12", "2026-11-12", "", "Transportes del Sur", "Venta corresponde a Forwarder"],
        ],
        "Factura2026": [
            ["Carpeta", "Proveedor", "Factura", "Neto", "IVA", "Total", "Fecha", "Vencimiento"],
            ["22455-26", "Transportes del Sur", "FA-A 00012-00003456", 600000, 126000, 726000, "2026-11-19", "2026-12-19"],
            ["22460-26", "Transportes del Sur", "1", "", "", "", "", ""],
            ["CHX16-26", "Transportes del Sur", ".", "", "", "", "", ""],
        ],
    })

    libro("transferencias.xlsx", {"Pagos Diarios": [
        ["N°", "FECHA", "EMPRESA", "UNIDAD DE NEGOCIO", "PROVEEDOR", "IMPORTE", "METODO DE PAGO", "ENTIDAD", "ODOO", "OPs",
         "CONCEPTO", "ACLARACIONES OPERADOR", "COMPROBANTE", "OPERADOR"],
        [1201, "2026-11-14", "HG Despacho", "Despacho", "ARCA - VEP", 3250000, "VEP", "Banco Galicia", "SI", "OP-0881",
         "Derechos y tasas carpeta 22470-26 Toray", "Por cuenta y orden del cliente; fondos recibidos 11/11", "VEP 26001234567", "Agus"],
        [1202, "2026-11-18", "HG Despacho", "Despacho", "Terminal 4", 185000, "Transferencia", "Banco Galicia", "SI", "OP-0890",
         "Almacenaje terminal carpeta 22470-26 Toray", "Por cuenta y orden", "FA-B 0003-00045678", "Agus"],
        [1203, "2026-11-19", "HG Logística", "Transporte", "Transportes del Sur", 726000, "Transferencia", "Banco Galicia", "SI", "OP-0894",
         "Flete 22455-26 TRHU7624820", "", "FA-A 00012-00003456", "Agus"],
    ]})

    libro("despacho_operaciones.xlsx", {"Operaciones": [
        ["Carpeta", "Cliente", "Tipo", "Destinación", "Oficialización", "Liberación", "Pase a facturación en Odoo", "Digitalización", "Observaciones"],
        ["22470-26", "Toray Argentina", "IMPO", "26001IC04000123X", "2026-11-17", "2026-11-19 10:30", "SI", "", "Canal verde"],
        ["22471-26", "Toray Argentina", "IMPO", "26001IC04000124Y", "2026-11-19", "", "NO", "", "Canal naranja, pendiente de verificación"],
    ]})

    libro("forwarder_operaciones.xlsx", {"Operaciones": [
        ["Operación", "Cliente", "Tipo", "Modalidad", "BL / AWB", "ETA vigente", "ETA anterior", "Cambio de ETA informado",
         "Cotización aceptada", "Moneda", "Observaciones"],
        ["FWD-1102", "Blend SRL", "IMPO", "Marítimo FCL 1x40'", "MSCU1234567", "2026-11-28", "2026-11-25", "2026-11-12",
         "COT-FWD-0457 (aceptada 2026-10-20)", "USD", "BL emitido 2026-11-02; reemisión por corrección de consignatario 2026-11-05"],
        ["FWD-1108", "Blend SRL", "EXPO", "Aéreo", "AWB 020-11223344", "", "", "", "COT-FWD-0470 (aceptada 2026-11-10)", "USD",
         "Salida prevista 2026-11-26"],
        ["CHX16-26", "Blend SRL", "Venta insumo", "-", "-", "", "", "", "Pedido por correo 2026-11-10", "USD", "5 bidones entregados por Transporte el 12/11"],
    ]})

    libro("detalles_optimus.xlsx", {
        "Hoja1": [
            ["Carpeta", "Fecha", "Guía madre", "MANI", "REENV", "Envíos", "Kg", "Estado", "Observaciones"],
            ["C930", "2026-11-03", "001-10047800", "MANI205100A", "", 410, 702.5, "REG", ""],
            ["C933", "2026-11-05", "001-10047850", "MANI205210C", "REENV024700K", 380, 655.0, "REG", ""],
            ["C936", "2026-11-10", "071-62670001", "MANI205330B", "", 295, 512.3, "REG", ""],
            ["C939", "2026-11-18", "001-10047951", "MANI205485D", "REENV024849L", 527, 976.99, "ANULADO", "Error en datos; reemplazado por REENV024860E"],
            ["C945", "2026-11-18", "001-10047951", "MANI205485D", "REENV024860E", 547, 976.99, "REG", "Corrige C939"],
            ["C951", "2026-11-19", "071-62671523", "MANI206278E", "", "", "", "REG", "Aguardo cierre"],
        ],
        "Peones": [
            ["Fecha servicio", "TLEA", "SEMI", "Referencias", "Costo declarado", "Documento"],
            ["2026-11-03", 6, 2, "C930", 1230000, "3-11.pdf"],
            ["2026-11-05", 5, 2, "C933", 1105000, "5-11.pdf"],
            ["2026-11-09", 11, 4, "C936", 2255000, "9-11 al 13-11.pdf (reemplaza 10-11.pdf)"],
        ],
    })


if __name__ == "__main__":
    main()
