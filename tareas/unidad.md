# Agentes de unidad: Despacho, Forwarder, Transporte y Courier

Sos el agente de **una** unidad (te lo dice el disparo de tu tarea: `despacho`, `forwarder`,
`transporte` o `ecommerce`, que es Courier). Tomás los pedidos de tu unidad, buscás los datos y creás la
factura en Odoo **como borrador**. Administración la revisa y la valida.

Primero leé y seguí `tareas/comun.md`. Tus reglas de facturación están en:

```bash
python -m facturacion.cli reglas <tu unidad>
```

Seguilas al pie de la letra (plazos, qué buscar, excepciones conocidas). Donde dicen «coordinador»,
entendé «el pedido de la cola»; donde dicen `registrar_bitacora`, además cerrá el pedido (paso 4).

## 1. Qué pedidos procesar

Procesá todos los pedidos de tu unidad en estado `derivado` (las tareas no reciben texto al dispararse,
así que no importa si te disparó Recepción, Control o el horario de respaldo):

  ```bash
  python -m facturacion.cli --prueba --agente transporte cola listar --unidad transporte --estado derivado
  ```

Si no hay ninguno, terminá diciendo eso.

## 2. Tomar el pedido

```bash
python -m facturacion.cli --prueba --agente transporte cola tomar HG-20261124-0007
scripts/cola.sh subir "Transporte: HG-20261124-0007 en proceso"
```

Si `tomar` falla porque el pedido ya no está `derivado`, otro agente lo tomó: dejalo.

## 3. Buscar los datos y facturar

Usá las herramientas de siempre, con `unidad` igual a tu unidad (el comando rechaza otra):

```bash
python -m facturacion.cli --prueba --agente transporte herramienta leer_fuente '{"unidad":"transporte","accion":"listar"}'
python -m facturacion.cli --prueba --agente transporte herramienta leer_fuente '{"unidad":"transporte","accion":"buscar","fuente":"chx_seguimiento","hoja":"BaseDatos","texto":"TRHU7624820"}'
python -m facturacion.cli --prueba --agente transporte herramienta odoo_buscar '{"unidad":"transporte","modelo":"account.move","dominio":[["ref","ilike","22455-26"]],"campos":["name","state","amount_total"]}'
python -m facturacion.cli --prueba --agente transporte herramienta odoo_crear_borrador_factura @/tmp/borrador.json
```

Para el borrador, escribí el JSON en un archivo temporal (fuera del repo) y pasalo con `@archivo`.
Facturá **sólo los servicios que dice el pedido**: si el pedido es de una operación de varias unidades,
lo de las otras unidades no es tuyo.

## 4. Cerrar el pedido

Elegí un estado final y dejá el informe en `--resultado` (JSON):

| Estado | Cuándo |
| --- | --- |
| `borrador_creado` | Se creó el borrador (puede haber líneas pendientes aparte, decilo en `pendientes`) |
| `pendiente` | Falta un dato o evidencia: no se creó nada |
| `excepcion` | Hay una diferencia que tiene que ver una persona (montos, referencias que no coinciden) |
| `duplicado` | Ya había factura en Odoo para esa operación |
| `rechazado` | No se debe facturar (operación cancelada, la vende otra unidad, etc.) |

```bash
python -m facturacion.cli --prueba --agente transporte cola cerrar HG-20261124-0007 borrador_creado --resultado @/tmp/resultado.json
scripts/cola.sh subir "Transporte: HG-20261124-0007 borrador_creado"
```

El `--resultado` sigue el formato de informe de tus reglas:

```json
{
  "resumen": "Borrador por retiro y devolución; demora y desvío pendientes de factura del transportista.",
  "factura": {"id": 4512, "nombre": "BORRADOR", "moneda": "ARS", "total": 1028500, "link": "..."},
  "lineas": [{"concepto": "Retiro y devolución", "cantidad": 1, "precio": 850000, "tipo": "servicio"}],
  "evidencia": ["chx_seguimiento BaseDatos fila 2: devolución 19/11", "tarifarios_clientes Tarifas: Denver devolución 850.000"],
  "plazo": "Transporte: servicio ejecutado con evidencia (devolución 19/11).",
  "pendientes": [{"que": "Demora y desvío", "falta": "factura del transportista", "responsable": "Kiara Marquez"}]
}
```

## Respuesta final

El pedido, el estado final y una línea con lo principal (borrador y total, o qué falta).
