"""Definiciones de las herramientas custom (las ejecuta nuestro servidor, no el sandbox).

Las credenciales de Odoo y Google nunca salen de este servidor: el agente pide
la acción, `ejecutor.py` la valida y la ejecuta, y devuelve el resultado.
"""

UNIDADES = ["despacho", "transporte", "forwarder", "ecommerce"]

_unidad = {
    "type": "string",
    "enum": UNIDADES,
    "description": "Unidad de negocio. Define la compañía de Odoo (la fija el servidor).",
}

ODOO_BUSCAR = {
    "type": "custom",
    "name": "odoo_buscar",
    "description": (
        "Lee registros de Odoo (search_read) dentro de la compañía de la unidad. Sólo lectura. "
        "Modelos permitidos: res.partner, product.product, account.move, account.move.line, account.tax, "
        "res.currency, account.journal, sale.order, sale.order.line, purchase.order, purchase.order.line, "
        "project.project, project.task, account.analytic.account, l10n_latam.document.type. "
        "Ejemplo de dominio: [[\"move_type\",\"=\",\"in_invoice\"],[\"ref\",\"ilike\",\"22437-26\"]]."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "unidad": _unidad,
            "modelo": {"type": "string"},
            "dominio": {"type": "array", "description": "Dominio Odoo como lista de triples.", "items": {}},
            "campos": {"type": "array", "items": {"type": "string"}},
            "limite": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            "orden": {"type": "string", "description": "Ej. \"date desc\""},
        },
        "required": ["unidad", "modelo", "dominio", "campos"],
        "additionalProperties": False,
    },
}

LEER_FUENTE = {
    "type": "custom",
    "name": "leer_fuente",
    "description": (
        "Lee un rango de una planilla operativa registrada (Google Sheets o Excel sincronizado). "
        "Sólo lectura. Llamá primero con accion=\"listar\" para ver las fuentes y hojas disponibles para tu "
        "unidad. Con accion=\"leer\" devuelve filas; con \"buscar\" devuelve las filas que contienen el texto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "unidad": _unidad,
            "accion": {"type": "string", "enum": ["listar", "leer", "buscar"]},
            "fuente": {"type": "string", "description": "Nombre corto de la fuente (ej. chx_seguimiento)."},
            "hoja": {"type": "string"},
            "rango": {"type": "string", "description": "Rango A1, ej. A1:N200. Para leer."},
            "texto": {"type": "string", "description": "Texto a buscar (carpeta, contenedor, guía). Para buscar."},
        },
        "required": ["unidad", "accion"],
        "additionalProperties": False,
    },
}

ODOO_CREAR_BORRADOR = {
    "type": "custom",
    "name": "odoo_crear_borrador_factura",
    "description": (
        "Crea una factura de cliente en estado BORRADOR en Odoo. No la valida ni la envía: Administración la "
        "revisa y valida. Rechaza el pedido si ya existe una factura no cancelada para el mismo cliente y la "
        "misma referencia de operación. Cada línea debe indicar su tipo (honorario, servicio, gasto_recuperable, "
        "cuenta_y_orden, adicional) y la evidencia que la respalda."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "unidad": _unidad,
            "partner_id": {"type": "integer", "description": "ID de res.partner del cliente."},
            "referencia_operacion": {
                "type": "string",
                "description": "Carpeta / operación / guía / período que identifica lo facturado. Se guarda en ref.",
            },
            "moneda": {"type": "string", "description": "Código ISO: ARS, USD, EUR."},
            "fecha_factura": {"type": "string", "description": "YYYY-MM-DD. Omitir para que la fije Administración."},
            "tipo_documento_id": {"type": "integer", "description": "l10n_latam.document.type (A, B, E...) si se conoce."},
            "lineas": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "descripcion": {"type": "string"},
                        "tipo_linea": {
                            "type": "string",
                            "enum": ["honorario", "servicio", "gasto_recuperable", "cuenta_y_orden", "adicional"],
                        },
                        "product_id": {"type": "integer"},
                        "cantidad": {"type": "number", "exclusiveMinimum": 0},
                        "precio_unitario": {"type": "number"},
                        "impuestos_ids": {"type": "array", "items": {"type": "integer"}},
                        "evidencia": {"type": "string", "description": "Fuente y referencia que prueba el servicio y el precio."},
                    },
                    "required": ["descripcion", "tipo_linea", "cantidad", "precio_unitario", "evidencia"],
                    "additionalProperties": False,
                },
            },
            "notas_internas": {
                "type": "string",
                "description": "Resumen de evidencia, plazo aplicable y pendientes, para el revisor de Administración.",
            },
        },
        "required": ["unidad", "partner_id", "referencia_operacion", "moneda", "lineas", "notas_internas"],
        "additionalProperties": False,
    },
}

REGISTRAR_BITACORA = {
    "type": "custom",
    "name": "registrar_bitacora",
    "description": (
        "Registra en la bitácora de auditoría el resultado de una solicitud: borrador creado, pendiente o "
        "rechazada, con faltantes y responsables."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "unidad": _unidad,
            "referencia_operacion": {"type": "string"},
            "resultado": {"type": "string", "enum": ["borrador_creado", "pendiente", "rechazada"]},
            "factura_id": {"type": "integer"},
            "detalle": {"type": "string"},
            "faltantes": {"type": "array", "items": {"type": "string"}},
            "responsable": {"type": "string"},
        },
        "required": ["unidad", "referencia_operacion", "resultado", "detalle"],
        "additionalProperties": False,
    },
}

HERRAMIENTAS_ESPECIALISTA = [ODOO_BUSCAR, LEER_FUENTE, ODOO_CREAR_BORRADOR, REGISTRAR_BITACORA]
# El coordinador sólo lee para clasificar; no puede crear facturas.
HERRAMIENTAS_COORDINADOR = [ODOO_BUSCAR, LEER_FUENTE]

# Sin bash, archivos ni web: estos agentes sólo trabajan con las herramientas de arriba.
TOOLSET_DESHABILITADO = {
    "type": "agent_toolset_20260401",
    "default_config": {"enabled": False, "permission_policy": {"type": "always_ask"}},
}
